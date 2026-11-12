<div align="center">

# EEX DataSource for Python

**A dependable, typed Python client for the EEX Group DataSource REST API v2.**

[![PyPI](https://img.shields.io/pypi/v/eex-datasource.svg)](https://pypi.org/project/eex-datasource/)
[![Python](https://img.shields.io/pypi/pyversions/eex-datasource.svg)](https://pypi.org/project/eex-datasource/)
[![Typed](https://img.shields.io/badge/typing-py.typed-blue.svg)](https://peps.python.org/pep-0561/)

</div>

`eex-datasource` provides a small synchronous interface to Derivatives, Gas Spot, Auctions, Index,
and Transparency data. It handles authentication, connection pooling, EEX rate limits, retries,
response parsing, and completeness safeguards while preserving the values returned by the source.

> [!IMPORTANT]
> This is an independent client library and is not an official EEX Group product. API access and
> data availability depend on your EEX Group DataSource subscription.

## Why use it?

- **Complete API organization** — coherent namespaces for all five documented API domains.
- **Safe by default** — responses at the record limit are never silently presented as complete.
- **Source fidelity** — decimal prices, nulls, unknown fields, corrections, and cancellations are
  preserved.
- **Production-friendly transport** — pooled connections, bounded retries, safe diagnostics, and a
  shareable one-request-per-second limiter.
- **Typed and lightweight** — Python 3.11+, `py.typed`, and only `httpx` in the core installation.
- **Notebook ready** — optional, consistent conversion to pandas DataFrames.

## Installation

Install the latest release from [PyPI](https://pypi.org/project/eex-datasource/):

```bash
python -m pip install eex-datasource
```

Install pandas support when DataFrame conversion is needed:

```bash
python -m pip install "eex-datasource[pandas]"
```

## Quick start

Create an API token in the [EEX Group DataSource Hub](https://eds.eex-group.com/) and expose it as
an environment variable:

```bash
export EEX_API_TOKEN="your-token"
```

Then discover an instrument and retrieve its trades:

```python
from eex_datasource import EEXClient

with EEXClient() as client:
    commodities = client.derivatives.commodities()
    areas = client.derivatives.areas(commodities[0])
    trading_dates = client.derivatives.trading_dates(commodities[0], areas[0])

    trade_date = trading_dates[-1]
    shortcodes = client.derivatives.shortcodes(
        commodities[0], areas[0], trade_date
    )
    maturities = client.derivatives.maturities(
        commodities[0], areas[0], trade_date, shortcodes[0]
    )

    trades = client.derivatives.trades(
        commodities[0],
        areas[0],
        trade_date,
        shortcode=shortcodes[0],
        maturity=maturities[0],
    )

for trade in trades:
    print(trade)

print(trades.metadata)
```

Date-only parameters accept `datetime.date`, while intraday filters accept `datetime.time`:

```python
from datetime import date, time

trades = client.derivatives.trades(
    "Power",
    "DE",
    trade_date=date(2026, 1, 15),
    time_from=time(8, 30),
    time_to=time(12, 0),
)
```

Equivalent ISO date and time strings remain supported.

An explicit token takes precedence over the environment variable:

```python
client = EEXClient(token="your-token")
```

Always close manually created clients, or prefer the context manager shown above.

## API organization

| Namespace | Data |
|---|---|
| `client.derivatives` | Reference data, trades, top-of-book, statistics, settlements |
| `client.gas_spot` | Reference data, trades, top-of-book, statistics, settlements |
| `client.auctions` | Auction reference data, results, and revenues |
| `client.indices` | Index discovery, daily values, and history |
| `client.transparency` | Companies, facilities, units, UMM events, and time series |

Discovery operations return ordinary `list[str]` values. Single-object operations return a
`Record`; collections return a list-like `Result[Record]` containing:

- `records` — immutable parsed records;
- `metadata` — operation, path, retrieval time, parameters, count, and completeness status;
- `raw` — the original decoded JSON payload;
- `.to_pandas()` — optional DataFrame conversion.

```python
frame = trades.to_pandas()
```

JSON floating-point values are decoded as `Decimal` by default. Conversion to lossy binary floats
is left to the caller. Nested objects are flattened losslessly into dotted columns by default:

```text
capacity.available
capacity.unitMeasure
```

Nested collections such as spread legs, shareholders, and auctioneers remain object columns because
automatically exploding them would change the number and meaning of rows. Disable object flattening
when the original structure is preferred:

```python
frame = trades.to_pandas(flatten=False)
```

Single-object responses support the same conversion:

```python
frame = record.to_pandas()
```

## Historical retrieval and completeness

Range methods correspond to one API request. They do not silently fetch reference data, adjacent
dates, or related instruments.

The reviewed OpenAPI contracts allow up to 60,000 records per request. If a response reaches the
requested limit—or 60,000 when no limit was supplied—the client raises
`SuspectedTruncationError`:

```python
from eex_datasource import SuspectedTruncationError

try:
    trades = client.derivatives.trade_history(
        "Power", "DE", "2026-01-01", "2026-01-31"
    )
except SuspectedTruncationError as error:
    partial_result = error.result
    print(partial_result.metadata.potentially_truncated)
```

Pass `allow_partial=True` only when explicitly accepting an incomplete response. The returned
metadata remains marked as potentially truncated.

## Rate limits and retries

EEX documents a user-wide limit of one request per second. Every operation and retry passes through
a monotonic limiter. Share one limiter when multiple clients use credentials belonging to the same
user:

```python
from eex_datasource import EEXClient, RateLimiter

limiter = RateLimiter()
first = EEXClient("token-one", rate_limiter=limiter)
second = EEXClient("token-two", rate_limiter=limiter)
```

The in-process limiter cannot coordinate separate applications or hosts. Retries are bounded and
limited to transient network failures, HTTP 429, and server errors. Valid `Retry-After` headers are
honored.

## Error handling

All library exceptions derive from `EEXError`:

```text
EEXError
├── ConfigurationError
└── APIError
    ├── InvalidRequestError
    ├── AuthenticationError
    ├── AuthorizationError
    ├── NotFoundError
    ├── RateLimitError
    ├── TransportError
    ├── ResponseParsingError
    ├── SuspectedTruncationError
    └── MultiRequestError
```

Errors retain safe operation, status, parameter, and request-ID diagnostics. Tokens are never
included in exception messages.

## Advanced configuration

```python
import httpx

from eex_datasource import EEXClient

client = EEXClient(
    timeout=httpx.Timeout(30.0, connect=10.0),
    retries=3,
    max_retry_delay=30.0,
)
```

For newly introduced operations, `client.request("/relative/path")` provides low-level GET access
without bypassing authentication, throttling, timeout, retry, or redirect policies. Absolute URLs
are rejected.

## Development

```bash
uv sync --extra dev
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src
uv run pytest
```

Pull requests run these checks on Python 3.11 through 3.14. Distributions are built by GitHub
Actions and published to PyPI from GitHub Releases using Trusted Publishing; maintainers do not
store PyPI API tokens in GitHub.

## Security and data handling

- TLS verification is enabled by default.
- Authorization is never forwarded through redirects.
- Tokens are not written to disk or included in diagnostics.
- Live market data is not cached.
- Source units, prices, timestamps, and update events are not silently rewritten.

Please report security-sensitive issues privately to the repository owner rather than opening a
public issue.

## License

Licensed under the [MIT License](LICENSE).
