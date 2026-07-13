"""Post-synthesis citation grounding.

The synthesis model writes ``[n]``-cited prose, but nothing guarantees each
cited sentence is actually backed by source ``n``. Paraphrase drift, composite
sentences, and mis-cites all inflate the delivered citation count while lowering
its trustworthiness (the FACT metric re-fetches each cited URL and checks
support). This module strips ``[n]`` markers whose sentence is not supported by
source ``n``'s available text, so every surviving citation re-verifies.

Default support test is deterministic lexical overlap (no LLM call): a sentence
is supported when it shares enough content tokens with the source, or any
numeric token in the sentence appears in the source. Callers can inject a
stronger semantic ``supports`` callable.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

_CITATION = re.compile(r"\[(\d+)\]")
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?|[0-9]+%?")
_NUMERIC = re.compile(r"\d")
# Short function words carry no grounding signal; ignore them in overlap.
_STOP = frozenset(
    "the a an of to in for and or but with on at by is are was were be been as "
    "that this these those it its from into than then so such not no can will "
    "may would could each per one two more most also which who what when where".split()
)

SupportsFn = Callable[[str, str], bool]

# Characters of preceding text treated as the claim a citation supports.
_CLAIM_WINDOW = 240


def _source_text(source: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("methodology", "data_summary", "results_summary", "conclusions", "summary"):
        value = str(source.get(key, "")).strip()
        if value:
            parts.append(value)
    for claim in source.get("claims", []) or []:
        parts.append(str(claim.get("claim", "")))
        parts.append(str(claim.get("evidence", "")))
    return " ".join(parts)


def _content_tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1}


def _lexical_supports(sentence: str, source_text: str, min_overlap: float) -> bool:
    sent_tokens = _content_tokens(sentence)
    if not sent_tokens:
        return False
    src_tokens = _content_tokens(source_text)
    if not src_tokens:
        return False
    # Any concrete number in the claim must appear in the source — a mismatched
    # figure is the classic FACT failure, so a shared number is strong evidence.
    numeric = {t for t in sent_tokens if _NUMERIC.search(t)}
    if numeric & src_tokens:
        return True
    if numeric and not (numeric & src_tokens):
        return False
    overlap = len(sent_tokens & src_tokens) / len(sent_tokens)
    return overlap >= min_overlap


def _split_body_and_references(brief: str) -> tuple[str, str]:
    marker = "\n## References"
    idx = brief.find(marker)
    if idx == -1:
        return brief, ""
    return brief[:idx], brief[idx:]


def ground_citations(
    brief: str,
    sources: list[dict[str, Any]],
    *,
    min_overlap: float = 0.2,
    supports: SupportsFn | None = None,
    source_text_fn: Callable[[dict[str, Any]], str] | None = None,
) -> str:
    """Strip ``[n]`` citations not supported by source ``n``; leave prose intact.

    ``source_text_fn`` overrides where a source's grounding text comes from —
    pass a re-fetch of the citable URL to keep only citations that survive the
    same fetch the FACT metric performs. Defaults to the engine's extract.
    The References section (appended deterministically) is never modified.
    """
    if not brief or not sources:
        return brief
    body, references = _split_body_and_references(brief)
    text_of = source_text_fn or _source_text
    source_texts = [text_of(s) for s in sources]

    def supported(claim: str, idx: int) -> bool:
        if idx < 1 or idx > len(sources):
            return False
        text = source_texts[idx - 1]
        if supports is not None:
            return supports(claim, text)
        return _lexical_supports(claim, text, min_overlap)

    # A citation sits after the claim it supports; judge each against the clause
    # of text preceding it. Position-based removal handles repeated [n] with
    # different verdicts and never splits decimals mid-number.
    keep: list[tuple[int, int]] = []  # spans to drop
    for m in _CITATION.finditer(body):
        claim = body[max(0, m.start() - _CLAIM_WINDOW) : m.start()]
        if not supported(claim, int(m.group(1))):
            keep.append((m.start(), m.end()))
    if keep:
        out: list[str] = []
        cursor = 0
        for start, end in keep:
            out.append(body[cursor:start])
            cursor = end
        out.append(body[cursor:])
        body = "".join(out)
    body = re.sub(r"[ \t]{2,}", " ", body)
    return body + references
