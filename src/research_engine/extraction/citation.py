"""Citation parsing and normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


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
    citations: list[Citation] = []

    # Author (Year)
    for match in re.finditer(
        r"([A-Z][a-zA-Z\-]+(?:\s+(?:and|et\s+al\.)?\s*[A-Z][a-zA-Z\-]+)*\s*\((\d{4})\))",
        text,
    ):
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
