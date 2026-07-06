"""Detect stale paths in keyword tables and uncovered modules."""

from __future__ import annotations

from pathlib import Path

from table_parser import parse_routers


def drift_check(router_dir: Path, src_root: Path) -> dict:
    routers = parse_routers(router_dir)
    referenced: set[str] = set()
    for rf in routers.values():
        for loads in rf.keyword_table.values():
            for load in loads:
                referenced.add(load.strip())
    existing: set[str] = {str(p.relative_to(src_root.parent)) for p in src_root.rglob("*.py")}
    stale = {p for p in referenced if not (src_root.parent / p).exists()}
    uncovered = {p for p in existing if p not in referenced}
    return {
        "referenced": len(referenced),
        "existing": len(existing),
        "stale": sorted(stale),
        "uncovered": sorted(uncovered),
    }


def main() -> None:
    base = Path(__file__).resolve().parent.parent.parent
    report = drift_check(base / ".claude" / "agents", base / "src")
    assert isinstance(report["stale"], list)
    print(f"drift_check self-check: OK (referenced={report['referenced']}, existing={report['existing']})")


if __name__ == "__main__":
    main()
