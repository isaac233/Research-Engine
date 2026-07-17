"""Citation parsing and normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Bound the scan: the author-year regex is CPU-bound, so catastrophic backtracking on
# a huge page can't be preempted by the extract-batch timeout (GIL-held). Real
# citations live in normal-sized text; a slice keeps the work bounded.
_MAX_CITATION_CHARS = 200_000

# Author (Year), e.g. "Doe (2020)" / "Smith and Jones (2019)". Whitespace is
# unambiguous (a single required \s+ per name, no competing \s*) and the name run is
# bounded ({0,10}); the old pattern's \s+…\s* overlap backtracked EXPONENTIALLY on a
# run of capitalized words separated by multiple spaces and hung a whole extract batch.
_AUTHOR_YEAR = re.compile(
    r"([A-Z][a-zA-Z\-]+(?:\s+(?:and\s+|et\s+al\.\s+)?[A-Z][a-zA-Z\-]+){0,10}\s*\((\d{4})\))"
)


@dataclass(frozen=True, slots=True)
class Citation:
    """A normalized citation extracted from a source."""

    raw: str
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    context: str | None = None


def extract_citations(text: str) -> list[Citation]:
    """Extract likely citation blocks from text.

    Matches:
    - Author (Year) patterns: Doe (2020)
    - [1], [2] numbered citations
    - DOI links
    """
    if len(text) > _MAX_CITATION_CHARS:
        text = text[:_MAX_CITATION_CHARS]
    citations: list[Citation] = []

    # Author (Year)
    for match in _AUTHOR_YEAR.finditer(text):
        raw = match.group(0)
        authors = [a.strip() for a in re.split(r"\s+(?:and|et\s+al\.)\s*", match.group(1).split("(")[0]) if a.strip()]
        year = int(match.group(2))
        citations.append(Citation(raw=raw, authors=authors, year=year, context=_context(text, match)))

    # Numbered citations [1], [2]
    for match in re.finditer(r"\[(\d{1,3})\]", text):
        raw = match.group(0)
        citations.append(Citation(raw=raw, year=None, context=_context(text, match)))

    # DOI
    for match in re.finditer(r"10\.\d{4,9}/[-._;()/:\wA-Za-z0-9]+", text):
        raw = match.group(0)
        citations.append(Citation(raw=raw, doi=raw, context=_context(text, match)))

    return citations


def _context(text: str, match: re.Match[str], window: int = 120) -> str:
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return text[start:end].replace("\n", " ").strip()


def normalize_doi(doi: str) -> str:
    """Return a clean DOI without leading https://doi.org/."""
    return doi.lower().strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def citations_to_dict(citations: list[Citation]) -> list[dict[str, Any]]:
    return [
        {
            "raw": c.raw,
            "title": c.title,
            "authors": c.authors,
            "year": c.year,
            "doi": c.doi,
            "url": c.url,
            "context": c.context,
        }
        for c in citations
    ]
