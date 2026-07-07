"""Citation snowballing: forward and backward citation expansion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.discovery.dedup import DedupEngine
from research_engine.discovery.schema import Paper
from research_engine.discovery.sources.base import SourceAdapter


@dataclass(frozen=True, slots=True)
class SnowballResult:
    """Result of a citation snowball run."""

    seed: Paper
    papers: list[Paper] = field(default_factory=list)
    depth: int = 1
    meta: dict[str, Any] = field(default_factory=dict)


class SnowballEngine:
    """Expand a seed paper to cited/citing papers up to a configurable depth."""

    def __init__(
        self,
        adapter: SourceAdapter,
        dedup: DedupEngine | None = None,
        max_depth: int = 1,
    ) -> None:
        self.adapter = adapter
        self.dedup = dedup or DedupEngine()
        self.max_depth = max_depth

    def expand(self, seed: Paper) -> SnowballResult:
        """Expand from seed paper to related papers via citations."""
        if self.max_depth < 1:
            return SnowballResult(seed=seed, papers=[], depth=0)

        seen: set[str] = {seed.key}
        frontier: list[Paper] = [seed]
        collected: list[Paper] = []
        expansions = 0

        for _depth in range(1, self.max_depth + 1):
            next_frontier: list[Paper] = []
            for paper in frontier:
                neighbors = self._neighbors(paper)
                for neighbor in neighbors:
                    if neighbor.key not in seen:
                        seen.add(neighbor.key)
                        next_frontier.append(neighbor)
                        collected.append(neighbor)
                        expansions += 1
            if not next_frontier:
                break
            frontier = next_frontier

        return SnowballResult(
            seed=seed,
            papers=collected,
            depth=self.max_depth,
            meta={"expansions": expansions, "unique_keys": len(seen)},
        )

    def _neighbors(self, paper: Paper) -> list[Paper]:
        """Resolve cited and citing paper IDs through the source adapter."""
        neighbors: list[Paper] = []
        for source_id in paper.citations_out + paper.citations_in:
            fetched = self.adapter.fetch_by_id(source_id)
            if fetched is not None:
                neighbors.append(fetched)
        return neighbors

    def health(self) -> dict[str, Any]:
        return {"ok": True, "source": self.adapter.name, "max_depth": self.max_depth}
