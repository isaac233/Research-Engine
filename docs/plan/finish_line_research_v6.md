# Finish-Line Research v6 — Beating the Task-53 Challenge Class (vague queries + sparse/PDF evidence + faithfulness)

**Date:** 2026-07-17
**Motivation:** After the CDP 403-recovery lever, task 53 ("how the world's wealthiest
governments invest") reached RACE 32.68 / FACT 32.5% — still ~6 RACE and ~40 FACT points
behind task 52 ("investment philosophies of Duan Yongping, Buffett, Munger": 38.64 / 72.5%).
The gap is **not** intrinsic to the query and must not be treated as an excuse. It is a
**solvable challenge class** the engine must master: *broad/underspecified queries whose
authoritative evidence is sparse, paywalled, or PDF-locked.* This doc distills SOTA strategies
(grounded in current papers) and maps each to a concrete, env-gated lever in our codebase.

---

## 1. Diagnosis — what task 53 has that task 52 doesn't

| Axis | Task 52 (easy) | Task 53 (hard) | The transferable challenge |
|---|---|---|---|
| **Query specificity** | 3 named entities | 1 vague sentence, ambiguous scope | Must **scope + enumerate entities** autonomously |
| **Evidence location** | quotable public prose (letters, interviews) | SWF annual-report **PDFs**, data portals, paywalled press | Must **ingest PDFs + reach data portals** |
| **Verifiability** | cites verify (82→29 eff) | loose bank, many cites fail (76→13 eff) | Must **abstain on unsupported cites** |
| RACE/FACT | 38.64 / 72.5% | 32.68 / 32.5% | close both |

All three reduce to: **the query never gets scoped into concrete, fetchable, verifiable
sub-targets, and the writer cites faster than the evidence can support.**

---

## 2. SOTA strategies (grounded) → our levers

### Challenge A — Vague / underspecified queries
The current path (`query_decomposer.plan_objectives` → `react_planner` → `OutlineBuilder`)
derives objectives from the raw query, then organizes *whatever was banked* → topic drift +
weak instruction-following. SOTA fixes this by **scoping before search**.

- **ADORE** (arXiv:2601.18267, **#1 on DeepResearch Bench, RACE 52.65**): a *Grounding Agent*
  converts an underspecified prompt into a concrete brief with explicit scope assumptions
  **autonomously** (no user clarification), then a *Planning Agent* emits sections + success
  criteria.
- **RhinoInsight** (arXiv:2511.18743, RACE 50.92): a *Verifiable Checklist* built from the
  query **alone** (no evidence): ambiguous/underspecified checks trigger "plan intents" that
  fix scope, definitions, and acceptance criteria; a critic splits/merges outline nodes and
  binds each check to a node. → every sub-goal is well-defined and acceptance-ready **before**
  retrieval.
- **Entity Set Expansion** (SetExpan 1910.08192; LM-probing 2004.13897; UltraWiki 2403.04247):
  turn a semantic class ("wealthiest governments") into a concrete seed→expanded entity list
  (Norway GPFG, ADIA, CIC, SAFE, GIC, KIA, PIF, Temasek, HKMA, QIA…). Entity-rich queries also
  favor **sparse/BM25** retrieval (EntityQuestions 2109.08535) — which is exactly SearXNG.

→ **Lever S1 — Query-grounding brief.** One pre-search LLM call (in/near `plan_objectives`)
that emits `{scope, definitions, entities[], per_section_checklist[]}`. Env-gated. Seeds the
existing `seeded_outline`.
→ **Lever S2 — Entity-seeded objectives.** Expand the enumerated entities + cross-cutting
themes (asset allocation, governance, returns, geography) into concrete objectives → concrete,
fetchable serp queries ("Norway GPFG asset allocation 2024 annual report").

### Challenge B — Sparse / paywalled / PDF-locked evidence
`_fetchable_ref` and `read_fn` (orchestrator.py:1096, 1127) **drop every `.pdf` and `doi.org`**.
For task 53 the authoritative evidence *is* PDFs (nbim.no reports, IE SWF 2024 report) and data
portals (globalswf.com/ranking, ifswf.org, swfinstitute.org) — all reachable.

- **We already have `extraction/pdf_converter.py::PDFConverter.convert_bytes`** (pdfplumber +
  pypdf fallback, tables included) — **built and unwired.** Dropping PDFs is leaving the single
  richest source for this query class on the floor.
- **FinSage** (arXiv:2504.14493, 92.5% recall on financial filings): financial PDFs need
  table→text rewriting, section-summary metadata per chunk, and **HyDE query expansion +
  sparse-dense multi-path retrieval**.
- **Query expansion**: Query2doc (2303.07678), HyDE (2212.10496), GAR (2009.08553), GRF
  (2304.13157) all lift sparse/BM25 recall by expanding the query with an LLM pseudo-answer or
  domain terms — directly usable in `summary_feedback.refine_query`.

→ **Lever S3 — PDF ingestion (highest-ROI fetchability fix).** Stop dropping `.pdf`; route PDF
URLs' bytes through `PDFConverter.convert_bytes` in the react read path. Size/time-capped.
→ **Lever S4 — LLM query expansion in `refine_query`/`search_fn`** (Query2doc/HyDE-style).
→ **Lever S5 — Fetchability-aware serp rerank + portal priors.** Boost known data portals,
deprioritize known-paywalled hosts (sciencedirect, wsj, ft) for the query class.
→ **Lever S6 — CDP 403-recovery (DONE this session).** Keep; raise per-objective retries.

### Challenge C — Citation faithfulness on loose evidence
Task 53 emitted 76 cite markers but only 13 verified. The writer cites faster than the (thin)
bank supports.

- **ADORE Memory-locked synthesis**: each section is written using **only** its section-scoped
  *admissible* evidence set (a claim–evidence graph) → traceability by construction → cites
  verify. Plus **evidence-coverage-guided execution**: audit each section's support; under-
  supported sections trigger *targeted* follow-up retrieval before writing.
- **Attribute-or-Abstain** (arXiv:2407.07799): score each cited claim's evidence with a cheap
  NLI checker (**Minicheck / TRUE**); **abstain** (drop the cite or soften the claim) when
  support is low. Small prompted models (ours) benefit from **post-hoc** attribution (P-Cite),
  confirming our existing paradigm; the missing piece is the *abstain gate*.
- We already have `synthesis/verify_citations.py` and `verify_regen.py`. The prior verify-regen
  attempt measured negative because span-entailment ≠ the page-level FACT judge — this time
  build an **NLI-scored abstain gate** (drop unverifiable cites) aligned to FACT's granularity,
  not a regeneration pass.

→ **Lever S7 — Section-scoped (memory-locked) writing** (ADORE): writer may cite only its
section's admissible spans.
→ **Lever S8 — Attribute-or-Abstain NLI gate**: post-hoc, drop/soften cites whose span fails a
cheap NLI check. Directly lifts FACT precision.
→ **Lever S9 — Evidence-coverage audit → targeted re-retrieval** for under-supported sections
(closes task 53's dropped dimensions).

---

## 3. Prioritized build plan (highest ROI first)

| # | Lever | Fixes | Effort | Expected impact | Code touchpoints |
|---|---|---|---|---|---|
| 1 | **S1 grounding brief + S2 entity-seeded objectives** | vague-query drift (IF/comp/insight) + concrete fetchable queries | M | biggest RACE lever for this class | `discovery/query_decomposer.py::plan_objectives`, react seeded_outline |
| 2 | **S3 PDF ingestion** | sparse fetchable evidence (FACT + comp) | S (converter exists) | biggest FACT/comp lever for this class | `orchestrator._fetch_page_text`/`_fetchable_ref`, `extraction/pdf_converter.py` |
| 3 | **S8 Attribute-or-Abstain NLI gate** | FACT precision (13→ up) | M | direct FACT lift on any bank | `synthesis/verify_citations.py`, new NLI checker |
| 4 | **S4 query expansion + S5 fetchability rerank** | retrieval recall | S–M | incremental spans on sparse topics | `summary_feedback.refine_query`, react `search_fn` |
| 5 | **S7 memory-locked writing + S9 coverage audit** | structural faithfulness + coverage | L (ADORE-style) | highest ceiling; stage last | `react_planner`, `section_writer`, evidence bank |

**Method discipline:** all levers env-gated + default-off (linear path untouched); TDD;
measure each on **task 53 specifically** (the surface that exhibits the failure — cache/easy-
task A/Bs are the wrong instrument, per prior [[diagnose-before-escalate]] lesson), same
winning env + kimi judge, `engine.jsonl`/`scores.jsonl` archived + serp purged before each run.
Target: task 53 RACE/FACT → task 52 parity (≈38 / ≈70), which lifts the N=3 mean toward the
40.67 bar.

---

## 4. Key references
- ADORE — Orchestrating Specialized Agents for Trustworthy Enterprise RAG (arXiv:2601.18267) — **#1 DRB, memory-locked synthesis + evidence-coverage execution**
- RhinoInsight (arXiv:2511.18743) — verifiable checklist from query alone; evidence audit
- WebWeaver (arXiv:2509.13312) — dynamic outline / OEDR (our north star)
- Attribute or Abstain (arXiv:2407.07799) — abstain gate via NLI evidence-quality
- Generation-Time vs Post-hoc Citation (arXiv:2509.21557) — P-Cite for small models
- FinSage (arXiv:2504.14493) — financial-filing RAG: PDF/table handling + HyDE
- Query2doc (2303.07678) / HyDE (2212.10496) / GAR (2009.08553) — LLM query expansion
- Entity Set Expansion: SetExpan (1910.08192), LM-probing (2004.13897), UltraWiki (2403.04247)
- Cited but Not Verified (arXiv:2605.06635) — source-attribution eval for DR agents
- Domain data (fetchable HTML): globalswf.com/ranking, ifswf.org, nbim.no, swfinstitute.org
