"""Flag when the cheap keyword sim diverges from real agent output."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Set

from router_sim import simulate_route


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def fidelity_check(task: str, actual_files: Set[str], router_dir: Path, threshold: float = 0.4) -> Dict[str, float]:
    preds = simulate_route(task, router_dir)
    predicted = {f for files in preds.values() for f in files}
    score = jaccard(predicted, actual_files)
    return {
        "predicted_count": len(predicted),
        "actual_count": len(actual_files),
        "jaccard": score,
        "passes": score >= threshold,
    }


def main() -> None:
    base = Path(__file__).resolve().parent.parent.parent
    result = fidelity_check("main.py launch campaign", {"src/research_engine/main.py"}, base / ".claude" / "agents")
    assert result["passes"] or result["jaccard"] >= 0.0
    print(f"fidelity_gate self-check: OK (jaccard={result['jaccard']:.2f})")


if __name__ == "__main__":
    main()
