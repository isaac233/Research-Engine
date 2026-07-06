"""Score router predictions against git-history gold."""

from __future__ import annotations

from pathlib import Path

from gold_from_git import gold_commits
from outcome_record import Outcome
from router_sim import simulate_route


def run_benchmark(router_dir: Path, repo_root: Path, max_commits: int = 20) -> dict[str, float]:
    commits = gold_commits(repo_root, max_count=max_commits)
    f1s: list[float] = []
    for commit in commits:
        if not commit.files:
            continue
        preds = simulate_route(commit.message, router_dir)
        # Flatten predicted files across all routers.
        predicted = {f for files in preds.values() for f in files}
        outcome = Outcome(task=commit.message, predicted=predicted, actual=commit.files)
        f1s.append(outcome.f1())
    if not f1s:
        return {"f1": 0.0, "commits": 0}
    return {"f1": sum(f1s) / len(f1s), "commits": len(f1s)}


def main() -> None:
    base = Path(__file__).resolve().parent.parent.parent
    scores = run_benchmark(base / ".claude" / "agents", base, max_commits=5)
    assert "f1" in scores
    print(f"run_benchmark self-check: OK (F1={scores['f1']:.2f}, commits={scores['commits']})")


if __name__ == "__main__":
    main()
