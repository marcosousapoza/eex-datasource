# eex-datasource

`eex-datasource` is a small Python client and incremental storage toolkit for
the [EEX Group DataSource REST API v2](https://eds.eex-group.com/).

It provides:

- a synchronous, typed client for Derivatives, Gas Spot, Auctions, Index, and
  Transparency endpoints;
- automatic one-request-per-second pacing and retry handling;
- high-level methods that pool related endpoint calls;
- SHA-256-addressed gzip archives of exact API responses;
- request caching with configurable freshness;
- normalized SQLite and PostgreSQL storage;
- version-aware handling of trade cancellations, settlement corrections, UMM
  updates, and corrected time-series points;
- Alembic migrations and deployment-friendly CLI commands.

The package targets the current EEX v2 API. The older v1 API is not supported.

## Installation

The project uses [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync
```

On filesystems that do not support virtual-environment symlinks (including
some synchronized drives), place the environment outside the project:

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/eex-datasource-venv
uv sync
```

Install optional PostgreSQL and progress-bar support:

```bash
uv sync --extra postgres --extra progress
```

The `tqdm` dependency is optional. Commands work normally without it.

## Authentication

Create an access token in the EEX Group DataSource Hub and export it:

```bash
export EEX_ACCESS_TOKEN="..."
```

The token is sent as a Bearer token and is never included in cache keys,
database request metadata, or logs.

## Python client

```python
from eex_datasource import EEXClient

with EEXClient("your-access-token") as client:
    trades = client.derivatives.trades(
        "POWER",
        "DE",
        "2026-11-25",
        shortcode="DEBM",
        maturity=202612,
    )

    gas_day = client.fetch_market_day(
        "gas_spot",
        "NATGAS",
        "TTF",
        "2026-11-25",
    )

    umms = client.transparency.umm_updates(
        "POWER",
        "2026-11-25T00:00:00Z",
        area="DE",
        facility_type="Producer",
        modified_to="2026-11-26T00:00:00Z",
    )
```

The low-level adapters follow the published endpoint hierarchy:

```python
client.derivatives
client.gas_spot
client.auctions
client.indices
client.transparency
```

Endpoint methods document their behavior in docstrings and refer to the
OpenAPI snapshots in [`specs/`](specs/README.md). Additional query filters use
the API's original names (for example, `fields=["TrdDate", "Px"]`).

Important endpoint differences:

- Gas Spot top-of-book snapshots require a shortcode. If omitted, the client
  discovers shortcodes and pools their snapshots; synchronization retains
  provenance separately for each response.
- Snapshot top-of-book, auction/transparency reference data, and
  shortcode-scoped derivatives reference routes do not support `limit`.
  The argument remains accepted for pooled calls but is not sent on these
  routes. Transparency series also use time bounds rather than `limit`.
- Derivative maturities require a shortcode. Transparency asset IDs require
  their parent IDs, and UMM update scoping requires both `area` and
  `facility_type`; incomplete combinations raise `ValueError`.
- `current_umms()` and `current_adhoc()` require the keyword `validity_from`,
  matching the API's mandatory `validityFrom` query parameter. For example:

  ```python
  client.transparency.current_umms(
      "POWER", "DE", "Producer",
      validity_from="2026-11-25T00:00:00Z",
      validity_to="2026-11-26T00:00:00Z",
  )
  ```

All date-time values returned by EEX remain in their source dictionaries. The
storage layer converts commonly queried fields to Python/SQL date, timestamp,
and decimal types.

## Database setup

SQLite is the default:

```bash
uv run eex-datasource db upgrade
```

Its default URL and archive directory are:

```text
sqlite:///eex-datasource.db
./eex-archive
```

PostgreSQL:

```bash
export EEX_DATABASE_URL="postgresql+psycopg://user:password@host/database"
uv run eex-datasource db upgrade
```

Configuration can be supplied through environment variables:

| Variable | Default |
|---|---|
| `EEX_ACCESS_TOKEN` | none |
| `EEX_DATABASE_URL` | `sqlite:///eex-datasource.db` |
| `EEX_ARCHIVE_DIR` | `eex-archive` |
| `EEX_BASE_URL` | `https://api.eex-group.com/v2` |
| `EEX_REQUEST_INTERVAL` | `1.05` seconds |
| `EEX_TIMEOUT` | `60` seconds |
| `EEX_LOG_LEVEL` | `INFO` |

## Incremental synchronization

Market data:

```bash
uv run eex-datasource sync derivatives \
  --commodity POWER --area DE \
  --from 2026-11-01 --to 2026-11-25

uv run eex-datasource sync gas-spot \
  --commodity NATGAS --area TTF \
  --from 2026-11-01 --to 2026-11-25
```

Auctions and indices:

```bash
uv run eex-datasource sync auctions \
  --from 2026-01-01 --to 2026-11-25

uv run eex-datasource sync indices \
  --commodity NATGAS --area THE --index EGSI_D \
  --from 2026-01-01 --to 2026-11-25
```

Transparency:

```bash
uv run eex-datasource sync transparency-reference \
  --commodity POWER --area DE --validity-date 2026-11-25

uv run eex-datasource sync transparency-umm \
  --commodity POWER --area DE --facility-type Producer \
  --from 2026-11-24T00:00:00Z --to 2026-11-25T00:00:00Z

uv run eex-datasource sync transparency-series \
  --commodity POWER --area DE --symbol AvailableCapacity \
  --from 2026-11-01T00:00:00Z --to 2026-11-25T00:00:00Z
```

Complete top-of-book change history for one instrument:

```bash
uv run eex-datasource sync top-of-book \
  --market derivatives --commodity POWER --area DE \
  --trade-date 2026-11-25 --shortcode DEBM --maturity 202612 \
  --time-from 08:00:00 --time-to 18:00:00
```

The ordinary market sync stores the latest top-of-book values. The dedicated
command stores every published change in hourly request windows.

Use `--force` before the command to bypass the request cache:

```bash
uv run eex-datasource --force sync indices ...
```

For recurring operation, re-fetch a small overlap window. Database imports are
idempotent, while revisions and cancellations remain available. The
`sync_state` table records the last successfully committed watermark for each
scope.

### Batch configuration

`sync all` accepts a JSON list:

```json
[
  {
    "job": "derivatives",
    "commodity": "POWER",
    "area": "DE",
    "date_from": "2026-11-24",
    "date_to": "2026-11-25"
  },
  {
    "job": "indices",
    "commodity": "NATGAS",
    "area": "THE",
    "index": "EGSI_D",
    "date_from": "2026-11-24",
    "date_to": "2026-11-25"
  }
]
```

```bash
uv run eex-datasource sync all --config jobs.json
```

Only one synchronizer may use a database at a time. A database lease prevents
parallel deployment jobs from accidentally exceeding the account-level EEX
rate limit.

## Archive and cache

Responses are stored exactly as received under:

```text
<archive>/sha256/ab/cd/<sha256>.json.gz
```

The database keeps:

- a canonical request hash;
- the uncompressed response hash;
- fetch timestamp, URL, query, response status, and row count;
- compressed and uncompressed object sizes;
- normalized-row provenance.

Request freshness and content deduplication are separate. An identical request
inside the configured TTL is loaded from the archive. After expiry it is
fetched again, allowing mutable data to receive corrections. Identical response
bodies share one gzip object.

Verify or evict archived bodies:

```bash
uv run eex-datasource cache verify
uv run eex-datasource cache prune --older-than 180d
```

Pruning removes gzip bodies but retains hashes, fetch metadata, and normalized
data.

## Database model

Operational tables:

- `sync_run`, `sync_state`, `sync_lease`
- `api_fetch`, `archive_object`

Market tables:

- `market_instrument`, `instrument_snapshot`
- `market_trade`, `top_of_book`, `market_statistic`, `settlement`

Auction and index tables:

- `auction`, `auction_result`, `auction_revenue`
- `index_definition`, `index_observation`

Transparency tables:

- `transparency_company`, `transparency_facility`, `transparency_unit`
- `transparency_capacity`, `transparency_reference_snapshot`
- `umm_thread`, `umm_revision`, `umm_capacity_interval`
- `transparency_series`, `transparency_series_point`

Frequently queried values have typed columns. Every source object is also
retained as JSON, so newly introduced API fields are not discarded.

## Row limits and partitioning

The current EEX documentation permits one request per second and up to 60,000
rows per response. The API does not provide uniform ordering or pagination.

The synchronizer therefore partitions:

- market data by date, then shortcode, then maturity when needed;
- indices by date if a range reaches the limit;
- UMMs into modified-time windows;
- transparency series into bounded time windows.

A leaf response containing exactly 60,000 rows is treated as potentially
truncated and raises an error rather than silently producing incomplete data.

## Deployment

Build the container:

```bash
docker build -t eex-datasource .
```

Run migrations and a sync:

```bash
docker run --rm --env-file .env \
  eex-datasource db upgrade

docker run --rm --env-file .env \
  eex-datasource sync derivatives \
  --commodity POWER --area DE \
  --from 2026-11-24 --to 2026-11-25
```

Mount a persistent volume for SQLite and the archive, or configure PostgreSQL.
Scheduling is intentionally left to cron, systemd, Kubernetes CronJobs, or the
deployment platform rather than embedding another scheduler.

## Development

```bash
uv sync --extra dev --extra progress
uv run --extra dev pytest
uv build
```

The offline tests check adapter paths, trailing slashes, query names, and
required query parameters against the bundled OpenAPI files. PyYAML is used
only for these development tests, not by the runtime client.

### Optional live API tests

Live tests run automatically **only when `EEX_ACCESS_TOKEN` is nonempty**:

```bash
export EEX_ACCESS_TOKEN="..."
uv run --extra dev pytest -m integration -rs
```

Without a token, they skip without making network requests. To run only the
offline suite even when credentials are configured:

```bash
uv run --extra dev pytest -m "not integration"
```

The live tests discover entitled commodities, areas, and dates across all five
API families. They make read-only requests with small limits where supported
and use flat company discovery instead of downloading transparency asset trees.
They share a paced client, respect a minimum 1.05-second request interval, and
honor `EEX_BASE_URL` and `EEX_TIMEOUT`. HTTP 403 and empty discovery lists skip
unavailable products; invalid credentials (HTTP 401), other API failures, and
unexpected response shapes fail the tests. Do not run live tests concurrently
with other jobs using the same account.

The authoritative OpenAPI files and their source URLs are listed in
[`specs/README.md`](specs/README.md).
