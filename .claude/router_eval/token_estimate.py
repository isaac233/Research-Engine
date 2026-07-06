"""Estimate token cost of a set of files."""

from __future__ import annotations

from pathlib import Path
from typing import Set


def estimate_tokens(file_paths: Set[str], root: Path) -> int:
    """Crude token estimate: ~0.25 tokens per byte for source code."""
    total_bytes = 0
    for p in file_paths:
        fp = root / p
        if fp.exists():
            total_bytes += fp.stat().st_size
    return int(total_bytes / 4)


def main() -> None:
    base = Path(__file__).resolve().parent.parent.parent
    cost = estimate_tokens({"src/research_engine/__init__.py"}, base)
    assert cost >= 0
    print(f"token_estimate self-check: OK ({cost} tokens)")


if __name__ == "__main__":
    main()
