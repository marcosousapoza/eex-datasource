"""Download current public EEX OpenAPI specification snapshots."""

from __future__ import annotations

import urllib.request
from pathlib import Path

BASE_URL = "https://eds.eex-group.com/api-spec"
NAMES = ("derivatives", "gas_spot", "auctions", "index", "transparency")
DESTINATION = Path(__file__).parents[1] / "specs"


def main() -> None:
    DESTINATION.mkdir(exist_ok=True)
    for name in NAMES:
        url = f"{BASE_URL}/{name}.yaml"
        target = DESTINATION / f"{name}.yaml"
        with urllib.request.urlopen(url, timeout=60) as response:
            target.write_bytes(response.read())
        print(f"Updated {target}")


if __name__ == "__main__":
    main()
