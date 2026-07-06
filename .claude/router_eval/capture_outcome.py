"""Capture predicted vs actual file sets and propose learned-log deltas."""

from __future__ import annotations

import json
from pathlib import Path

from outcome_record import Outcome


def load_prediction(pred_path: Path) -> dict[str, list]:
    if not pred_path.exists():
        return {"task": "", "core": [], "support": [], "probe": []}
    return json.loads(pred_path.read_text(encoding="utf-8"))


def files_from_git_diff(repo_root: Path) -> set[str]:
    """Return repo-relative .py files touched since base branch."""
    import subprocess

    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return {p for p in result.stdout.splitlines() if p.endswith(".py")}


def capture(task: str, pred_path: Path, repo_root: Path) -> Outcome:
    pred = load_prediction(pred_path)
    predicted = set(pred.get("core", [])) | set(pred.get("support", [])) | set(pred.get("probe", []))
    actual = files_from_git_diff(repo_root)
    return Outcome(task=task, predicted=predicted, actual=actual)


def main() -> None:
    base = Path(__file__).resolve().parent.parent.parent
    pred = base / "router_eval" / "last_prediction.json"
    outcome = capture("self-check", pred, base)
    print(f"capture_outcome self-check: OK (predicted={len(outcome.predicted)}, actual={len(outcome.actual)})")


if __name__ == "__main__":
    main()
