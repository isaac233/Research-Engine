"""Launch helper for the Research Engine CLI.

This is a Phase 0 stub. The real entry point will be `src/research_engine/main.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    print("[launch] Research Engine launcher stub.")
    print(f"[launch] Project root: {Path(__file__).resolve().parent.parent}")
    print("[launch] Use: research-engine run \"<query>\" (when implemented).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
