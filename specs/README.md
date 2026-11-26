# EEX OpenAPI specifications

The client follows these public EEX Group DataSource REST API v2
specifications:

- <https://eds.eex-group.com/api-spec/derivatives.yaml>
- <https://eds.eex-group.com/api-spec/gas_spot.yaml>
- <https://eds.eex-group.com/api-spec/auctions.yaml>
- <https://eds.eex-group.com/api-spec/index.yaml>
- <https://eds.eex-group.com/api-spec/transparency.yaml>

Run `python tools/update_specs.py` to refresh the local snapshots. The package
does not parse these files at runtime; they are retained for review and API
drift checks.

Keep the YAML snapshots in version control so contract tests also work in a
fresh checkout without network access.

Adapter module docstrings link to these sources. The offline tests in
[`tests/test_api_contract.py`](../tests/test_api_contract.py) load the snapshots
with PyYAML and check discovery, daily, historical, and pooled requests against
their path templates and declared query parameters (including required ones).
After refreshing snapshots, run:

```bash
uv run --extra dev pytest -m "not integration"
```

The optional read-only checks in
[`tests/test_live_api.py`](../tests/test_live_api.py) run only when
`EEX_ACCESS_TOKEN` is supplied. See the root README for entitlement skips and
rate-limit precautions.
