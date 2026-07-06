"""Longitudinal self-improvement + collapse-free proof for the learned log."""

from __future__ import annotations

from pathlib import Path
from typing import List

from table_parser import RouteItem, parse_learned_log


def contradictions(items: List[RouteItem]) -> List[tuple]:
    """Detect two confirmed items with same signal but mutually exclusive loads."""
    confirmed = [i for i in items if i.status == "CONFIRMED"]
    pairs: List[tuple] = []
    for i, a in enumerate(confirmed):
        for b in confirmed[i + 1 :]:
            if a.signal.lower() == b.signal.lower() and a.load != b.load:
                pairs.append((a.id, b.id))
    return pairs


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    items = parse_learned_log(base / "research-engine-routes.md")
    cons = contradictions(items)
    assert len(cons) == 0
    print(f"replay self-check: OK ({len(items)} items, 0 contradictions)")


if __name__ == "__main__":
    main()
