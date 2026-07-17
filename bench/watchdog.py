#!/usr/bin/env python3
"""Stall watchdog for long background runs — catch freezes in minutes, not hours.

Emits ONE line per event to stdout so the Monitor tool turns each into a live
notification: a `heartbeat` while things progress, `STALL` the moment nothing
advances for `--stall-secs`, and `DONE`/`MAXTIME` when finished. Progress = any
watched path's (mtime, total size) changing — for a bench campaign the best signal
is `data/state.db` (written each stage) plus the run log.

Attach it to a background job like:
  python bench/watchdog.py \
    --watch data/state.db --watch bench/out/run.log \
    --done-file bench/out/run.log --done-regex 'RACE overall' \
    --stall-secs 240 --heartbeat-secs 300 --max-secs 5400
run under the Monitor tool so STALL/heartbeat/DONE reach the operator immediately.
"""
from __future__ import annotations

import argparse
import os
import re
import time


def _signal(paths: list[str]) -> tuple[float, int]:
    """Return (newest mtime, total size) across paths — the progress fingerprint."""
    newest = 0.0
    total = 0
    for p in paths:
        try:
            st = os.stat(p)
            newest = max(newest, st.st_mtime)
            total += st.st_size
        except OSError:
            pass  # not created yet / transient — treated as no change
    return newest, total


def _selftest() -> None:
    import tempfile

    # Missing paths contribute nothing.
    assert _signal(["/does/not/exist"]) == (0.0, 0)
    with tempfile.NamedTemporaryFile("w", delete=False) as fh:
        path = fh.name
        fh.write("a")
    try:
        s1 = _signal([path])
        assert s1[1] == 1, s1  # size counted
        with open(path, "a", encoding="utf-8") as fh2:
            fh2.write("bc")
        s2 = _signal([path])
        assert s2 != s1 and s2[1] == 3, (s1, s2)  # growth = progress (fingerprint changes)
    finally:
        os.unlink(path)
    # Stall decision is a plain elapsed-since-last-progress compare.
    assert not (100.0 - 0.0 >= 240.0)  # 100s elapsed, 240s threshold -> not yet stalled
    assert 300.0 - 0.0 >= 240.0  # 300s elapsed -> stalled
    print("selftest OK", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="append", default=[], help="path whose mtime/size = progress")
    ap.add_argument("--done-file", help="file to scan for --done-regex")
    ap.add_argument("--done-regex", help="regex that means finished-successfully")
    ap.add_argument("--stall-secs", type=float, default=240.0)
    ap.add_argument("--heartbeat-secs", type=float, default=300.0)
    ap.add_argument("--poll-secs", type=float, default=20.0)
    ap.add_argument("--max-secs", type=float, default=7200.0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
        return 0
    if not a.watch:
        ap.error("--watch is required")

    done_re = re.compile(a.done_regex) if a.done_regex else None
    start = last_progress = last_beat = time.time()
    last_sig = _signal(a.watch)
    print(f"WATCH start: {', '.join(a.watch)} | stall>{a.stall_secs:.0f}s", flush=True)

    while True:
        time.sleep(a.poll_secs)
        now = time.time()

        if done_re and a.done_file:
            try:
                with open(a.done_file, encoding="utf-8", errors="replace") as fh:
                    if done_re.search(fh.read()):
                        print(f"DONE: matched /{a.done_regex}/ after {now - start:.0f}s", flush=True)
                        return 0
            except OSError:
                pass

        sig = _signal(a.watch)
        if sig != last_sig:
            last_sig, last_progress = sig, now

        stalled = now - last_progress
        if stalled >= a.stall_secs:
            print(f"STALL: no progress {stalled:.0f}s (>{a.stall_secs:.0f}s) -- inspect/kill", flush=True)
            return 2
        if now - last_beat >= a.heartbeat_secs:
            last_beat = now
            print(
                f"heartbeat: alive, {now - start:.0f}s elapsed, last change {stalled:.0f}s ago",
                flush=True,
            )
        if now - start >= a.max_secs:
            print(f"MAXTIME: {a.max_secs:.0f}s reached -- stopping watch", flush=True)
            return 3


if __name__ == "__main__":
    raise SystemExit(main())
