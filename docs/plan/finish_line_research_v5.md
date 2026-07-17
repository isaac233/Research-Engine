# Finish-line research v5 — the measured gap is SCALE + PLAN-THEN-FILL, not volume or writer-polish (2026-07-17)

Grounded in **today's measured data** (STEP 1 falsification + task-anchored-outline
experiment) cross-referenced with the SOTA methods already distilled in v1-v4 and the
actual DeepResearch-Bench RACE criteria (`bench/data/criteria.jsonl`) and reference
report (`bench/data/reference.jsonl`). This round stops proposing writer-prompt tweaks
and names the structural gap.

## The bar, and where we actually are (task 51, kimi judge)
| | RACE | comp | insight | IF | read | FACT |
|---|---|---|---|---|---|---|
| our react brief (STEP 1) | 14.66 | 14.1 | 7.5 | 8.65 | 33.1 | 79.4% |
| Claude-3.7 bar (DoD) | 40.67 | 39.0 | 37.7 | 45.8 | 41.5 | 93.7% |
| WebWeaver on Qwen3-30B-A3B (achievable, local MoE) | 46.77 | — | — | — | — | ~93% |

RACE is **reference-normalized**: 50 = ties the reference report. We score 14.66 because
we are nowhere near the reference on its own task-specific criteria.

## What the reference actually is (the thing we're graded against)
- **Reference report length = 63,118 chars (~16k tokens). Our brief = 13,024 chars (~1/5).**
- Task 51's graded criteria (25 total, dimension-weighted):
  - **comprehensiveness (7):** population projections 2020-2050; per-category analysis of
    **clothing / food / housing / transportation**; other consumption categories; …
  - **insight (5):** depth/originality projecting consumption-habit *changes*; **logical
    rigor synthesizing diverse factors for market sizing**; segmentation of willingness.
  - **instruction_following (5):** **direct** population projection; coverage of **ALL**
    specified sectors; use of **ALL** mandated analytical bases (projection + willingness
    + habit change).
  - **readability (8):** structure, quantitative-data presentation, professional prose.
- **Our STEP-1 brief scored comp 14 / insight 7.5 / IF 8.65** because it was a ~13k-char
  *healthcare/aging essay* (section titles: Longevity, Health Challenges, Healthcare
  Strain, Policy, Call to Action; keyword coverage cloth=1 food=1 transport=1 market=1).
  It answered ~1 of 25 criteria.

## THE CORE METHODOLOGICAL DIFFERENCE (SOTA vs ours)
**SOTA is PLAN-THEN-FILL at reference scale. Ours is GATHER-THEN-ORGANIZE at 1/5 scale.**

WebWeaver (RACE 46.77 on the *same* local 30B MoE we run) and Step-DeepResearch both:
1. Decompose the QUERY into a fixed outline skeleton of its information needs BEFORE
   retrieval, then **co-evolve** it with evidence.
2. Do **per-section targeted retrieval** — each outline section drives its own search
   until it is well-supported (so every asked dimension gets evidence).
3. Write **section-by-section at reference length** (20k+ tokens), each section seeing
   only its own evidence (coherence + no context overflow).

We do the inverse: one discovery pass / a react loop that banks whatever the dominant
serp topic returns, THEN an outline that organizes *that* evidence (so it drifts to the
evidence's topic, not the task's), THEN a writer capped at ~13k chars total.

**Today's two experiments prove this is the gap, not volume or writer-polish:**
- **Volume is NOT the lever** (STEP 1): react `MAX_PAGES` 16→48 banked the same 17 pages
  (real cap = `react_planner.max_iters=8`) and RACE stayed ~15. More spans ≠ higher RACE.
- **Outline-anchoring alone is NOT enough** (STEP 1b): forcing the question's dimensions
  onto the outline lifted RACE 14.66→17.25 and IF 8.65→12.5 — real, on the surface that
  fails — but the report still drifted (became a "functional food" essay, food=47 vs
  cloth/housing/transport ~1) and FACT crashed 79→21%, because **the BANK didn't contain
  balanced per-dimension evidence for the outline to organize.** Anchoring the outline
  without balanced retrieval just forces sections onto thin evidence and breaks citations.

## WHAT NEEDS TO CHANGE — three coupled levers, in dependency order
All three are the never-built Phase 3-4 of `finish_line_plan.md`. They are coupled: each
alone regressed or under-delivered (measured). Ship them together, measure on the LIVE
bench (the cache A/B cannot see retrieval or length — proven today).

### Lever 1 — Outline skeleton seeded from the task BEFORE retrieval (extends today's work)
Decompose the query into its mandated sections up front (`plan_objectives` already
enumerates them; `OutlineBuilder(task_anchored=True)` already exists) and FIX that
skeleton as the retrieval target — do not let banked evidence redefine it. Targets IF +
comprehensiveness (cover all mandated sectors). Cheap: wire the two existing pieces.

### Lever 2 — Per-section targeted retrieval with a coverage quota (THE retrieval-balance fix)
Each outline section runs its OWN gap query until it has ≥K spans; the react loop's
budget is spent to *balance across sections*, not to pile pages on the dominant topic.
This is the fix for the drift that tanked FACT in STEP 1b and the low comprehensiveness/IF
throughout. Change `react_planner` to iterate per-outline-section (not just per-objective),
and CDP-recover the ~50% 403 reads so thin sections can fill. Targets comp + IF + FACT
(on-page balanced evidence).

### Lever 3 — Reference-scale writing budget (the biggest raw RACE lever)
Reference = 63k chars; ours = 13k. On a reference-normalized metric a 1/5-length report
cannot tie. Raise section count and per-section length toward reference scale:
`SectionWriter` `n=max(2,min(spans,8))` and `max_tokens=1200` are the hard cap; `deepen`
only adds 2-4 sentences to a few sections. Write section-by-section (already do) at a
per-section token budget scaled to the quality slider / `num_ctx`, targeting reference
length. Cheapest to *try first* as an isolated probe (does more length alone move RACE?),
but its real payoff needs Levers 1-2 supplying balanced evidence to write about.

## Sequencing (cheapest-falsifying first)
1. **Length probe (½ day):** raise SectionWriter n + max_tokens + deepen breadth; live
   task-51 react bench under watchdog. GATE: does RACE rise toward the reference at 2-3×
   length? If length alone does nothing, the bottleneck is evidence coverage → skip to 2.
2. **Levers 1+2 together (retrieval-balance + seeded skeleton):** per-section quota
   retrieval into the fixed task skeleton. Live bench N≥3. GATE: comp + IF rise AND FACT
   holds (no STEP-1b-style FACT collapse — balanced evidence should prevent it).
3. **Combine 1+2+3, N≥4 react bench:** the real test vs the bar. Only here does the cache
   A/B become useless — these are all live/structural.

## What is ALREADY settled (do not re-litigate)
- **Volume/page-cap: DEAD** (STEP 1). Don't raise `MAX_PAGES`; raise `max_iters`/per-section.
- **FACT verify-and-regenerate: NEGATIVE** (v4, [[verify-regen-negative]]) — span-entailment
  ≠ page-level judge. FACT is decent (44-79%) when retrieval is on-page; its residual is
  STRUCTURAL (PDF/paywall/>6000-char-deep spans auto-fail), addressed by Lever 2's
  HTML-preferring balanced retrieval, not by another writer pass.
- **cite_fix / P-Cite lexical re-point: NEGATIVE** (v3) — our cites are already span-aligned.
- **Writer-prompt polish (paragraph, faithful, synth): exhausted** — `section_synth` is the
  champion (28 RACE on cache) and is already the default; more prompt variants swing ±2
  within noise. The gap is structural (scale + retrieval), not prose style.
- **Grammar-constrained verbatim decoding: NEGATIVE** (v4/FullCite) — lowers claim↔cite
  semantic alignment; entailment is the target, not character-identity.
- **SFT/RL: no budget** — SOTA's real moat; we substitute structure (plan-then-fill).

## The one-sentence answer to "what needs to happen"
Stop gathering-then-organizing at 1/5 scale; build **plan-then-fill at reference scale** —
a task-seeded outline skeleton (Lever 1) filled by per-section balanced retrieval (Lever 2)
and written to reference length section-by-section (Lever 3) — and measure it on the LIVE
bench, because the fast cache A/B is blind to exactly the levers that matter (proven today).

Sources: today's STEP 1 / STEP 1b measurements; `bench/data/criteria.jsonl` +
`reference.jsonl` (metric ground truth); v1-v4 research docs; `finish_line_plan.md`
Phase 3-4 (the unbuilt WebWeaver Planner+Writer). See [[deepresearch-bench-scoreboard]].
