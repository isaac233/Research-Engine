"""End-of-session ritual: cleanup, update HANDOFF, commit, push, open PR.

Defaults to a dry-run preview. Use ``--live`` to perform real git/GitHub ops.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

from research_engine.cleanup.janitor import CleanupJanitor
from research_engine.config import EngineConfig

DEFAULT_COMMIT_MESSAGE = "chore: end-of-session ritual"
DEFAULT_BRANCH = "session/auto"
DEFAULT_BASE = "main"


def _load_github_pr() -> Any:
    """Load the sibling ``github_pr.py`` module without requiring a package."""
    script_path = Path(__file__).resolve().parent / "github_pr.py"
    spec = importlib.util.spec_from_file_location("github_pr", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load github_pr from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").is_dir()


def _current_branch(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _has_changes(project_root: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def _update_handoff(project_root: Path) -> Path:
    handoff_path = project_root / "HANDOFF.md"
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    block = (
        f"\n\n## End-of-session ritual — {timestamp}\n"
        "- Triggered by `scripts/end_session.py`\n"
        "- Status: cleanup, tests, commit, and PR preparation completed.\n"
    )
    if handoff_path.exists():
        existing = handoff_path.read_text(encoding="utf-8")
        handoff_path.write_text(existing + block, encoding="utf-8")
    else:
        handoff_path.write_text("# HANDOFF" + block, encoding="utf-8")
    return handoff_path


def _run_tests(project_root: Path) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def main(argv: list[str] | None = None, *, project_root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="End-of-session ritual.")
    parser.add_argument(
        "--message",
        default=DEFAULT_COMMIT_MESSAGE,
        help="Commit/PR title message",
    )
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch name for the PR")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Base branch for the PR")
    parser.add_argument("--body", default="", help="Optional PR body")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually run cleanup, tests, git, and GitHub ops (default is dry-run)",
    )
    parser.add_argument(
        "--allow-main",
        action="store_true",
        help="Allow running on the base branch (dangerous)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the test run step",
    )
    args = parser.parse_args(argv)

    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    project_root = Path(project_root)

    if not _is_git_repo(project_root):
        print(f"[end_session] ERROR: {project_root} is not a git repository.")
        return 1

    try:
        current_branch = _current_branch(project_root)
    except subprocess.CalledProcessError as exc:
        print(f"[end_session] ERROR: failed to detect current branch: {exc}")
        return 1

    if current_branch == args.base and not args.allow_main:
        print(
            f"[end_session] ERROR: refusing to run on {args.base}; "
            "create a feature branch first or use --allow-main."
        )
        return 1

    config = EngineConfig(project_root=project_root)

    if args.live:
        janitor = CleanupJanitor(
            state_db_path=config.state_db_path(),
            engine_data_dir=config.engine_data_dir,
            project_root=config.project_root,
        )
        cleanup = janitor.clean()
        if not cleanup.ok:
            print(f"[end_session] ERROR: cleanup failed: {cleanup.error}")
            return 1
        print(f"[end_session] cleanup ok: {cleanup.meta}")
    else:
        print(
            f"[end_session] DRY-RUN: would run cleanup for {config.engine_data_dir} "
            f"and vacuum {config.state_db_path()}"
        )

    if args.live:
        handoff_path = _update_handoff(project_root)
        print(f"[end_session] updated {handoff_path}")
    else:
        print(
            f"[end_session] DRY-RUN: would append an end-of-session entry to "
            f"{project_root / 'HANDOFF.md'}"
        )

    if not args.skip_tests:
        if args.live:
            if not _run_tests(project_root):
                print("[end_session] ERROR: tests failed")
                return 1
            print("[end_session] tests passed")
        else:
            print("[end_session] DRY-RUN: would run pytest -q")

    if not _has_changes(project_root):
        print("[end_session] No changes to commit.")
        return 0

    if not args.live:
        print(
            f"[end_session] DRY-RUN: would open PR {args.branch!r} against "
            f"{args.base} from branch {current_branch!r}"
        )
        return 0

    try:
        github_pr = _load_github_pr()
    except ImportError as exc:
        print(f"[end_session] ERROR: could not load github_pr: {exc}")
        return 1

    return int(
        github_pr.main(
            [
                "--message",
                args.message,
                "--branch",
                args.branch,
                "--base",
                args.base,
                "--body",
                args.body,
                "--live",
            ]
        )
    )


if __name__ == "__main__":
    sys.exit(main())
