# finish_line_research_v10 — closing the gap to Claude-3.7 across ALL RACE dimensions

**Date:** 2026-07-21. **Method:** online SOTA sweep (firecrawl research paper search + full-text passage reads), filtered to **inference-time, no-training, 16 GB-portable** levers, mapped per RACE dimension, with each lever's arXiv ablation evidence + the exact change in our code. Supersedes v9's *diagnosis* with a *per-metric attack plan*.

## Where we are vs the bar (validated 2026-07-21, task 53, kimi judge)

| dim | ours (vague profile) | bar (Claude-3.7) | gap | RACE weight |
|---|---|---|---|---|
| comprehensiveness | 32.15 | ~40 | ~8 | — |
| **insight** | **30.41** | ~40 | **~10 (worst)** | **~0.39 (highest)** |
| instruction_following | 36.88 | ~41 | ~4 (nearly there) | — |
| readability | 33.21 | ~41 | ~8 | — |
| **overall RACE** | **32.44** | **40.67** | **~8** | |
| FACT | 76.7% | 93.7% | ~17 | (separate harness) |

Insight is our worst dim AND the highest-weighted → highest ROI. FACT has the largest absolute gap. IF is essentially solved by v9's scope levers (R1/R2).

## The load-bearing evidence (4 papers, dim-level ablations verified from full text)

### FS-Researcher (arXiv:2602.01566) — DeepResearch Bench module ablation, GPT-5 backbone
| removing… | Comp | Insight | Instr | Read | RACE |
|---|---|---|---|---|---|
| (full system) | 51.96 | 54.44 | 52.14 | 51.26 | **52.76** |
| − dual-agent (merge build+write) | −11.06 | **−16.89** | −5.84 | −6.48 | −10.35 |
| − section-wise writing | −4.90 | −8.80 | −1.64 | −4.80 | −5.13 |
| − persistent workspace (notes KB) | −3.58 | **−7.95** | −1.36 | −1.34 | −4.07 |

Reads: (1) **separating evidence-gathering from writing** is worth +10 RACE / +17 insight — interleaving "encourages premature synthesis and shallow exploration"; (2) **section-wise writing** (re-ground on outline+KB each section) is worth +5 RACE / +9 insight over one-shot; (3) the **knowledge base of cross-source evidence NOTES** (not raw spans — "more cross-source comparisons and analyses" as rounds grow) drives +8 insight; (4) comprehensiveness and readability are **orthogonal** and the density→readability drop is "a presentation-level issue [that] a targeted post-hoc rephrasing pass can recover … while preserving comprehensiveness" (their Appendix K). Caveat: their backbones are GPT-5 / Sonnet-4.5; the file-system *machinery* needs a strong backbone (their Limitations), but the four *principles* are model-agnostic.

### On-Device Deep Research at 4B (arXiv:2607.12257) — OUR regime (Qwen3-4B, Ollama, 24 GB laptop)
**Central result: per-source EXPOSURE bounds faithfulness; RETRIEVAL bounds coverage — two separate levers.** Raising chars-of-each-source shown to the writer 400→1500 lifts cited-claim faithfulness **0.45→0.58** (retrieved) / 0.37→0.58 (gold); most gain by 800 chars; costs ~235 output tokens (nearly free). At high exposure, "faithfulness … is bound by exposure, not by whether the cited source is the correct one." Coverage is untouched by exposure — only retrieval recall moves it. And: **repair/self-critique loops do NOT lift trustworthy coverage on small models** ("small models correct themselves only with a strong external checker") — validates our MiniCheck (W1) over self-revision.

### LANCER (arXiv:2601.22008) — zero-shot LLM reranking for nugget COVERAGE
Three prompt-only stages, no training: (1) generate n diverse sub-questions from the request; (2) score each doc's answerability per sub-question (0–5); (3) greedy coverage aggregation → rerank so the top-k covers the most distinct sub-questions. Beats relevance rerankers on coverage; transparent (shows facets covered/missed). Crucially it **selects** among already-retrieved docs — it does NOT spawn more queries (the exact thing that made our W2/R3 net-negative via dilution).

### DeepSurvey (arXiv:2605.29522) — analytical depth + citation reliability
Separates *analysis* from *generation*: **full-text keynotes** per source (contributions/methods/assumptions/limitations) + **cross-paper relation modeling: comparison TABLES, typed relation graphs, guided Q&A**, then evidence-constrained (section-locked) writing. Citation 0.728 recall / 0.681 precision (+12/+9% over baselines). Portable nuggets = keynotes + **comparison tables** (task 53 had *0 tables* despite being a quantitative $-figures question).

## The v10 attack plan — ranked by ROI × portability × avoids-known-negatives

### Tier 1 — cheap, net-new, high-ROI

**V1 — Context-window spans (the exposure lever). Targets FACT + insight. #1 pick.**
Our `memory/evidence_bank.py` banks **single sentences** (`_query_ranked` → one sentence/span, `_MAX_PAGE_SPANS=20`). On-Device-4B says fragmented single-sentence exposure is exactly what caps faithfulness. Fix: bank a **~600–1200 char contiguous window** around each query-matched sentence (sentence + neighbors), not the bare sentence. The writer already injects full `s.text` (no truncation), so wider spans flow straight through. FACT-safe *and* FACT-positive: the parity judge checks claim-vs-full-page, so a wider verbatim window is strictly more-supported; our MiniCheck gate still guards. Env-gate `RESEARCH_ENGINE_SPAN_WINDOW_CHARS` (0 = today's sentence behavior). **Cheapest change, biggest cheap FACT upside, also feeds insight (more context per source to synthesize).**

**V2 — Coverage rerank (LANCER) before banking. Targets comprehensiveness.**
We already emit objectives ≈ sub-questions. Add a zero-shot pass: score each fetched page's answerability per objective (0–5), greedily pick the page set that covers the most objectives, read/bank those first under the fixed page budget. This is the "fetchability/coverage rerank" flagged as the #1 remaining lever since v5 — now with a concrete method that **avoids the W2/R3 dilution failure** (it selects among retrieved pages, never spawns gap queries). Env-gate `RESEARCH_ENGINE_COVERAGE_RERANK`.

**V3 — Cross-source synthesis notes + comparison tables (pre-write insight pass). Targets insight + readability + comp.**
Before the writer runs, one JSON-constrained pass over the frozen bank produces (a) 2–4 **cross-source comparison notes** and (b) **comparison tables** from numeric spans — each cell/claim cites span ids. The writer may cite them like any span. This is FS-Researcher's "evidence notes" (+7.95 insight) + DeepSurvey's comparison tables, made FACT-safe by citing spans (judge checks vs page). Directly attacks our worst dim. Env-gate `RESEARCH_ENGINE_SYNTHESIS_NOTES`.

### Tier 2 — structural, medium effort

**V4 — Post-hoc readability rephrase pass. Targets readability.**
After the brief, one rephrase pass improving flow/transitions **without adding claims or changing cites** (strip-foreign-cites already enforces the citation set). FS-Researcher Appendix K: recovers readability while preserving comprehensiveness. Our read = 33.2. FACT-neutral by construction. Env-gate `RESEARCH_ENGINE_REPHRASE_PASS`.

**V5 — Adversarial synthesis (reuse DevilAgent in the write phase). Targets insight.**
We already run a `DevilAgent` + `CampaignStage.ADVERSARIAL`, but its output feeds evaluation, not the brief. Route it pre-write: surface contradictions / counter-evidence across the bank, the writer integrates them ("multi-perspective reasoning" — arXiv:2601.04651). Insight lever at near-zero new infra. Env-gate `RESEARCH_ENGINE_ADVERSARIAL_SYNTHESIS`.

**V6 — Verify clean build→write separation (dual-phase).**
FS-Researcher's biggest ablation (+10.35). We bank-then-write via react (`_react_plan` → `_react_brief`), and the writer is already section-wise with carry-context (confirmed in `section_writer.py`) — so we partially have this. The delta: FREEZE the bank before writing and ensure the writer never triggers new retrieval; put V3's notes into the frozen KB. Mostly an audit + guardrail, not a rebuild.

### Tier 3 — bigger bets (track, don't build now)
- **Trained backbone as the AGENT** (AgentCPM-Report 8B native GGUF fit / MindDR-30B / already-pulled Tongyi-DR) — buys RACE not FACT (WebWeaver off-the-shelf RACE 46.77 but FACT 25%); heavy retrieval-shim work. Already tracked in [[trained-deepresearch-models]].
- **FS-Researcher file-system workspace** — needs a strong backbone (their own Limitations); we harvested the 4 principles instead of the machinery.

## What NOT to do (known-negatives, do not re-open)
- **No new gap-query expansion loops** — W2/W4 (v7) and R3 (v9 `gap` cell, FACT 57.6%) all net-negative via retrieval dilution. V2 coverage-rerank is *selection*, deliberately not expansion.
- **No self-critique/self-revision for FACT** — On-Device-4B: small models don't self-correct; keep the external MiniCheck checker (W1).
- **Don't stack R5 (Tongyi lane) / R6 (ranker) on vague-cohort tasks** — the 2026-07-21 A/B measured both as hurting this class.

## Measurement protocol (unchanged discipline)
Env-gate every lever default-OFF; A/B one variable at a time via `scripts/run_task53_ab.sh` under `RETRIEVAL_CACHE`; kimi judge via the bridge; then prove the CLASS on a 2nd underspecified task before trusting. Expected first target: V1 lifts FACT 76.7→~85; V2+V3 lift insight 30→~35 and comp 32→~36; V4 lifts read 33→~37 → overall toward the 40.67 bar.

## Implementation mechanics (v10.1 — second research pass, verified from full text)

**V1 — sentence-window spans ("small-to-big").** Rank by single-sentence query overlap (keep `_query_ranked` precision) but BANK a window = matched sentence ± K neighbor sentences, merged when windows overlap on the same page. Char target ~**800–1024**: On-Device-4B faithfulness curve 0.45→0.55 by 800, →0.58 by 1500 (most gain by 800); LlamaIndex chunk-size eval peaks faithfulness AND relevancy at 1024; sentence-window retrieval (LlamaIndex `SentenceWindowNodeParser`) is the canonical pattern. Env `RESEARCH_ENGINE_SPAN_WINDOW_SENTENCES` (K, def 0 = today) or `_SPAN_WINDOW_CHARS`. Must merge adjacent selected sentences into one contiguous span (dedup overlap). FACT-safe: parity judge checks claim-vs-page, wider verbatim window = more support, not less.

**V2 — LANCER coverage rerank, exact algorithm.** (1) Sub-questions: REUSE our existing objectives (paper: n=2–3 sufficient; more → topic drift) — zero extra generation. (2) Answerability: per candidate page, one batched LLM call rating each objective 0–5 with LANCER's verbatim rubric ("Determine whether the question can be answered based on the provided context? Rate 0–5… 5=highly relevant/complete/accurate … 0=not relevant"). (3) Aggregate = **greedy-sum** (most threshold-robust of the variants): start Z={}, iteratively add the page maximizing `U_sum(Z)=Σ_j max_{d∈Z} r_{d,qj}`, until gain=0, then append remaining by descending utility. Read/bank the top pages under `REACT_MAX_PAGES`. Bound scored candidates (~top 20 by relevance first) — serial Ollama, and Deep-Reporter warns filtering can be ~70% of latency. Env `RESEARCH_ENGINE_COVERAGE_RERANK`. Selection, not expansion → avoids the W2/R3 dilution failure. (Support: arXiv:2603.08819 shows retrieval coverage predicts final report coverage.)

**V3 — split into V3a + V3b.**
- **V3a — Deep-Reporter checklist-guided section writing + per-section evidence filter.** Use R2 critic's per-section acceptance criteria AS the sectional checklist `C_k` ("must address all"); before writing section k, filter the bank to spans that entail `(section, C_k)` (one relevance/entailment pass); add a running GLOBAL summary `m_global` alongside our existing carry-context tail `m_local`. Deep-Reporter's decoded section prompt (position-aware first/middle/last, strict cite rules, 300–800 words/section) is a richer template than our current `_write_section` — port it. Ablation: filtering + recurrent context are the inference-time wins (their table gains needed SFT, but base agentic framework still 4.2× naive). Env `RESEARCH_ENGINE_SECTION_CHECKLIST`.
- **V3b — comparison tables from numeric spans** (DeepSurvey). Pre-write pass: detect a quantitative dimension set across entities, emit a markdown table, each cell cites a span id. Insight + readability; task 53 had 0 tables. Env `RESEARCH_ENGINE_COMPARISON_TABLES`.

**V4 — post-hoc rephrase.** One pass, improves flow only; `_strip_foreign_cites` already pins the citation set so no new claims can enter. **V5 — adversarial synthesis:** feed `DevilAgent` contradictions into the pre-write notes.

**Extra caveat — circularity (arXiv:2601.13227):** nugget-based RAG judged by nugget-based judges can self-confirm. We're safe (judge = RACE/kimi + parity-FACT, not nugget-based) — but keep V2's answerability scores OUT of any scoring path.

## Outcomes (measured 2026-07-21, task 53, frozen-cache single-variable A/B, kimi judge)

| cell | RACE | comp | insight | IF | read | FACT | chars | verdict |
|---|---|---|---|---|---|---|---|---|
| B0 vague | 32.44 | 32.15 | 30.41 | 36.88 | 33.21 | 76.7% | 17098 | baseline |
| **V1 spanwin** (±2 sent / 1024 cap) | **34.24** | 34.48 | 32.22 | 38.14 | 34.62 | **82.1%** | 21778 | ✅ **clean win, every dim up, FACT +5.4pt** |
| V3b tables (on V1) | 34.12 | 33.75 | 32.36 | 36.55 | **36.47** | 79.3% | 18703 | ⚠️ wash (read +1.85, rest ~flat/down) |

- **V1 = validated.** Exposure lever behaved exactly as On-Device-4B predicted; the frozen cache makes it a true single variable (retrieval identical), so this is signal not N=1 noise.
- **V2 deferred, not built:** under frozen cache the same pages are always available and B0 is under the page budget → coverage *selection* drops nothing = inert (W5-inert trap). Only bites on a fresh/over-budget run (which reintroduces retrieval noise). Needs a corpus-capped or fresh-N≥3 eval.
- **V3b inconclusive:** table lands + readability +1.85, but overall RACE flat and the article body came out 3k shorter this run. Root cause = the methodological finding below. Stays env-gated, not promoted.
- **⚠️ METHODOLOGICAL FINDING (governs all remaining levers):** `KEEP_CACHE` freezes RETRIEVAL but NOT GENERATION. The Ollama synth writer at temp=0 is **not bit-deterministic** — run-to-run RACE ~±1-2 and length ~±3k chars. So writing-side levers (V3b/V4/V3a/V5) can't be cleanly measured at N=1 unless their effect is large/mechanistic. **Test writing-side levers at N≥3.** V1 was measurable at N=1 only because FACT +5.4 dwarfed the noise.

## Sources (verified full-text this session)
- FS-Researcher: test-time file-system scaling — arXiv:2602.01566
- On-Device DR at 4B: exposure bounds faithfulness — arXiv:2607.12257
- LANCER: LLM reranking for nugget coverage — arXiv:2601.22008
- DeepSurvey: analytical depth + citation reliability — arXiv:2605.29522
- Supporting: multi-perspective RAG 2601.04651 · ScaffoldAgent 2606.20122 · DualGraph 2602.13830 · AgentCPM-Report 2602.06540 · DeepResearch Bench II 2601.08536

## v10.2 measured outcomes (2026-07-22, autonomous session, kimi judge via bridge)

All levers env-gated default-off; task-53 cells use the frozen B0 cache (single-variable);
task-57 is live retrieval (multi-entity class-proof).

| lever | test | RACE | Δ vs baseline | verdict |
|---|---|---|---|---|
| V1 spanwin | task-57 vs baseline 35.20 | **37.82** | +2.62 (every dim up) | ✅ class-proven → promoted into `vague` |
| V3 notes | task-53 frozen N=3, V1 34.65 base | 34.98 | +0.33 (insight +0.25, read −2.0) | ⚠️ WASH — not promoted |
| V7 entity | task-57 vs thematic+V1 37.82 | 32.90 | −4.92 (5/13 firms, no comparative) | ❌ NEGATIVE — not promoted |
| V8 spans32 | task-53 frozen N=3, V1@20 34.65 | 33.53 | −1.12 (shorter, 19.2k vs 21.8k) | ❌ NEGATIVE — not promoted |

**Conclusion.** Insight (worst dim, 0.39 wt) does not move with a pre-write synthesis pass (V3),
per-entity restructuring (V7), or more banked evidence (V8). The article prose is already analytical
and cross-source; the ceiling is the **local writer's (mistral-small3.2) analytical capacity (~34-35
RACE)**, not the scaffold. Structure without evidence-depth *fragments* (V7); more spans without a higher
writer cap *dilute* (V8, writer is output-capped at `max_sentences`). This is convergent with the v7
(W1-W5) and v9 (R1-R6) results: only V1 (exposure) and the react+grounded-scope+WARP `vague` stack are
net-positive on this writer.

**The remaining ~5-6 RACE gap to the 40.67 bar is a MODEL problem.** The next real lever is a **trained
deep-research model as the AGENT** (Tongyi-DR-30B / AgentCPM-Report 8B GGUF) driving the retrieval+reason
loop with a SearXNG/CDP shim — not more inference-time scaffolding (R5's passive reasoning-lane swap was
measured worst). Buys RACE not FACT; keep the parity-FACT harness + MiniCheck. See
`docs/plan/resource_fit_verification.md`.

### v10.2 CORRECTION (verified by diffing saved articles)

The V8 / depth-stack rows above are **INCONCLUSIVE, not negative.** Diffing the saved
articles showed the engine is **deterministic on the frozen cache** (temp=0): every config's
3 reps are byte-identical, and `engine_t53_v8_r1.jsonl` is byte-identical to `engine_t53_v1_r1.jsonl`.
So `MAX_PAGE_SPANS=32` (V8) and `WRITER_MAX_SENTENCES=28` (depth-stack) produced **no article
change** — task-53's frozen pages are span-poor (<20 spans/page), so those caps never bind.
The "RACE 34.65→33.53" was **kimi JUDGE noise on the identical article** (judge noise ≈ ±1 sd,
≤2.5 range; e.g. V1's 3 reps 34.81/35.80/33.35 are one article judged three times).

Corrected takeaways: (1) the run-to-run RACE variance is the JUDGE, not the writer — the prior
"writer non-determinism → N≥3 engine runs" heuristic is wrong; correct protocol = 1 engine run
per config, judge ×N. (2) V3 (real +1385-char change, flat RACE) = wash and V7 (real restructure,
−4.9) = negative both stand — those levers changed the article. (3) The evidence-DEPTH hypothesis
is **untested**; to test it, run V8 + higher writer cap on the RICH-evidence **task-57 frozen
cache** where the flags bind. The "writer is the ceiling" conclusion rests on V1/V3/V7, not V8.
