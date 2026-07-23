# Finish-line research v3 — WHY we're stuck and WHAT to employ (2026-07-15, online-sourced)

Online research into the specific causes of our RACE/FACT gap and the methods that
close it, for a **local-model, no-training-budget** engine. Sources are recent
(2025-2026) deep-research papers, read in full for the actionable method.

## The gap (our trustworthy baseline vs the bar)
- Ours (kimi judge, writer_eval V2): **RACE 24.7 / FACT 53.0% / E.Cit 17.25**.
- Bar (Claude-3.7-w/Search): **RACE 40.7 / FACT 93.7% / E.Cit 32**.
- Two separate problems: **citation accuracy (FACT)** and **report depth/breadth (RACE)**.

## WHY #1 — FACT is stuck (~53%): we cite the WRONG way
**Evidence — "Generation-Time vs Post-hoc Citation" (arXiv:2509.21557):** two paradigms.
- **G-Cite** (generate prose + inline cites in ONE pass) — what our `section_deepen`
  default does. Prioritizes precision but **loses coverage**, and when the writer
  paraphrases a span the inline cite no longer verifies against the page.
- **P-Cite** (draft first, then a SEPARATE pass attaches/verifies citations) —
  **"achieves higher coverage with competitive correctness."** Paper's explicit
  recommendation: **"retrieval-centric, P-Cite-first."** Human eval: P-Cite gives
  more correct answers with LESS citation hallucination.
- **Verdict:** our catalogue #10 ("attribute-first sentence generation", a G-Cite
  method) is the *inferior* paradigm. Switch to **post-hoc citation correction.**

**The cheap, no-training method — CiteFix (arXiv:2504.15629):** post-processing that
**corrects** (not just deletes) citations. Split report into factual points
(sentences delimited by cites) → for each, score similarity to the retrieved docs
(keyword + semantic / BERTScore) → re-point each cite to the **best-supporting**
doc, drop the unsupportable. **+15.46% relative citation accuracy, minimal latency,
works on open models (Qwen-2.5-14B: +8-10%).** Amazon product paper — built for
exactly our constraint (small model, low cost, no retraining).

**Why this fits us perfectly:** our `EvidenceBank` already holds **verbatim spans
bound to their URL**. A post-hoc pass that re-points each sentence's `[eN]` to the
best-matching bank span makes the citation verify *by construction* (the span is a
verbatim substring of the cited page the FACT metric re-fetches). This is the RIGHT
version of the abandoned `verify_citations` — match against the trusted BANK SPAN,
NOT a re-fetched page (the earlier re-fetch approach failed on boilerplate, per
HANDOFF; that failure does not apply here).

## WHY #2 — RACE depth is shallow: untrained local models write shallow lists
**Evidence — Step-DeepResearch (arXiv:2512.20491), a 32B model that rivals OpenAI/
Gemini DeepResearch:** they name our exact failure mode — **"base models without
task-specific training exhibit shallow response patterns, characterized by short,
loosely connected sentences and superficial bullet points."** Their headline fixes
were TRAINING (mid-train + SFT + RL) — out of our budget — but two are architectural
and transferable:
1. **Synthesis-driven Drafting** — "transform raw tool-call trajectories into
   structured **paragraphs with logical deduction**, strictly limiting unordered
   lists as the primary content body." (Depth comes from connected analytical prose,
   not bullet piles.)
2. **A negative correlation between depth and comprehensiveness** — pushing depth
   made the model **terminate early** and lose coverage. Fix: a **pairwise judge that
   keeps a revision only if it is deeper WITHOUT losing coverage.** (We have `deepen`;
   make it enforce this gate instead of blindly splicing.)
- Also: single-agent **ReAct** beats heavyweight multi-agent (validates our #8 loop
  direction); "internalized atomic capabilities" via training is their moat we can't
  copy — so we lean on structure + post-hoc correction instead.

## WHAT to employ (this session — all cheap, no training, MEASURABLE FAST)
The big unlock: **#10 and #11 are WRITER-side → measurable on the cached
`fixed_evidence.jsonl` via `bench/writer_eval.py` in MINUTES with the kimi judge.**
No slow live pipeline needed to get real numbers. (Only retrieval changes need the
slow path — and the speed fix below makes those finish too.)

1. **#10 → P-Cite post-hoc citation correction** (`synthesis/cite_fix.py`): after the
   writer drafts, for each sentence match to the best-supporting bank span (lexical
   keyword+overlap, no extra model), re-point/attach `[eN]`, drop unsupportable.
   Add a `section_deepen_pcite` writer variant; A/B vs `section_deepen` on the cache.
   **Target: FACT 53% → 70%+ without RACE loss.**
2. **#11 → synthesis-driven paragraph drafting + coverage-preserving depth gate**:
   section-writer prompt directs connected analytical paragraphs, bans list-as-body;
   `deepen` keeps a revision only if it grows coverage. Measure on the cache.
   **Target: RACE 24.7 → higher Comp/Depth.**
3. **#12 → prefer HTML over PDF/DOI**: already covered (react `read_fn` skips PDF/DOI;
   `_citable_url` prefers HTML). No new work.

## What NOT to do (research-backed negatives)
- Do NOT pursue generation-time attribute-first for FACT (G-Cite loses coverage;
  P-Cite wins — 2509.21557).
- Do NOT chase RL/SFT (Step-DR's real moat) — no budget; structure + post-hoc instead.
- Do NOT re-fetch pages to verify citations (HANDOFF-proven failure; match the bank).

## Measurement discipline (fixes the "smoke never finishes" waste)
- Writer/citation changes → `python -m bench.writer_eval score --variant X` over the
  cache (minutes, kimi judge). This is where #10/#11 get their numbers.
- Retrieval changes → the live pipeline, now with a **hard wall-clock/step budget**
  and **serp-only react search** so a run finishes in minutes, never hangs.

Sources: 2509.21557 (G/P-Cite), 2504.15629 (CiteFix), 2512.20491 (Step-DeepResearch),
2509.13312 (WebWeaver), plus the catalogue in `~/.claude/plans/peaceful-popping-pancake.md`.
