from __future__ import annotations

import argparse

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
