"""Parse router markdown files into structured keyword tables and learned log."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RouteItem:
    id: str
    subsystem: str
    signal: str
    load: str
    tactic: str
    prov: str
    hits: int
    verified: str
    status: str


@dataclass
class RouterFile:
    path: Path
    keyword_table: dict[str, list[str]] = field(default_factory=dict)
    learned_items: list[RouteItem] = field(default_factory=list)


def parse_routers(router_dir: Path) -> dict[str, RouterFile]:
    """Parse every `*-router.md` under `router_dir`."""
    result: dict[str, RouterFile] = {}
    if not router_dir.exists():
        return result
    for p in router_dir.glob("*-router.md"):
        rf = RouterFile(path=p)
        text = p.read_text(encoding="utf-8")
        # Parse only tables whose header promises a "Load" column.
        in_table = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("| Signal"):
                in_table = "load" in s.lower()
                continue
            if in_table and s.startswith("| ") and "|" in s[2:]:
                parts = [c.strip() for c in s.split("|")]
                parts = [c for c in parts if c]
                if len(parts) >= 2 and not parts[0].lower().startswith("signal"):
                    rf.keyword_table[parts[0].lower()] = [s.strip() for s in parts[1].split(",")]
            elif in_table and not s.startswith("|"):
                in_table = False
        result[p.stem] = rf
    return result


def parse_learned_log(log_path: Path) -> list[RouteItem]:
    """Parse `.claude/research-engine-routes.md` learned items."""
    items: list[RouteItem] = []
    if not log_path.exists():
        return items
    for line in log_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(R\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|", line)
        if m:
            items.append(
                RouteItem(
                    id=m.group(1),
                    subsystem=m.group(2).strip(),
                    signal=m.group(3).strip(),
                    load=m.group(4).strip(),
                    tactic=m.group(5).strip(),
                    prov=m.group(6).strip(),
                    hits=int(m.group(7)),
                    verified=m.group(8).strip(),
                    status=m.group(9).strip(),
                )
            )
    return items


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    routers = parse_routers(base / "agents")
    learned = parse_learned_log(base / "research-engine-routes.md")
    assert "research-engine-router" in routers
    assert any(item.id == "R001" for item in learned)
    print("table_parser self-check: OK")


if __name__ == "__main__":
    main()
