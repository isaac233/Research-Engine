"""Verify and pull the Research Engine model lanes via Ollama.

Reads ``config/model_lanes.yaml``, normalizes tags, checks what is already
installed, and (unless ``--dry-run``) pulls each requested lane tag. Records the
outcome per lane to ``data/model_pull_report.json`` so the rest of the engine
can degrade a missing/speculative tag to its installed fallback instead of
hardcoding a tag that may 404.

Usage:
    python scripts/pull_models.py --dry-run      # resolve tags, no pulls
    python scripts/pull_models.py                # pull all enabled lanes
    python scripts/pull_models.py --only deep    # pull one lane
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LANES_PATH = REPO_ROOT / "config" / "model_lanes.yaml"
REPORT_PATH = REPO_ROOT / "data" / "model_pull_report.json"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
PULL_TIMEOUT_S = 3600  # large GGUF pulls can be slow


@dataclass(frozen=True)
class PullResult:
    lane: str
    requested_tag: str
    resolved_tag: str
    pulled: bool
    used_fallback: bool
    installed_before: bool
    error: str | None = None


@dataclass
class Report:
    installed: list[str] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)


def normalize_hf_tag(raw: str) -> str:
    """Fix malformed Hugging Face tags. ``.co/x`` -> ``hf.co/x``; others pass through."""
    tag = raw.strip()
    if tag.startswith(".co/"):
        return "hf.co/" + tag[len(".co/") :]
    if tag.startswith("co/"):
        return "hf.co/" + tag[len("co/") :]
    return tag


def verify_installed() -> set[str]:
    """Return the set of installed Ollama model names, or empty set if unreachable."""
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=10) as resp:  # noqa: S310 (local only)
            data = json.load(resp)
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: could not reach Ollama at {OLLAMA_TAGS_URL}: {exc}", file=sys.stderr)
        return set()
    return {m.get("name", "") for m in data.get("models", [])}


def load_lanes() -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(LANES_PATH.read_text(encoding="utf-8"))
    lanes = raw.get("lanes", {}) if isinstance(raw, dict) else {}
    if not lanes:
        raise ValueError(f"No lanes found in {LANES_PATH}")
    return lanes


def pull_lane(tag: str, *, dry_run: bool) -> tuple[bool, str | None]:
    """Attempt ``ollama pull <tag>``. Return (pulled, error)."""
    if dry_run:
        return (False, None)
    try:
        proc = subprocess.run(  # noqa: S603,S607 (trusted local CLI)
            ["ollama", "pull", tag],
            capture_output=True,
            text=True,
            timeout=PULL_TIMEOUT_S,
        )
    except FileNotFoundError:
        return (False, "ollama CLI not found on PATH")
    except subprocess.TimeoutExpired:
        return (False, f"pull timed out after {PULL_TIMEOUT_S}s")
    if proc.returncode == 0:
        return (True, None)
    return (False, (proc.stderr or proc.stdout or "unknown error").strip()[:300])


def resolve_lane(
    name: str, lane: dict[str, Any], installed: set[str], *, dry_run: bool
) -> PullResult:
    requested = normalize_hf_tag(str(lane.get("tag", "")))
    fallback = str(lane.get("fallback", ""))

    if requested in installed:
        return PullResult(name, requested, requested, True, False, True)

    if dry_run:
        # Cannot know if a pull would succeed; report the resolution that WOULD
        # apply: requested tag (pull attempt) unless only the fallback is installed.
        if fallback and fallback in installed:
            return PullResult(name, requested, fallback, False, True, False, "dry-run: fallback installed")
        return PullResult(name, requested, requested, False, False, False, "dry-run: would attempt pull")

    pulled, error = pull_lane(requested, dry_run=dry_run)
    if pulled:
        return PullResult(name, requested, requested, pulled, False, False, error)

    # Requested tag failed: degrade to fallback.
    if fallback and fallback in installed:
        return PullResult(name, requested, fallback, False, True, False, error)
    if fallback:
        fb_pulled, fb_error = pull_lane(fallback, dry_run=dry_run)
        return PullResult(
            name, requested, fallback, fb_pulled, True, False, error or fb_error
        )
    return PullResult(name, requested, requested, False, False, False, error)


def build_report(results: list[PullResult], installed: set[str]) -> Report:
    return Report(
        installed=sorted(installed),
        results=[
            {
                "lane": r.lane,
                "requested_tag": r.requested_tag,
                "resolved_tag": r.resolved_tag,
                "pulled": r.pulled,
                "used_fallback": r.used_fallback,
                "installed_before": r.installed_before,
                "error": r.error,
            }
            for r in results
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify/pull Research Engine model lanes.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve tags, do not pull.")
    parser.add_argument("--only", type=str, default=None, help="Pull a single lane by name.")
    args = parser.parse_args(argv)

    lanes = load_lanes()
    if args.only:
        if args.only not in lanes:
            print(f"ERROR: unknown lane {args.only!r}; have {sorted(lanes)}", file=sys.stderr)
            return 2
        lanes = {args.only: lanes[args.only]}

    installed = verify_installed()
    results: list[PullResult] = []
    for name, lane in lanes.items():
        if not lane.get("enabled", True):
            continue
        result = resolve_lane(name, lane, installed, dry_run=args.dry_run)
        results.append(result)
        status = (
            "installed" if result.installed_before
            else "pulled" if result.pulled
            else f"FALLBACK->{result.resolved_tag}" if result.used_fallback
            else "MISSING"
        )
        print(f"  {name:10s} {result.requested_tag:60s} -> {status}")
        if result.error:
            print(f"             note: {result.error}", file=sys.stderr)

    report = build_report(results, installed)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report.__dict__, indent=2), encoding="utf-8")
    print(f"\nReport written to {REPORT_PATH}")

    usable = [r for r in results if r.installed_before or r.pulled or r.used_fallback]
    if not usable:
        print("ERROR: no usable lane resolved (Ollama down?).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
