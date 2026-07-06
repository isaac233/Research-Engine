"""Launch helper for the Research Engine CLI.

Delegates to the real entry point in `src/research_engine/main.py`.
"""

from __future__ import annotations

from research_engine.main import cli

if __name__ == "__main__":
    cli()

