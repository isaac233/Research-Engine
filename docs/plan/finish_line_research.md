# Finish-Line Research — How to Beat Opus on DeepResearch Bench (2026-07-13)

Online research (NOT via the engine) into the methodology of SOTA deep-research
systems. Goal: prove the project's goal (gemma4/local-model-driven engine beats
Opus) is achievable, and extract the exact architecture to get there.

## VERDICT: ACHIEVABLE — strong evidence

**WebWeaver (Alibaba Tongyi, arXiv:2509.13312) on Qwen3-30B-A3B (a 30B MoE, 3B
active — runs locally, MoE tolerates VRAM offload this project already uses)
scores RACE 46.77 on DeepResearch Bench — beating Claude-3.7-w/Search (40.67)
AND OpenAI Deep Research (46.45).** With Claude-Sonnet-4 the same architecture
hits **93.37% citation accuracy** (= Claude-3.7's 93.68% bar). The paper also
shows the skill is *learnable* by small models (WebWeaver-3k SFT set). The user
already runs `qwen3.6-27b`. => A local 27-30B MoE + the right architecture beats
the bar. The engine's current RACE ~21 / FACT ~20% is an ARCHITECTURE gap, not a
model-capacity gap (confirmed: `--quality 1.0` bigger models gave no lift).

## The winning architecture (WebWeaver — methodology, not summary)

Dual-agent, both **ReAct** (think→action→observation loops):

**Planner** — actions: `search`, `write_outline`, `terminate`. Runs a *dynamic
research cycle* that interleaves evidence acquisition with outline optimization
(they co-evolve — NOT search-then-outline nor outline-then-search):
- `search`: query web → two-stage filter: (1) LLM selects relevant URLs from
  titles/snippets; (2) for each fetched page, LLM (a) distills a query-relevant
  summary (fed back into planner context) and (b) extracts **verifiable evidence
  spans** (quotes, data points) stored in a **Memory Bank** with **evidence IDs**.
- `write_outline`: refine/expand/restructure the outline; **populate each section
  with citations = evidence IDs** from the memory bank.
- `terminate`: when the outline is comprehensive and well-supported.

**Memory Bank** — context management. Only short summaries live in the planner's
context; raw evidence is stored by ID and retrieved on demand. (Planner parses
100+ pages / 100k+ tokens; writer emits 20k+ tokens.) This defeats "lost in the
middle" / context-bleeding.

**Writer** — actions: `retrieve`, `write`, `terminate`. Sequential, single-agent,
section-by-section (NOT parallel — parallel loses coherence). For each section:
`retrieve` ONLY the evidence IDs the outline cited for that section, then `write`.
Targeted per-section evidence => drastically less context-bleed => **high citation
accuracy + comprehensiveness + readability simultaneously**.

## The citation mechanism — "Attribute First, then Generate" (arXiv:2403.17104)

How to get sentence-level citations that actually verify (fixes FACT):
1. **Content selection** — extract verbatim relevant spans from sources. These
   spans ARE the attribution. (Located via string-matching; unmatched omitted.)
2. **Sentence planning** — group spans into clusters; each cluster = one sentence.
3. **Sentence-by-sentence generation** — generate each sentence conditioned ONLY
   on its cluster's spans + preceding sentences: p(s_{i+1} | s_{1:i}, C_{i+1}).
   Citation is BUILT-IN, not post-hoc. Concise, verifiable, cuts fact-check 50%+.

This is the opposite of the engine's failed approach (free-form synth → post-hoc
lexical guard). The engine's extraction ALREADY produces verbatim evidence spans
(the anti-hallucination substring guard) — reuse them as the attribution source.

## Reliability enabler — grammar-constrained decoding (arXiv:2510.03847 SLM survey)

"Tool-use accuracy depends on argument correctness and strict schema adherence
more than raw parameter count. SLMs with enforced schemas frequently match or
surpass larger LLMs in function calling." Pattern A: 3-9B SLM + JSON-Schema =>
>99% structured-output validity. Recipe: **grammar/JSON-schema constrained
decoding + temperature 0 + validator + repair-with-verifier + SLM-default /
frontier-fallback on uncertainty.** Ollama supports structured outputs (llama.cpp
GBNF grammars / `format` schema). The engine currently free-form parses JSON with
defensive fallback — switching every agentic step (URL selection, evidence
extraction, outline ops, action selection) to constrained decoding is a concrete,
high-impact, currently-missing lever.

## How RACE / FACT actually score (to optimize honestly, not game)

- **RACE**: Judge LLM generates task-specific dimension weights + criteria, scores
  target vs a reference report (Gemini-2.5-pro Deep Research). S = tgt/(tgt+ref),
  so 50 = ties reference. Dims: Comprehensiveness, Depth, Instruction-following,
  Readability. Comprehensiveness correlates with # effective citations (more
  evidence → more coverage). Reference reports are long + comprehensive; the
  engine's ~5KB briefs score low on Comp/Depth. Outline-driven writing fixes this.
- **FACT**: extract statement-URL pairs → dedupe → fetch cited URL text → judge
  support. C.Acc = supported/total; E.Cit = supported count. Rewards BOTH accuracy
  and abundance. WebWeaver gets ~200 effective citations (planner seeks more
  evidence). PDFs/DOIs that the fetcher can't read auto-fail → prefer HTML pages.

## Open implementations to borrow from
- `shibing624/WebResearcher` — open dual-agent WebWeaver (planner/writer + memory bank).
- `SkyworkAI/DeepResearchAgent` — hierarchical multi-agent.
- `langchain-open-deep-research` — RACE 43.44 (beats Claude), Ollama-compatible.

## Mapping to THIS engine (restructure, not rewrite)
- discovery/ (SearXNG web lane, adapters) => Planner `search` tool + two-stage URL filter (enricher already fetches pages).
- extraction/ verbatim-evidence spans => Memory Bank content + attribution source.
- NEW planning/ outline agent (ReAct) => dynamic outline + evidence IDs.
- synthesis/ => Writer (section-by-section, retrieve-then-write, attribute-first).
- llm/ollama_client => add grammar/JSON-schema constrained decoding.
- bench/ + kimi-k2.7-code:cloud judge => the measurement loop (already trustworthy).

## Sources (relevant + uniquely useful; methodology read, not abstracts)
- arXiv:2509.13312 WebWeaver — the winning architecture + local-model proof.
- arXiv:2403.17104 Attribute First, then Generate — sentence-level citation mechanism.
- arXiv:2506.11763 DeepResearch Bench — exact RACE/FACT scoring internals.
- arXiv:2510.03847 SLM Agentic Systems survey — constrained decoding + SLM feasibility.
- Supporting: 2407.01796 ReClaim (ground every sentence), 2502.09604 SelfCite
  (context-ablation citation reward), 2509.21557 G-Cite vs P-Cite, 2605.06635
  Cited-but-Not-Verified (AST citation eval), 2604.03173 reference-hallucination rates.
