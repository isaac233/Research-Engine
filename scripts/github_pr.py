"""Create branch, commit, push, and open a GitHub pull request.

Defaults to a dry-run preview. Use ``--live`` to perform real git/GitHub ops.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command without shell interpolation."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _has_changes(cwd: Path) -> bool:
    result = _run(["git", "status", "--porcelain"], cwd=cwd, check=False)
    return bool(result.stdout.strip())


def _current_branch(cwd: Path) -> str:
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return result.stdout.strip()


def _is_git_repo(cwd: Path) -> bool:
    return (cwd / ".git").is_dir()


def _origin_exists(cwd: Path) -> bool:
    result = _run(["git", "remote"], cwd=cwd, check=False)
    return "origin" in result.stdout.splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open a GitHub PR for the current session.")
    parser.add_argument("--message", required=True, help="Commit/PR title message")
    parser.add_argument("--branch", default="session/auto", help="Branch name")
    parser.add_argument("--base", default="main", help="Base branch for the PR")
    parser.add_argument("--body", default="", help="Optional PR body")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually run git and GitHub operations (default is dry-run)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    if not _is_git_repo(repo_root):
        print(f"[github_pr] ERROR: {repo_root} is not a git repository.")
        return 1
    current = _current_branch(repo_root)

    if args.live and current == args.base:
        print(f"[github_pr] ERROR: refusing to commit directly to {args.base}; create a feature branch first.")
        return 1

    if not _origin_exists(repo_root):
        print("[github_pr] ERROR: no 'origin' remote configured.")
        return 1

    if not _has_changes(repo_root):
        print("[github_pr] No changes to commit.")
        if args.live:
            return 0
        print("[github_pr] Dry-run complete; no actions taken.")
        return 0

    if not args.live:
        print(f"[github_pr] DRY-RUN: would create branch={args.branch!r}, commit message={args.message!r}, push, and open PR against {args.base} for {repo_root}")
        print("[github_pr] Re-run with --live to execute.")
        return 0

    try:
        _run(["git", "checkout", "-b", args.branch], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        if "already exists" not in exc.stderr:
            print(f"[github_pr] ERROR: failed to create branch: {exc.stderr}")
            return 1
        _run(["git", "checkout", args.branch], cwd=repo_root)

    try:
        _run(["git", "add", "-A"], cwd=repo_root)
        _run(["git", "commit", "-m", args.message], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        print(f"[github_pr] ERROR: commit failed: {exc.stderr}")
        return 1

    try:
        _run(["git", "push", "-u", "origin", args.branch], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        print(f"[github_pr] ERROR: push failed: {exc.stderr}")
        return 1

    try:
        pr_result = _run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                args.message,
                "--body",
                args.body or args.message,
                "--base",
                args.base,
            ],
            cwd=repo_root,
        )
        print(pr_result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        print(f"[github_pr] ERROR: PR creation failed: {exc.stderr}")
        return 1

    print(f"[github_pr] SUCCESS: branch {args.branch!r} pushed and PR opened against {args.base}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
