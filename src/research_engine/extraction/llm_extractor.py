"""LLM-driven extraction of methods/data/results/conclusions from full text.

A local model reads the resolved full text and returns replication-grade
structured fields plus claims with verbatim evidence. This replaces the
abstract-level regex path when full text is available.

Defines its own lightweight ``LLMClaim`` so this module does not import
``structured`` (which imports this module) — one-way dependency.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from research_engine.extraction.chunker import Chunker
from research_engine.extraction.prompts import EXTRACTION_SYSTEM_V1, EXTRACTION_USER_V1
from research_engine.llm.provider import LLMProvider, Message

_SECTION_KEYS = ("methodology", "data_summary", "results_summary", "conclusions", "replication_notes")


@dataclass(frozen=True, slots=True)
class LLMClaim:
    claim: str
    evidence: str
    section: str
    confidence: str


@dataclass(frozen=True, slots=True)
class LLMExtraction:
    methodology: str
    data_summary: str
    results_summary: str
    conclusions: str
    replication_notes: str
    claims: list[LLMClaim]
    raw_response: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls, raw: str = "", error: str | None = None) -> LLMExtraction:
        meta: dict[str, Any] = {}
        if error:
            meta["error"] = error
        return cls("", "", "", "", "", [], raw, meta)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


class LLMSectionExtractor:
    """Extract structured sections + evidenced claims from full text via an LLM."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str | None = None,
        max_chars: int = 24000,
        chunker: Chunker | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
    ) -> None:
        self.provider = provider
        self.model = model
        self.max_chars = max_chars
        self.chunker = chunker or Chunker(max_chars=max_chars)
        self.temperature = temperature
        self.max_tokens = max_tokens

    def extract_sections(self, title: str, abstract: str, full_text: str) -> LLMExtraction:
        """Return a consolidated extraction, chunking long text with a deterministic merge."""
        if not full_text.strip():
            return LLMExtraction.empty(error="empty full text")

        chunks = self.chunker.split(full_text)
        partials = [self._extract_one(title, abstract, chunk) for chunk in chunks]
        merged = self._merge(partials) if len(partials) > 1 else partials[0]
        # Anti-hallucination: keep only claims whose evidence is verbatim in the text.
        verified, dropped = self._verify_claims(merged.claims, full_text)
        meta = dict(merged.meta)
        meta["chunks"] = len(chunks)
        meta["unverified_dropped"] = dropped
        return LLMExtraction(
            methodology=merged.methodology,
            data_summary=merged.data_summary,
            results_summary=merged.results_summary,
            conclusions=merged.conclusions,
            replication_notes=merged.replication_notes,
            claims=verified,
            raw_response=merged.raw_response,
            meta=meta,
        )

    def _extract_one(self, title: str, abstract: str, text: str) -> LLMExtraction:
        messages = [
            Message(role="system", content=EXTRACTION_SYSTEM_V1),
            Message(
                role="user",
                content=EXTRACTION_USER_V1.format(
                    title=title[:300], abstract=abstract[:1200], text=text
                ),
            ),
        ]
        try:
            response = self.provider.complete(
                messages,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - provider/network failure must not crash extraction
            return LLMExtraction.empty(error=f"{type(exc).__name__}: {exc}")
        return self._parse(response)

    @staticmethod
    def _parse(response: str) -> LLMExtraction:
        obj = _extract_json_object(response)
        if obj is None:
            return LLMExtraction.empty(raw=response, error="no JSON object in response")

        def _field(key: str) -> str:
            value = obj.get(key, "")
            text = str(value).strip()
            return "" if text.upper() == "ABSENT" else text

        claims: list[LLMClaim] = []
        for raw_claim in obj.get("claims", []) or []:
            if not isinstance(raw_claim, dict):
                continue
            claim = str(raw_claim.get("claim", "")).strip()
            evidence = str(raw_claim.get("evidence", "")).strip()
            if not claim or not evidence:
                continue
            claims.append(
                LLMClaim(
                    claim=claim,
                    evidence=evidence,
                    section=str(raw_claim.get("section", "")).strip() or "unknown",
                    confidence=str(raw_claim.get("confidence", "medium")).strip().lower(),
                )
            )
        return LLMExtraction(
            methodology=_field("methodology"),
            data_summary=_field("data_summary"),
            results_summary=_field("results_summary"),
            conclusions=_field("conclusions"),
            replication_notes=_field("replication_notes"),
            claims=claims,
            raw_response=response,
        )

    @staticmethod
    def _merge(partials: list[LLMExtraction]) -> LLMExtraction:
        """Deterministically merge chunk extractions (no extra LLM call)."""
        def _join(key: str) -> str:
            seen: list[str] = []
            for p in partials:
                value = getattr(p, key).strip()
                if value and value not in seen:
                    seen.append(value)
            return "\n\n".join(seen)

        claims: list[LLMClaim] = []
        seen_claims: set[str] = set()
        for p in partials:
            for c in p.claims:
                key = _normalize(c.claim)
                if key not in seen_claims:
                    seen_claims.add(key)
                    claims.append(c)
        return LLMExtraction(
            methodology=_join("methodology"),
            data_summary=_join("data_summary"),
            results_summary=_join("results_summary"),
            conclusions=_join("conclusions"),
            replication_notes=_join("replication_notes"),
            claims=claims,
            raw_response="",
            meta={"merged_from": len(partials)},
        )

    @staticmethod
    def _verify_claims(claims: list[LLMClaim], full_text: str) -> tuple[list[LLMClaim], int]:
        haystack = _normalize(full_text)
        kept: list[LLMClaim] = []
        dropped = 0
        for c in claims:
            if _normalize(c.evidence) in haystack:
                kept.append(c)
            else:
                dropped += 1
        return kept, dropped


def _extract_json_object(response: str) -> dict[str, Any] | None:
    """Find and parse the first balanced JSON object in a model response."""
    text = response.strip()
    # Strip common code fences.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None
