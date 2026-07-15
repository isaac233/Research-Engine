"""P-Cite post-hoc citation correction (#10, CiteFix — arXiv:2504.15629).

The research-backed FACT lever. Our writer generates prose + inline ``[eN]`` cites
in ONE pass (G-Cite); when it paraphrases a span the cite no longer verifies against
the page, so FACT stalls (~53%). The remedy (2509.21557: "P-Cite-first") is a
SEPARATE pass that, for each sentence, re-points its citations to the
best-*supporting* evidence span and drops the unsupportable — CiteFix's
"correction, not deletion" applied against the trusted Evidence Bank.

Crucially we match against the BANK SPAN (a verbatim substring of the cited page),
NOT a re-fetched page — the earlier re-fetch verifier failed on boilerplate
(HANDOFF). A citation re-pointed to a span whose terms cover the sentence therefore
verifies by construction when the FACT metric re-fetches that span's URL.

Matching is lexical (content-term overlap) — deterministic, no extra model call.
"""

from __future__ import annotations

import re

from research_engine.memory.evidence_bank import EvidenceBank, _terms

_CITATION = re.compile(r"\[(e\d+)\]")
# Split on sentence terminators (keeping them) and blank-line/newline runs, so
# prose structure and the References block survive untouched.
_SPLIT = re.compile(r"([.!?]+[)\]\"']*\s+|\n+)")

# A cited span "supports" a sentence when it shares at least this many content terms.
_MIN_SUPPORT_TERMS = 3
# Re-point to the best span only when it also covers this fraction of the sentence's
# content terms — guards against re-pointing to an off-topic span sharing a few words.
_MIN_REPOINT_RATIO = 0.34


def fix_citations(
    brief: str,
    bank: EvidenceBank,
    *,
    min_terms: int = _MIN_SUPPORT_TERMS,
    min_ratio: float = _MIN_REPOINT_RATIO,
) -> str:
    """Re-point each sentence's ``[eN]`` to its best-supporting bank span; drop the rest.

    The ``## References`` section (if any) is left verbatim.
    """
    if not brief:
        return brief
    marker = "\n## References"
    idx = brief.find(marker)
    body, references = (brief[:idx], brief[idx:]) if idx != -1 else (brief, "")

    span_terms = {s.id: _terms(s.text) for s in bank.spans()}

    def supports(span_id: str, sent_terms: set[str]) -> bool:
        st = span_terms.get(span_id)
        return st is not None and len(sent_terms & st) >= min_terms

    def best(sent_terms: set[str]) -> tuple[str | None, int]:
        best_id, best_ov = None, 0
        for sid, st in span_terms.items():
            ov = len(sent_terms & st)
            if ov > best_ov:
                best_id, best_ov = sid, ov
        return best_id, best_ov

    def fix_part(part: str) -> str:
        if not _CITATION.search(part):
            return part
        cited = list(dict.fromkeys(_CITATION.findall(part)))
        sent_terms = _terms(_CITATION.sub("", part))
        if not sent_terms:
            return _CITATION.sub("", part).rstrip()
        kept = [c for c in cited if supports(c, sent_terms)]
        if not kept:
            best_id, best_ov = best(sent_terms)
            if best_id and best_ov >= min_terms and best_ov / len(sent_terms) >= min_ratio:
                kept = [best_id]
        stripped = _CITATION.sub("", part).rstrip()
        return stripped + ("".join(f"[{c}]" for c in kept) if kept else "")

    parts = _SPLIT.split(body)
    # _SPLIT.split alternates: text, delimiter, text, delimiter, ...
    rebuilt = "".join(
        fix_part(p) if i % 2 == 0 else p for i, p in enumerate(parts)
    )
    return rebuilt + references
