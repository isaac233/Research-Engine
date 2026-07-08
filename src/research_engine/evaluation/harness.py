"""Evaluation harness: score a campaign's extracted and challenged output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from research_engine.adversarial.challenge import Challenge, VerificationResult
from research_engine.extraction.structured import ExtractedSource


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Metrics and narrative summary of a campaign's output quality."""

    total_claims: int = 0
    total_sources: int = 0
    challenged_count: int = 0
    high_severity_count: int = 0
    verified_count: int = 0
    failed_verification_count: int = 0
    citation_count: int = 0
    coverage_score: float = 0.0
    quality_score: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    markdown: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class EvaluationHarness:
    """Compute verifiable quality metrics from extraction + adversarial outputs."""

    def evaluate(
        self,
        sources: list[ExtractedSource],
        challenges: list[Challenge],
        verifications: list[VerificationResult],
        query: str = "",
        expected_claims: list[str] | None = None,
    ) -> EvaluationReport:
        total_claims = sum(len(s.claims) for s in sources)
        total_sources = len(sources)
        citation_count = sum(len(s.citations) for s in sources)

        unique_challenges = {self._challenge_key(c): c for c in challenges}
        challenged_count = len(unique_challenges)
        high_severity_count = sum(
            1 for c in unique_challenges.values() if c.severity == "high"
        )

        verified_count = sum(1 for v in verifications if v.ok)
        failed_verification_count = len(verifications) - verified_count

        coverage_score = self._coverage_score(total_sources, total_claims, citation_count)
        quality_score = self._quality_score(
            total_claims,
            challenged_count,
            high_severity_count,
            failed_verification_count,
        )

        extracted_claims = [c.claim for s in sources for c in s.claims]
        precision, recall, f1_score = self._golden_answer_scores(
            extracted_claims, expected_claims or []
        )

        report = EvaluationReport(
            total_claims=total_claims,
            total_sources=total_sources,
            challenged_count=challenged_count,
            high_severity_count=high_severity_count,
            verified_count=verified_count,
            failed_verification_count=failed_verification_count,
            citation_count=citation_count,
            coverage_score=round(coverage_score, 4),
            quality_score=round(quality_score, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1_score, 4),
            meta={
                "query": query,
                "conflict_count": sum(len(s.conflicts) for s in sources),
                "expected_claim_count": len(expected_claims or []),
                "matched_claim_count": self._count_matches(extracted_claims, expected_claims or []),
            },
        )
        return report

    def _challenge_key(self, challenge: Challenge) -> tuple[str | None, int | None, str]:
        return (challenge.source_id, challenge.claim_index, challenge.kind)

    def _coverage_score(self, sources: int, claims: int, citations: int) -> float:
        """Simple coverage heuristic: at least one source + claims + citations."""
        if sources == 0:
            return 0.0
        score = 0.5
        if claims > 0:
            score += 0.25
        if citations > 0:
            score += 0.25
        return min(1.0, score)

    def _quality_score(
        self,
        claims: int,
        challenged: int,
        high_severity: int,
        failed_verification: int,
    ) -> float:
        if claims == 0:
            return 0.0
        base = 1.0
        base -= 0.2 * min(challenged / max(claims, 1), 1.0)
        base -= 0.4 * min(high_severity / max(claims, 1), 1.0)
        base -= 0.4 * min(failed_verification / max(claims, 1), 1.0)
        return max(0.0, base)

    def _golden_answer_scores(
        self,
        extracted_claims: list[str],
        expected_claims: list[str],
    ) -> tuple[float, float, float]:
        """Compute precision/recall/F1 against a golden answer set."""
        if not expected_claims:
            # No claims expected: perfect if nothing extracted, otherwise all
            # extractions are false positives.
            precision = 1.0 if not extracted_claims else 0.0
            return (precision, 1.0, precision)

        true_positives = self._count_matches(extracted_claims, expected_claims)
        precision = true_positives / len(extracted_claims) if extracted_claims else 1.0
        recall = true_positives / len(expected_claims) if expected_claims else 1.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        return (precision, recall, f1)

    def _count_matches(self, extracted_claims: list[str], expected_claims: list[str]) -> int:
        """Count one-to-one claim matches using maximum bipartite matching.

        Greedy first-fit matching can under-count when a later extracted claim
        is a better match for an already-consumed expected claim. This uses a
        simple augmenting-path (Kuhn) algorithm to find the largest one-to-one
        matching between extracted and expected claims.
        """
        normalized_extracted = [self._normalize_claim(c) for c in extracted_claims]
        normalized_expected = [self._normalize_claim(c) for c in expected_claims]

        adjacency: list[list[int]] = [[] for _ in normalized_extracted]
        for i, a in enumerate(normalized_extracted):
            for j, b in enumerate(normalized_expected):
                if self._claim_match(a, b):
                    adjacency[i].append(j)

        match_for_expected = [-1] * len(normalized_expected)

        def _augment(i: int, seen: list[bool]) -> bool:
            for j in adjacency[i]:
                if seen[j]:
                    continue
                seen[j] = True
                if match_for_expected[j] == -1 or _augment(match_for_expected[j], seen):
                    match_for_expected[j] = i
                    return True
            return False

        count = 0
        for i in range(len(normalized_extracted)):
            if _augment(i, [False] * len(normalized_expected)):
                count += 1
        return count

    # Minimum token-set Jaccard similarity for a paraphrase match.
    _MIN_TOKEN_JACCARD = 0.35

    # Small English stopword set for token-overlap paraphrase matching.
    _STOPWORDS: frozenset[str] = frozenset(
        "the a an is are was were be been being have has had do does did will would could should may might must shall can need dare ought used to of in for on with at by from as into through during before after above below between under over again also further then once here there when where why how all any both each few more most other some such no nor not only own same so than too very just and but if or because until while although though since unless whether that which who whom whose what this these those i me my myself we our ours ourselves you your yours yourself yourselves he him his himself she her hers herself it its itself they them their theirs themselves one ones".split()
    )

    # Whole-word negation markers. A mismatch here is a strong signal that
    # token overlap alone would wrongly score an opposite claim as a match.
    _NEGATION_WORDS: frozenset[str] = frozenset(
        (
            "not",
            "no",
            "never",
            "none",
            "neither",
            "nor",
            "isn't",
            "aren't",
            "wasn't",
            "weren't",
            "hasn't",
            "haven't",
            "hadn't",
            "don't",
            "doesn't",
            "didn't",
            "won't",
            "wouldn't",
            "can't",
            "cannot",
            "couldn't",
        )
    )

    # Directional antonym pairs. A claim containing the positive direction and
    # another claim containing the corresponding negative direction should not
    # be treated as a paraphrase match.
    _DIRECTION_OPPOSITES: dict[str, str] = {
        "increase": "decrease",
        "increases": "decreases",
        "increased": "decreased",
        "improve": "worsen",
        "improves": "worsens",
        "improved": "worsened",
        "higher": "lower",
        "faster": "slower",
        "more": "less",
        "above": "below",
        "grow": "shrink",
        "grows": "shrinks",
        "grew": "shrank",
        "rise": "fall",
        "rises": "falls",
        "rose": "fell",
        "better": "worse",
        "reduce": "increase",
        "reduces": "increases",
        "reduced": "increased",
        "before": "after",
        "after": "before",
        "pre": "post",
        "post": "pre",
        "earlier": "later",
        "later": "earlier",
    }

    # Morphological antonym pairs (adjectives / ability words). Token overlap
    # alone would score "safe" and "unsafe" as a match, so we reject these
    # directly.
    _ANTONYM_PAIRS: dict[str, str] = {
        "safe": "unsafe",
        "unsafe": "safe",
        "accurate": "inaccurate",
        "inaccurate": "accurate",
        "effective": "ineffective",
        "ineffective": "effective",
        "sufficient": "insufficient",
        "insufficient": "sufficient",
        "capable": "incapable",
        "incapable": "capable",
        "able": "unable",
        "unable": "able",
        "fair": "unfair",
        "unfair": "fair",
        "common": "uncommon",
        "uncommon": "common",
        "likely": "unlikely",
        "unlikely": "likely",
        "usual": "unusual",
        "unusual": "usual",
        "known": "unknown",
        "unknown": "known",
        "valid": "invalid",
        "invalid": "valid",
        "correct": "incorrect",
        "incorrect": "correct",
        "complete": "incomplete",
        "incomplete": "complete",
        "consistent": "inconsistent",
        "inconsistent": "consistent",
        "reliable": "unreliable",
        "unreliable": "reliable",
        "stable": "unstable",
        "unstable": "stable",
        "successful": "unsuccessful",
        "unsuccessful": "successful",
    }

    # Qualifier words that narrow or contradict a broader claim. Substring matches
    # must ignore these added restrictions/over-generalizations so they do not
    # reward a hedged claim as equivalent to an unqualified one.
    _QUALIFIER_WORDS: frozenset[str] = frozenset(
        {
            "only",
            "except",
            "unless",
            "but",
            "however",
            "although",
            "though",
            "whereas",
            "merely",
            "just",
            "mainly",
            "mostly",
            "sometimes",
            "often",
            "rarely",
            "partially",
            "partly",
            "occasionally",
            "frequently",
            "seldom",
        }
    )

    # Causal vs. correlational language. A claim that says one thing "causes"
    # another is stronger than a claim that says the two are merely correlated.
    _CAUSAL_WORDS: frozenset[str] = frozenset(
        {
            "cause",
            "causes",
            "caused",
            "causing",
            "lead",
            "leads",
            "led",
            "leading",
            "result",
            "results",
            "resulted",
            "resulting",
            "produce",
            "produces",
            "produced",
            "producing",
            "make",
            "makes",
            "made",
            "making",
            "create",
            "creates",
            "created",
            "creating",
            "induce",
            "induces",
            "induced",
            "inducing",
            "trigger",
            "triggers",
            "triggered",
            "triggering",
            "drive",
            "drives",
            "driven",
            "driving",
        }
    )
    _CORRELATION_WORDS: frozenset[str] = frozenset(
        {
            "correlate",
            "correlates",
            "correlated",
            "correlating",
            "correlation",
            "associate",
            "associates",
            "associated",
            "associating",
            "association",
            "link",
            "links",
            "linked",
            "linking",
            "relate",
            "relates",
            "related",
            "relating",
            "relation",
            "relationship",
            "coincide",
            "coincides",
            "coincided",
            "coinciding",
            "accompany",
            "accompanies",
            "accompanied",
            "accompanying",
        }
    )

    def _claim_match(self, a: str, b: str) -> bool:
        """Return True if claims are substrings or share meaningful token overlap.

        Substring matching handles exact/shortened claims; token-overlap Jaccard
        catches paraphrases that preserve content words. Negation-count parity,
        directional-opposite checks, an antonym guard, a qualifier-mismatch
        guard, a numeric-mismatch guard, a causal/correlational-mismatch guard,
        and a tautology guard prevent empty or opposite-meaning claims from
        scoring as matches.
        """
        if a in b or b in a:
            return not self._has_semantic_conflict(a, b)
        if self._has_semantic_conflict(a, b):
            return False
        return self._token_jaccard(a, b) >= self._MIN_TOKEN_JACCARD

    def _has_semantic_conflict(self, a: str, b: str) -> bool:
        """Return True if claims are opposite, empty, or differ in scope."""
        return (
            self._negation_count(a) != self._negation_count(b)
            or self._has_opposite_direction(a, b)
            or self._has_antonym_conflict(a, b)
            or self._has_qualifier_mismatch(a, b)
            or self._has_numeric_conflict(a, b)
            or self._has_causal_correlation_mismatch(a, b)
            or self._is_tautology(a)
            or self._is_tautology(b)
        )

    def _has_numeric_conflict(self, a: str, b: str) -> bool:
        """Return True if both claims contain numbers and the values differ."""
        nums_a = self._numeric_values(a)
        nums_b = self._numeric_values(b)
        if not nums_a or not nums_b:
            return False
        return nums_a != nums_b

    def _numeric_values(self, text: str) -> set[str]:
        """Extract normalized numeric values, treating 12%, 12, and 1,000 as equal."""
        raw = re.findall(
            r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?", text.lower()
        )
        normalized: set[str] = set()
        for token in raw:
            number = token.rstrip("%").replace(",", "")
            if "." in number:
                number = number.rstrip("0").rstrip(".")
            normalized.add(number)
        return normalized

    def _has_causal_correlation_mismatch(self, a: str, b: str) -> bool:
        """Return True if one claim uses causal language and the other correlational."""
        tokens_a = set(self._word_tokens(a))
        tokens_b = set(self._word_tokens(b))
        causal_a = tokens_a & self._CAUSAL_WORDS
        causal_b = tokens_b & self._CAUSAL_WORDS
        correlation_a = tokens_a & self._CORRELATION_WORDS
        correlation_b = tokens_b & self._CORRELATION_WORDS
        return bool(
            (causal_a and correlation_b) or (correlation_a and causal_b)
        )

    def _has_qualifier_mismatch(self, a: str, b: str) -> bool:
        """Return True if exactly one claim is qualified.

        Qualifiers restrict scope ("only", "except", "sometimes") or add a
        contrast ("but", "however"). A match between a qualified and an
        unqualified claim is misleading. If both claims are qualified, let the
        other guards and token overlap decide whether the paraphrase is valid.
        """
        tokens_a = set(self._word_tokens(a))
        tokens_b = set(self._word_tokens(b))
        qualifiers_a = tokens_a & self._QUALIFIER_WORDS
        qualifiers_b = tokens_b & self._QUALIFIER_WORDS
        return bool(qualifiers_a) != bool(qualifiers_b)

    def _has_antonym_conflict(self, a: str, b: str) -> bool:
        """Return True if one claim uses a word and the other its morphological antonym."""
        tokens_a = set(self._word_tokens(a))
        tokens_b = set(self._word_tokens(b))
        return any(
            (word in tokens_a and opposite in tokens_b)
            or (word in tokens_b and opposite in tokens_a)
            for word, opposite in self._ANTONYM_PAIRS.items()
        )

    def _is_tautology(self, text: str) -> bool:
        """Return True if a claim is a repetitive, non-informative phrase.

        A claim made of at most two unique content words repeated (e.g.
        "the proposed approach is a proposed approach") carries no verifiable
        meaning and should not count as a match.
        """
        tokens = [
            token
            for token in re.findall(r"[a-z0-9%]+", text.lower())
            if token not in self._STOPWORDS
        ]
        if not tokens:
            return True
        unique = len(set(tokens))
        total = len(tokens)
        return total > 1 and unique <= 2 and unique / total <= 0.5

    def _negation_count(self, text: str) -> int:
        """Count whole-word negation markers."""
        return sum(
            word in self._NEGATION_WORDS for word in self._word_tokens(text)
        )

    def _has_opposite_direction(self, a: str, b: str) -> bool:
        """Return True if one claim uses a directional word and the other its opposite."""
        tokens_a = set(self._word_tokens(a))
        tokens_b = set(self._word_tokens(b))
        return any(
            (word in tokens_a and opposite in tokens_b)
            or (word in tokens_b and opposite in tokens_a)
            for word, opposite in self._DIRECTION_OPPOSITES.items()
        )

    def _token_jaccard(self, a: str, b: str) -> float:
        tokens_a = self._content_tokens(a)
        tokens_b = self._content_tokens(b)
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union if union else 0.0

    def _content_tokens(self, text: str) -> set[str]:
        """Lowercase alphanumeric tokens with stopwords removed."""
        return {
            token
            for token in re.findall(r"[a-z0-9%]+", text.lower())
            if token not in self._STOPWORDS
        }

    def _word_tokens(self, text: str) -> list[str]:
        """Lowercase alphabetic word tokens, including apostrophes."""
        return re.findall(r"[a-z']+", text.lower())

    def _normalize_claim(self, text: str) -> str:
        """Lowercase and collapse whitespace for fuzzy matching."""
        return " ".join(text.lower().split())
