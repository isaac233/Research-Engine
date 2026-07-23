"""dev_infra — one command to check (and best-effort start) the local services the
bench depends on, so a "dependency is down" is a one-liner, never a stall.

  python scripts/dev_infra.py check   # probe every dep; print status + the fix command
  python scripts/dev_infra.py up      # best-effort start the ones we own (bridge, shim)

Services:
  ollama :11434  local model server        EXTERNAL — start the Ollama tray; never force-kill
                                            (see memory/ollama-recovery-discipline).
  bridge :11444  kimi cloud judge (MITM-tolerant Ollama Cloud bridge)
                 -> python -m ollama_cloud_bridge --port 11444
  serp   :8080   SearXNG-compatible search shim (firecrawl key from ~/.claude.json, ddgs fallback)
                 -> python scripts/serp_shim.py

Reflex (memory/heuristics.md 2026-07-22): a dep being down is SOLVE-FIRST, not a blocker.
These shims exist so it's a one-command fix — build/stand-up before you ever say "blocked".

In a Claude session, prefer starting a down service via the harness background tool (it
persists across tool calls); `up` here detaches best-effort for standalone use.
"""
from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# (name, probe_url, external, start_argv, hint)
SERVICES = [
    ("ollama", "http://localhost:11434/api/tags", True, None,
     "start the Ollama tray (external); do NOT force-kill it"),
    ("bridge", "http://localhost:11444/api/tags", False,
     [sys.executable, "-m", "ollama_cloud_bridge", "--port", "11444"],
     "python -m ollama_cloud_bridge --port 11444"),
    ("serp", "http://localhost:8080/", False,
     [sys.executable, str(REPO_ROOT / "scripts" / "serp_shim.py")],
     "python scripts/serp_shim.py"),
]


def _probe(url: str, timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (localhost only)
            return 200 <= resp.status < 500
    except Exception:  # noqa: BLE001
        return False


def _start_detached(argv: list[str], log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    creation = 0
    if sys.platform == "win32":
        creation = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    with log.open("ab") as fh:
        subprocess.Popen(  # noqa: S603
            argv, cwd=str(REPO_ROOT), stdout=fh, stderr=fh,
            stdin=subprocess.DEVNULL, creationflags=creation, close_fds=True,
        )


def check() -> int:
    down = 0
    print(f"{'service':8} {'port':6} {'status':6}  fix")
    for name, url, external, _argv, hint in SERVICES:
        port = url.split(":")[2].split("/")[0]
        up = _probe(url)
        if not up:
            down += 1
        status = "UP" if up else "DOWN"
        fix = "" if up else (f"-> {hint}" + ("  [EXTERNAL]" if external else ""))
        print(f"{name:8} {port:6} {status:6}  {fix}")
    return 0 if down == 0 else 1


def up() -> int:
    import time

    for name, url, external, argv, hint in SERVICES:
        if _probe(url):
            print(f"{name}: already up")
            continue
        if external or argv is None:
            print(f"{name}: DOWN and external — {hint}")
            continue
        print(f"{name}: starting -> {hint}")
        _start_detached(argv, REPO_ROOT / "bench" / "out" / f"{name}.log")
    time.sleep(6)
    return check()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    raise SystemExit(up() if cmd == "up" else check())
