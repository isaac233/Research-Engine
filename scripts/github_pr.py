"""Create branch, commit, push, and open a GitHub pull request.

This is a Phase 0 stub. Do not run for real until Phase 9 wiring is complete.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Open a GitHub PR for the current session.")
    parser.add_argument("--message", required=True, help="Commit/PR title message")
    parser.add_argument("--branch", default="session/auto", help="Branch name")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    print(f"[github_pr] STUB: would create branch={args.branch}, commit message={args.message!r}, push, and open PR for {repo_root}")
    print("[github_pr] Not yet wired. See docs/plan/master_plan.md Phase 9.")


if __name__ == "__main__":
    main()
