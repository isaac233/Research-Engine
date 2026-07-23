"""Summary Bank — the planner-context half of the split memory bank (#9).

WebWeaver splits its memory: verbatim spans feed the *writer* (grounded citation),
while short per-page *summaries* feed the *planner* (context to decide what to
search next without stuffing full pages into the planning prompt). Our
:class:`~research_engine.memory.evidence_bank.EvidenceBank` already holds the
verbatim half; this holds the summary half. Keeping summaries separate keeps the
ReAct planner's context small and cheap as evidence volume scales up.
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True, slots=True)
class SummaryNote:
    """A short summary of one fetched page, tagged with the objective it served."""

    url: str
    title: str
    objective: str
    summary: str


class SummaryBank:
    """Ordered per-page summaries, deduped by URL, addressable for planner context."""

    def __init__(self) -> None:
        self._notes: list[SummaryNote] = []
        self._urls: set[str] = set()

    def add(self, note: SummaryNote) -> None:
        """Store a note; the first summary for a URL wins (a page is read once)."""
        if note.url in self._urls:
            return
        self._urls.add(note.url)
        self._notes.append(note)

    def notes(self) -> list[SummaryNote]:
        return list(self._notes)

    def urls(self) -> set[str]:
        """URLs already summarised — the ReAct loop uses this to skip re-reads."""
        return set(self._urls)

    def covered_objectives(self) -> set[str]:
        """Distinct objectives that at least one summary addressed."""
        return {n.objective for n in self._notes if n.objective}

    def is_empty(self) -> bool:
        return not self._notes

    def digest(self, max_chars: int = 4000) -> str:
        """Concatenated ``title: summary`` lines for the planner prompt, capped.

        Newest notes are least likely to be dropped is *not* the goal here — the
        planner wants breadth of what's been seen, so we keep first-seen order and
        stop once the budget is hit.
        """
        lines: list[str] = []
        used = 0
        for note in self._notes:
            line = f"{note.title}: {note.summary}".strip()
            if used + len(line) + 1 > max_chars:
                break
            lines.append(line)
            used += len(line) + 1
        return "\n".join(lines)
