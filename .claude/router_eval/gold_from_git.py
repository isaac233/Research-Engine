"""Build external git-history gold from commit diffs for router benchmarking."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GoldCommit:
    commit_hash: str
    message: str
    files: set[str] = field(default_factory=set)


def gold_commits(repo_root: Path, max_count: int = 50) -> list[GoldCommit]:
    result = subprocess.run(
        ["git", "log", f"--max-count={max_count}", "--pretty=format:%H|%s"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    commits: list[GoldCommit] = []
    for line in result.stdout.splitlines():
        if "|" not in line:
            continue
        h, m = line.split("|", 1)
        commits.append(GoldCommit(commit_hash=h, message=m))
    for c in commits:
        files_res = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", c.commit_hash],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        c.files = {p for p in files_res.stdout.splitlines() if p.endswith(".py")}
    return commits


def main() -> None:
    base = Path(__file__).resolve().parent.parent.parent
    commits = gold_commits(base, max_count=5)
    assert all(isinstance(c.files, set) for c in commits)
    print(f"gold_from_git self-check: OK ({len(commits)} commits)")


if __name__ == "__main__":
    main()
