"""Research outline — the structural keystone of the Planner/Writer rebuild.

The Planner builds an ``Outline`` (ordered sections, each with an intent and the
evidence IDs that support it) from the query + the Evidence Bank. The Writer then
walks the outline section by section, retrieving ONLY that section's evidence and
writing it — which is what lets a local model produce a comprehensive, coherent,
citation-accurate report instead of a flat pile of restated spans.
"""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True, slots=True)
class OutlineSection:
    """One report section: a heading, what it should cover, and its evidence."""

    title: str
    intent: str
    evidence_ids: tuple[str, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Outline:
    """An ordered set of sections citing evidence-bank IDs."""

    sections: tuple[OutlineSection, ...]

    def evidence_ids(self) -> tuple[str, ...]:
        """All cited evidence IDs across sections, unique, first-seen order."""
        seen: dict[str, None] = {}
        for section in self.sections:
            for eid in section.evidence_ids:
                seen.setdefault(eid, None)
        return tuple(seen)

    def pruned(self, known_ids: set[str]) -> Outline:
        """Drop evidence IDs not in ``known_ids`` (the model may hallucinate IDs),
        then drop any section left with no evidence (can't be written grounded)."""
        kept: list[OutlineSection] = []
        for section in self.sections:
            ids = tuple(e for e in section.evidence_ids if e in known_ids)
            if ids:
                kept.append(dataclasses.replace(section, evidence_ids=ids))
        return Outline(sections=tuple(kept))

    def partitioned(self) -> Outline:
        """Assign each evidence id to exactly ONE section (first-seen wins), then drop
        any section left empty.

        Section-locked writing (ADORE, W3): with disjoint admissible sets, a section can
        only cite the spans it was given, so a thin bank can't be over-cited across many
        sections. The default outline is untouched; this is applied only behind the flag.
        """
        used: set[str] = set()
        kept: list[OutlineSection] = []
        for section in self.sections:
            ids = tuple(e for e in section.evidence_ids if e not in used)
            used.update(ids)
            if ids:
                kept.append(dataclasses.replace(section, evidence_ids=ids))
        return Outline(sections=tuple(kept))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": [
                {"title": s.title, "intent": s.intent, "evidence_ids": list(s.evidence_ids)}
                for s in self.sections
            ]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Outline:
        sections = tuple(
            OutlineSection(
                title=str(s.get("title", "")),
                intent=str(s.get("intent", "")),
                evidence_ids=tuple(str(e) for e in (s.get("evidence_ids") or [])),
            )
            for s in (data.get("sections") or [])
        )
        return cls(sections=sections)
