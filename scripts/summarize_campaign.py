"""Summarize the V3 measurement campaign: RACE (overall + dims) and FACT per cell,
with means for the N=3 groups. Reads bench/out/campaign/scores_*.jsonl.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from bench.runner import _DIMS  # noqa: E402

CAMPAIGN = REPO / "bench" / "out" / "campaign"


def _row(label: str) -> dict[str, float] | None:
    p = CAMPAIGN / f"scores_{label}.jsonl"
    if not p.exists():
        return None
    rec = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    race, fact = rec.get("race", {}), rec.get("fact", {})
    out = {"RACE": race.get("overall_score", 0.0) * 100}
    for dim in _DIMS:
        out[dim[:5]] = race.get(dim, 0.0) * 100
    out["FACT"] = fact.get("citation_accuracy", 0.0) * 100
    return out


def _fmt(label: str, r: dict[str, float] | None) -> str:
    if r is None:
        return f"{label:14s} (missing)"
    cells = " ".join(f"{k}={v:5.2f}" for k, v in r.items())
    return f"{label:14s} {cells}"


def _mean(rows: list[dict[str, float]]) -> dict[str, float]:
    keys = rows[0].keys()
    return {k: statistics.mean(r[k] for r in rows) for k in keys}


def main() -> int:
    print("== class-proof V1 (task 57) ==")
    print("  baseline_57: run scores_task57 separately (recorded by baseline job)")
    print(_fmt("t57_v1", _row("t57_v1")))

    print("\n== V3 A/B (task 53, frozen cache, N=3) ==")
    v1 = [r for lbl in ("t53_v1_r1", "t53_v1_r2", "t53_v1_r3") if (r := _row(lbl))]
    v1v3 = [r for lbl in ("t53_v1v3_r1", "t53_v1v3_r2", "t53_v1v3_r3") if (r := _row(lbl))]
    for lbl in ("t53_v1_r1", "t53_v1_r2", "t53_v1_r3"):
        print(_fmt(lbl, _row(lbl)))
    if v1:
        print(_fmt("V1 MEAN", _mean(v1)))
    for lbl in ("t53_v1v3_r1", "t53_v1v3_r2", "t53_v1v3_r3"):
        print(_fmt(lbl, _row(lbl)))
    if v1v3:
        print(_fmt("V1+V3 MEAN", _mean(v1v3)))
    if v1 and v1v3:
        m1, m3 = _mean(v1), _mean(v1v3)
        delta = {k: m3[k] - m1[k] for k in m1}
        print(_fmt("DELTA(V3-V1)", delta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
