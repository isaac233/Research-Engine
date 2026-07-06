"""Measure token savings of router vs naive whole-dir load."""

from __future__ import annotations

from pathlib import Path

from router_sim import simulate_route
from token_estimate import estimate_tokens


def measure_savings(task: str, router_dir: Path, src_root: Path) -> dict:
    preds = simulate_route(task, router_dir)
    predicted = {f for files in preds.values() for f in files}
    all_files = {str(p.relative_to(src_root.parent)) for p in src_root.rglob("*.py")}
    router_cost = estimate_tokens(predicted, src_root.parent)
    naive_cost = estimate_tokens(all_files, src_root.parent)
    return {
        "router_tokens": router_cost,
        "naive_tokens": naive_cost,
        "savings_tokens": naive_cost - router_cost,
        "savings_ratio": naive_cost / max(router_cost, 1),
    }


def main() -> None:
    base = Path(__file__).resolve().parent.parent.parent
    result = measure_savings("main.py launch campaign", base / ".claude" / "agents", base / "src")
    assert result["savings_ratio"] >= 1.0
    print(f"measure_savings self-check: OK (ratio={result['savings_ratio']:.1f}x)")


if __name__ == "__main__":
    main()
