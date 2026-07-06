"""Deterministic simulation of routing decisions using parsed tables."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

from table_parser import parse_routers


def simulate_route(task: str, router_dir: Path) -> Dict[str, List[str]]:
    """Return a mapping of router name → predicted load files for a task."""
    task_lower = task.lower()
    routers = parse_routers(router_dir)
    predictions: Dict[str, List[str]] = {}
    for name, rf in routers.items():
        for signal, loads in rf.keyword_table.items():
            if any(word.strip(".,;:!?()[]") in task_lower for word in signal.lower().split()):
                predictions.setdefault(name, []).extend(loads)
    # De-duplicate while preserving order.
    for name in predictions:
        seen: Set[str] = set()
        unique: List[str] = []
        for item in predictions[name]:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        predictions[name] = unique
    return predictions


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    preds = simulate_route("main.py launch campaign", base / "agents")
    assert "research-engine-router" in preds
    assert any("main.py" in f for f in preds["research-engine-router"])
    print("router_sim self-check: OK")


if __name__ == "__main__":
    main()
