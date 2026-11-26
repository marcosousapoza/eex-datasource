from __future__ import annotations

import argparse
from datetime import UTC, datetime

import pytest

from eex_datasource.cli import build_parser

HELP_PATHS = [
    [],
    ["db"],
    ["db", "upgrade"],
    ["cache"],
    ["cache", "verify"],
    ["cache", "prune"],
    ["sync"],
    ["sync", "derivatives"],
    ["sync", "gas-spot"],
    ["sync", "auctions"],
    ["sync", "indices"],
    ["sync", "transparency-reference"],
    ["sync", "transparency-umm"],
    ["sync", "transparency-series"],
    ["sync", "top-of-book"],
    ["sync", "all"],
]


@pytest.mark.parametrize("path", HELP_PATHS)
def test_every_command_has_useful_help(
    path: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args([*path, "--help"])
    assert caught.value.code == 0
    output = capsys.readouterr().out
    assert "usage:" in output
    assert len(output.splitlines()) >= 5


def test_every_option_has_help_text() -> None:
    missing: list[str] = []

    def inspect(parser: argparse.ArgumentParser, path: str) -> None:
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    inspect(child, f"{path} {name}")
            elif action.dest != "help" and not action.help:
                missing.append(f"{path}: {action.option_strings or [action.dest]}")

    inspect(build_parser(), "eex-datasource")
    assert missing == []


@pytest.mark.parametrize("job", ["transparency-umm", "transparency-series"])
def test_timestamp_options_parse_iso8601_with_utc_default(job) -> None:
    extra = (
        [] if job == "transparency-umm" else ["--area", "DE", "--symbol", "Capacity"]
    )
    args = build_parser().parse_args(
        [
            "sync",
            job,
            "--commodity",
            "POWER",
            "--from",
            "2026-01-01T00:00:00",
            "--to",
            "2026-01-02T00:00:00Z",
            *extra,
        ]
    )
    assert args.date_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert args.date_to == datetime(2026, 1, 2, tzinfo=UTC)
