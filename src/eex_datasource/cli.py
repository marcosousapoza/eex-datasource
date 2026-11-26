"""Command-line interface for database setup and iterative synchronization."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config

from .client import EEXClient
from .config import Settings
from .storage.archive import Archive
from .storage.database import create_database_engine, session_factory
from .storage.maintenance import prune_archive, verify_archive
from .sync import Synchronizer

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser, using environment settings as option defaults."""
    defaults = Settings.from_env()
    parser = argparse.ArgumentParser(
        prog="eex-datasource",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Rate-limit aware client and incremental data loader for the\n"
            "EEX Group DataSource REST API v2."
        ),
        epilog=(
            "Quick start:\n"
            "  eex-datasource db upgrade\n"
            "  eex-datasource sync derivatives --commodity POWER --area DE \\\n"
            "    --from 2026-11-01 --to 2026-11-25\n\n"
            "Configuration can also be supplied with EEX_ACCESS_TOKEN,\n"
            "EEX_DATABASE_URL, EEX_ARCHIVE_DIR, and EEX_LOG_LEVEL."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=defaults.database_url,
        help=(
            "SQLAlchemy SQLite or PostgreSQL URL "
            "(default: EEX_DATABASE_URL or sqlite:///eex-datasource.db)."
        ),
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=defaults.archive_dir,
        help=(
            "Directory for content-addressed gzip responses "
            "(default: EEX_ARCHIVE_DIR or eex-archive)."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=defaults.base_url,
        help="EEX API root URL; override mainly for tests or proxies.",
    )
    parser.add_argument(
        "--access-token",
        default=defaults.access_token,
        help="EEX Bearer token (prefer the EEX_ACCESS_TOKEN environment variable).",
    )
    parser.add_argument(
        "--log-level",
        default=defaults.log_level,
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        type=str.upper,
        help="Application logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=defaults.timeout,
        help="HTTP timeout in seconds (default: 60).",
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=defaults.request_interval,
        help="Minimum seconds between API request starts (default: 1.05).",
    )
    parser.add_argument(
        "--cache-ttl",
        type=float,
        default=3600,
        help="Freshness period for identical requests in seconds (default: 3600).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass request freshness checks and contact EEX again.",
    )

    commands = parser.add_subparsers(
        dest="command", required=True, metavar="{db,cache,sync}"
    )
    database = commands.add_parser(
        "db",
        help="Manage the relational schema.",
        description="Create or migrate the configured SQLite/PostgreSQL database.",
    )
    database_commands = database.add_subparsers(
        dest="db_command", required=True, metavar="{upgrade}"
    )
    database_commands.add_parser(
        "upgrade",
        help="Upgrade to the latest schema.",
        description=(
            "Apply all packaged Alembic migrations to EEX_DATABASE_URL or "
            "--database-url. This command does not require an EEX token."
        ),
    )

    cache = commands.add_parser(
        "cache",
        help="Verify or prune archived responses.",
        description=(
            "Maintain the SHA-256-addressed gzip response archive. Metadata and "
            "normalized rows remain in the database after body eviction."
        ),
    )
    cache_commands = cache.add_subparsers(
        dest="cache_command", required=True, metavar="{verify,prune}"
    )
    cache_commands.add_parser(
        "verify",
        help="Verify archived hashes.",
        description=(
            "Read every non-evicted gzip object and verify its SHA-256 digest. "
            "Exit status is non-zero when an object is missing or corrupt."
        ),
    )
    prune = cache_commands.add_parser(
        "prune",
        help="Evict old gzip bodies.",
        description=(
            "Delete archived response bodies older than a retention duration. "
            "Fetch manifests, hashes, and normalized data are retained."
        ),
        epilog="Example: eex-datasource cache prune --older-than 180d",
    )
    prune.add_argument(
        "--older-than",
        required=True,
        type=_duration,
        metavar="DURATION",
        help="Retention threshold such as 180d, 24h, 30m, or 60s.",
    )

    sync = commands.add_parser(
        "sync",
        help="Fetch and normalize EEX datasets.",
        description=(
            "Run an idempotent synchronization job. Successful responses are "
            "archived before rows are normalized and sync watermarks advance."
        ),
    )
    jobs = sync.add_subparsers(dest="job", required=True, metavar="JOB")
    market_descriptions = {
        "derivatives": "Synchronize derivative reference data, trades, latest "
        "top-of-book, statistics, and settlements.",
        "gas-spot": "Synchronize Gas Spot reference data, trades, latest "
        "top-of-book, statistics, and settlements.",
    }
    for name, description in market_descriptions.items():
        market = jobs.add_parser(
            name,
            help=description,
            description=description
            + " Valid business dates are discovered first to avoid wasted calls.",
        )
        market.add_argument(
            "--commodity",
            required=True,
            help="EEX commodity code, for example POWER or NATGAS.",
        )
        market.add_argument(
            "--area",
            required=True,
            help="EEX market area code, for example DE or TTF.",
        )
        _date_range(market)

    auctions = jobs.add_parser(
        "auctions",
        help="Synchronize EU ETS auctions.",
        description=(
            "Synchronize auction reference records, results, and auctioneer "
            "revenues for discovered auction dates."
        ),
    )
    auctions.add_argument(
        "--commodity",
        default="ENVIRONMENTALS",
        help="Auction commodity code (default: ENVIRONMENTALS).",
    )
    auctions.add_argument(
        "--area", default="EU", help="Auction area code (default: EU)."
    )
    _date_range(auctions)

    indices = jobs.add_parser(
        "indices",
        help="Synchronize EEX index observations.",
        description=(
            "Synchronize index observations over a date range. Omitted "
            "commodity, area, or index values are discovered from the API."
        ),
    )
    indices.add_argument(
        "--commodity",
        help="Optional commodity code; omit to discover all entitled commodities.",
    )
    indices.add_argument(
        "--area", help="Optional area code; omit to discover entitled areas."
    )
    indices.add_argument("--index", help="Optional index code, for example EGSI_D.")
    _date_range(indices)

    reference = jobs.add_parser(
        "transparency-reference",
        help="Synchronize transparency master data.",
        description=(
            "Fetch the nested company, facility, unit, and capacity tree for "
            "one commodity, country, and validity date."
        ),
    )
    reference.add_argument(
        "--commodity",
        required=True,
        help="Transparency commodity: POWER or NATGAS.",
    )
    reference.add_argument(
        "--area", required=True, help="ISO country code, for example DE."
    )
    reference.add_argument(
        "--validity-date",
        required=True,
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Reference-data validity date.",
    )

    umm = jobs.add_parser(
        "transparency-umm",
        help="Synchronize UMM revisions.",
        description=(
            "Fetch Urgent Market Message updates in daily modified-time windows. "
            "Every message version is retained."
        ),
    )
    umm.add_argument(
        "--commodity",
        required=True,
        help="Transparency commodity: POWER, NATGAS, or OTHER.",
    )
    umm.add_argument("--area", help="Optional ISO country filter.")
    umm.add_argument(
        "--facility-type",
        help="Optional facility type such as Producer, Consumer, or Storage.",
    )
    _timestamp_range(umm)
    umm.add_argument(
        "--adhoc",
        action="store_true",
        help="Use the ad-hoc message endpoint instead of asset UMMs.",
    )

    series = jobs.add_parser(
        "transparency-series",
        help="Synchronize transparency time series.",
        description=(
            "Fetch transparency observations in bounded time windows while "
            "preserving corrected point versions."
        ),
    )
    series.add_argument(
        "--commodity", required=True, help="Commodity: POWER or NATGAS."
    )
    series.add_argument(
        "--area", required=True, help="ISO country code, for example DE."
    )
    series.add_argument(
        "--symbol",
        required=True,
        help="EEX series symbol, for example AvailableCapacity.",
    )
    _timestamp_range(series)
    series.add_argument(
        "--eurowind",
        action="store_true",
        help="Use the EuroWind renewables series endpoint.",
    )
    series.add_argument(
        "--filters",
        type=json.loads,
        default={},
        metavar="JSON",
        help=(
            "Additional query filters as JSON, for example "
            '\'{"fuelType":"Solar"}\' (default: {}).'
        ),
    )

    book = jobs.add_parser(
        "top-of-book",
        help="Synchronize complete intraday book history.",
        description=(
            "Fetch every published top-of-book change for one instrument. "
            "Requests are split into hourly windows."
        ),
    )
    book.add_argument(
        "--market",
        required=True,
        choices=("derivatives", "gas_spot"),
        help="EEX market family.",
    )
    book.add_argument("--commodity", required=True, help="Commodity code.")
    book.add_argument("--area", required=True, help="Market area code.")
    book.add_argument(
        "--trade-date",
        required=True,
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Business date containing the requested interval.",
    )
    book.add_argument(
        "--time-from",
        required=True,
        type=time.fromisoformat,
        metavar="HH:MM:SS",
        help="Inclusive interval start in market time.",
    )
    book.add_argument(
        "--time-to",
        required=True,
        type=time.fromisoformat,
        metavar="HH:MM:SS",
        help="Interval end in market time.",
    )
    book.add_argument(
        "--shortcode",
        help="Product shortcode; required for Gas Spot and usable with maturity.",
    )
    book.add_argument(
        "--maturity",
        help="Derivative maturity paired with --shortcode, for example 202612.",
    )
    book.add_argument(
        "--symbol",
        help="Derivative rolling symbol alternative, for example DEBM+1.",
    )

    all_jobs = jobs.add_parser(
        "all",
        help="Run jobs from a JSON configuration.",
        description=(
            "Run multiple synchronization jobs sequentially from a JSON array. "
            "Each object must contain a 'job' key and that job's normal options."
        ),
        epilog=(
            'Example object: {"job":"derivatives","commodity":"POWER",'
            '"area":"DE","date_from":"2026-11-24",'
            '"date_to":"2026-11-25"}'
        ),
    )
    all_jobs.add_argument(
        "--config",
        type=Path,
        required=True,
        help="JSON file containing a list of sync job argument objects.",
    )
    return parser


def _date_range(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--from",
        dest="date_from",
        required=True,
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="First business date to include.",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        required=True,
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Last business date to include.",
    )


def _timestamp_range(parser: argparse.ArgumentParser) -> None:
    """Add timestamp options without inspecting argparse's private actions."""
    parser.add_argument(
        "--from",
        dest="date_from",
        required=True,
        type=_coerce_datetime,
        metavar="TIMESTAMP",
        help="Inclusive ISO-8601 start, for example 2026-11-24T00:00:00Z.",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        required=True,
        type=_coerce_datetime,
        metavar="TIMESTAMP",
        help="Exclusive ISO-8601 end, for example 2026-11-25T00:00:00Z.",
    )


def main(argv: list[str] | None = None) -> None:
    """Execute a CLI command and exit with its result status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        exit_code = _dispatch(args)
    except Exception as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "db":
        _upgrade(args.database_url)
        return 0

    engine = create_database_engine(args.database_url)
    sessions = session_factory(engine)
    archive = Archive(args.archive_dir)

    if args.command == "cache":
        with sessions() as session:
            if args.cache_command == "verify":
                checked, invalid = verify_archive(session, archive)
                logger.info("Verified %d archive objects; %d invalid", checked, invalid)
                return 1 if invalid else 0
            count = prune_archive(session, archive, args.older_than)
            logger.info("Evicted %d archive objects", count)
            return 0

    if not args.access_token:
        raise ValueError(
            "An access token is required; pass --access-token or set EEX_ACCESS_TOKEN."
        )
    with EEXClient(
        args.access_token,
        base_url=args.base_url,
        timeout=args.timeout,
        request_interval=args.request_interval,
    ) as client:
        synchronizer = Synchronizer(
            client,
            sessions,
            archive,
            cache_ttl=timedelta(seconds=args.cache_ttl),
            force=args.force,
        )
        if args.job == "all":
            jobs = json.loads(args.config.read_text())
            if not isinstance(jobs, list):
                raise ValueError("all-job config must contain a JSON list")
            for item in jobs:
                _run_job(synchronizer, argparse.Namespace(**item))
        else:
            _run_job(synchronizer, args)
    return 0


def _run_job(sync: Synchronizer, args: argparse.Namespace) -> str:
    job = args.job
    if job in ("derivatives", "gas-spot"):
        return sync.market(
            "derivatives" if job == "derivatives" else "gas_spot",
            args.commodity,
            args.area,
            _coerce_date(args.date_from),
            _coerce_date(args.date_to),
        )
    if job == "auctions":
        return sync.auctions(
            getattr(args, "commodity", "ENVIRONMENTALS"),
            getattr(args, "area", "EU"),
            _coerce_date(args.date_from),
            _coerce_date(args.date_to),
        )
    if job == "indices":
        return sync.indices(
            _coerce_date(args.date_from),
            _coerce_date(args.date_to),
            commodity=getattr(args, "commodity", None),
            area=getattr(args, "area", None),
            index=getattr(args, "index", None),
        )
    if job == "transparency-reference":
        return sync.transparency_reference(
            args.commodity,
            args.area,
            _coerce_date(args.validity_date),
        )
    if job == "transparency-umm":
        return sync.transparency_umms(
            args.commodity,
            _coerce_datetime(args.date_from),
            _coerce_datetime(args.date_to),
            area=getattr(args, "area", None),
            facility_type=getattr(args, "facility_type", None),
            adhoc=getattr(args, "adhoc", False),
        )
    if job == "transparency-series":
        return sync.transparency_series(
            args.commodity,
            args.area,
            args.symbol,
            _coerce_datetime(args.date_from),
            _coerce_datetime(args.date_to),
            eurowind=getattr(args, "eurowind", False),
            filters=getattr(args, "filters", {}),
        )
    if job == "top-of-book":
        return sync.top_of_book_history(
            args.market,
            args.commodity,
            args.area,
            _coerce_date(args.trade_date),
            args.time_from
            if isinstance(args.time_from, time)
            else time.fromisoformat(args.time_from),
            args.time_to
            if isinstance(args.time_to, time)
            else time.fromisoformat(args.time_to),
            shortcode=getattr(args, "shortcode", None),
            maturity=getattr(args, "maturity", None),
            symbol=getattr(args, "symbol", None),
        )
    raise ValueError(f"Unknown sync job: {job}")


def _upgrade(database_url: str) -> None:
    configuration = Config()
    configuration.set_main_option(
        "script_location",
        str(Path(__file__).with_name("migrations")),
    )
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(configuration, "head")


def _coerce_datetime(value: str | datetime) -> datetime:
    """Parse ISO-8601 timestamps, treating naive values as UTC."""
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result


def _coerce_date(value: str | date) -> date:
    return date.fromisoformat(value) if isinstance(value, str) else value


def _duration(value: str) -> timedelta:
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    try:
        return timedelta(seconds=float(value[:-1]) * units[value[-1].lower()])
    except (KeyError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            "duration must look like 180d, 24h, 30m, or 60s"
        ) from exc


if __name__ == "__main__":  # pragma: no cover
    main()
