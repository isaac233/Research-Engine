"""Grounded citation fact-check backends for the attribute-or-abstain gate (W1).

MiniCheck (Tang et al., EMNLP 2024) scores whether a claim sentence is supported by a
document at GPT-4 quality for a fraction of the cost. It checks the claim against the
FULL document — the same granularity the DeepResearch-Bench FACT metric uses — so it is
aligned with the grader (unlike the prior lone-span check, which measured negative).

Two local runtimes, selected by the ``RESEARCH_ENGINE_ABSTAIN_GATE`` env value and
returned as a plain ``CheckFn`` so the gate logic (and its unit tests) never import a
model:

- ``minicheck`` -> Ollama ``bespoke-minicheck`` (7B) via the existing ``LLMProvider``.
- ``flan``      -> pip ``minicheck`` ``MiniCheck(model_name='flan-t5-large')`` (770M, CPU,
                   zero VRAM contention), lazily imported so torch/transformers stay an
                   OPTIONAL dependency — absent = the gate stays off, never a crash.
"""

from __future__ import annotations

from collections.abc import Callable

from research_engine.llm.provider import LLMProvider, Message

# (document_page_text, claim_sentence) -> support probability in [0, 1].
CheckFn = Callable[[str, str], float]

_OLLAMA_MODEL = "bespoke-minicheck"
# Fail fast on a wedged Ollama backend (the gate can call this up to max_checks times);
# mirrors the per-call request_timeout added for the other react reasoning calls.
_OLLAMA_TIMEOUT = 60.0


def build_check_fn(spec: str, provider: LLMProvider | None = None) -> CheckFn | None:
    """Return a check-fn for ``spec`` (``minicheck``|``flan``), or None when off/unavailable."""
    spec = (spec or "").strip().lower()
    if spec == "minicheck":
        return _ollama_check_fn(provider) if provider is not None else None
    if spec == "flan":
        return _flan_check_fn()
    return None


def _ollama_check_fn(provider: LLMProvider) -> CheckFn:
    """bespoke-minicheck via Ollama: the ``Document/Claim`` template → ``Yes``/``No``."""

    def check(document: str, claim: str) -> float:
        messages = [Message(role="user", content=f"Document: {document}\nClaim: {claim}")]
        reply = provider.complete(
            messages,
            model=_OLLAMA_MODEL,
            temperature=0.0,
            max_tokens=4,
            request_timeout=_OLLAMA_TIMEOUT,
        )
        return 1.0 if reply.strip().lower().startswith("yes") else 0.0

    return check


def _flan_check_fn() -> CheckFn | None:
    """pip MiniCheck-Flan-T5-Large (770M, CPU). Lazy import — optional dependency.

    Both the import AND model construction (first-run weight download, disk, torch) are
    guarded: any failure returns None so the gate stays off rather than crashing synthesis.
    """
    try:
        from minicheck.minicheck import MiniCheck

        scorer = MiniCheck(model_name="flan-t5-large", cache_dir="./ckpts")
    except Exception:  # noqa: BLE001 — optional dep / model load failed → gate off, not fatal
        return None

    def check(document: str, claim: str) -> float:
        _pred, probs, _raw, _meta = scorer.score(docs=[document], claims=[claim])
        return float(probs[0])

    return check
