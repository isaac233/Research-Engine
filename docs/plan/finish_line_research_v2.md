# Finish-Line Research v2 — Cleaner Signal + FACT/Breadth Methods (2026-07-14)

Second research pass, triggered by two measured problems: (1) N=3 benchmark
variance too high to tune against; (2) the outline+section Writer lifted RACE to
23.3 (best, > legacy 21.5) but dropped FACT to 16.7%. Sources read in full
(methodology, not abstracts).

## Finding 1 — Fine-grained (per-sentence) citation is the FACT bug
**arXiv:2604.01432 "Are Finer Citations Always Better?" (JHU, Apr 2026).** Controlling
for citation *volume*, enforcing sentence-level citation degrades attribution quality
16–276% vs **paragraph-level**; quality peaks at intermediate (paragraph) granularity.
Mechanism ("Granularity Mismatch"): atomic sentence units fracture the coreference /
multi-sentence dependency chains a model needs for faithful synthesis; the cited span
is "incomplete without the dependency chain." Larger models are penalised MORE by
fine-grained constraints. Crucially: coarser granularity improves attribution WITHOUT
hurting correctness (decoupled). → Our section writer forces one atomic span per
sentence AND paraphrases → both fracture attribution. **Fix: keep the delivered
sentence tight to its span (don't paraphrase away specifics), OR cite at paragraph
granularity.** Implemented `section_faithful` (outline structure + near-verbatim
per-span sentences) to test against `flat` (verbatim, FACT 35%) and `section`
(paraphrase, FACT 16.7%).

## Finding 2 — Objective-driven outline BEFORE retrieval + evidence-based termination
**arXiv:2604.24978 "Don't Stop Early" (Enterprise Deep Research), ablated on
DeepResearch Bench.** Coverage ablation (their metric): w/o Outline 3.80 → w/o Outline
Reflection 3.94 → w/o Agent Termination 4.02 → full 4.31. Three mechanisms:
1. **Coverage-driven outline built from the TASK's information objectives, BEFORE any
   retrieval** — enumerate sub-questions the report must answer. "Early retrieval biases
   the process toward tangential but easily-accessible details." (We do the opposite:
   build the outline FROM whatever we happened to fetch → evidence-limited.)
2. **Outline reflection** — check for missing/underspecified objectives, resolve gaps
   before execution.
3. **Evidence-based termination** — each section defines sufficiency conditions; keep
   gathering until met (prevents premature stopping = uneven depth).
→ Our Planner (breadth) half should: generate an objective outline from the query first,
then retrieve to satisfy each section, with per-section sufficiency + gap-driven search.

Corroborating (same direction): ScaffoldAgent (2606.20122, utility-guided dynamic
outline), DualGraph (2602.13830, separate exploration from outline, gap-triggered
search), RhinoInsight (2511.18743, verifiable checklist vs context rot), iterative
survey (2510.21900, recurrent outline vs one-shot), TTD-DR (2507.16075, draft skeleton
+ iterative revision).

## Finding 3 — Getting a clean signal (the measurement problem)
N=3 noise = discovery/screening/fetch variance (0–4 sources/task run-to-run), not the
writer. Fix built this session: **fixed-evidence writer-eval harness** (`bench/writer_eval.py`):
run discovery+extraction ONCE per task, cache the extracted sources (they carry
`meta.page_text`), then rebuild the Evidence Bank deterministically (no re-fetch) and
run any writer variant over the SAME evidence, scoring RACE+FACT. Isolates the writer;
iterate in minutes. `collect` (once) → `score --all` (compare variants). Complements a
larger N (≥10) headline sweep for the breadth work.

## FACT-recovery techniques worth trying (ranked)
- **Quote-tight per span** (implemented `section_faithful`) — cheapest; the flat writer
  proves verbatim → 35%.
- **Post-hoc support filter (SelfCite 2502.09604 / P-Cite 2509.21557):** after writing,
  drop a citation if its span doesn't entail the sentence (context-ablation reward, or a
  lightweight overlap check against the verbatim bank span — no re-fetch).
- **Paragraph-granularity citation** (2604.01432) — cite the span SET a paragraph draws
  from rather than one-per-sentence.
- **Faithful-by-construction Extract–Select–Rewrite** (CAMS 2606.23989) — atomic claims
  with provenance as the unit of attribution.

## Open-source references to borrow
WebResearcher (open WebWeaver), langchain-open-deep-research (RACE 43.44, Ollama-ok),
DeerFlow (ByteDance), Deep Literature Survey iterative workflow.

## Sources (read in full this pass)
- arXiv:2604.01432 Are Finer Citations Always Better? (granularity)
- arXiv:2604.24978 Don't Stop Early (objective outline + termination; DR-Bench ablation)
- Survey scan: 2606.20122, 2602.13830, 2511.18743, 2510.21900, 2507.16075, 2502.09604,
  2509.21557, 2606.23989, 2408.04568 (FRONT), 2409.02897 (LongCite).
