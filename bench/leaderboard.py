"""Published DeepResearch Bench reference scores — the Opus/Gemini bar.

Verified snapshot from the DeepResearch Bench paper (arXiv:2506.11763, Table 1),
RACE evaluated with the Gemini-2.5-Pro judge. RACE values are 0-100 where 50 =
ties the reference report. FACT c_acc is % citation accuracy; e_cit is average
effective citations. These are the external bar the engine is measured against.

Caveat: our local run may use a different judge (Ollama/Gemini CLI), so treat
these as directional context, not exact parity. The closest public Anthropic
entry is Claude-3.7-Sonnet w/Search; Opus is not on this public table.
"""

from __future__ import annotations

from dataclasses import dataclass

SOURCE = "DeepResearch Bench paper (arXiv:2506.11763) Table 1; RACE judge = Gemini-2.5-Pro"
AS_OF = "2025-06 (paper release)"
LEADERBOARD_URL = "https://huggingface.co/spaces/muset-ai/DeepResearch-Bench-Leaderboard"


@dataclass(frozen=True, slots=True)
class RefScore:
    """One published reference row (RACE 0-100, FACT c_acc %, e_cit count)."""

    name: str
    kind: str  # "llm_search" | "deep_research_agent"
    race_overall: float
    comprehensiveness: float
    insight: float  # paper column "Depth"
    instruction_following: float
    readability: float
    fact_c_acc: float
    fact_e_cit: float


REFERENCE_BAR: tuple[RefScore, ...] = (
    RefScore("Claude-3.7-Sonnet w/Search", "llm_search",
             40.67, 38.99, 37.66, 45.77, 41.46, 93.68, 32.48),
    RefScore("Gemini-2.5-Pro-Grounding", "llm_search",
             35.12, 34.06, 29.79, 41.67, 37.16, 81.81, 32.88),
    RefScore("Grok Deeper Search", "deep_research_agent",
             40.24, 37.97, 35.37, 46.30, 44.05, 83.59, 8.15),
    RefScore("Perplexity Deep Research", "deep_research_agent",
             42.25, 40.69, 39.39, 46.40, 44.28, 90.24, 31.26),
    RefScore("OpenAI Deep Research", "deep_research_agent",
             46.98, 46.87, 45.25, 49.27, 47.14, 77.96, 40.79),
    RefScore("Gemini-2.5-Pro Deep Research", "deep_research_agent",
             48.88, 48.53, 48.50, 49.18, 49.44, 81.44, 111.21),
)

# The single honest "beat this" Anthropic bar on the public table.
ANTHROPIC_BAR = REFERENCE_BAR[0]
