"""Chaos tests on the learned log."""

from __future__ import annotations

import tempfile
from pathlib import Path

from table_parser import parse_learned_log


def test_survives_malformed_lines() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "routes.md"
        p.write_text("| R001 | x | y | z | t | p | 1 | 2026-01-01 | CONFIRMED |\n| bad line |\n", encoding="utf-8")
        items = parse_learned_log(p)
        assert len(items) == 1
        assert items[0].id == "R001"


def test_empty_log() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "routes.md"
        p.write_text("", encoding="utf-8")
        items = parse_learned_log(p)
        assert items == []


def main() -> None:
    test_survives_malformed_lines()
    test_empty_log()
    print("test_log_robustness self-check: OK")


if __name__ == "__main__":
    main()
