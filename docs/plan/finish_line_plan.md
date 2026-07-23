# Finish-Line Plan: Beat Opus on DeepResearch Bench (WebWeaver restructure)

## Overview
The RACE ~21 / FACT ~20% gap vs Claude-3.7 (40.67 / 93.68%) is architectural, not model-capacity (confirmed: `--quality 1.0` gave no lift). This plan restructures the linear `SCREEN→EXTRACT→SYNTH` stages into the proven WebWeaver dual-agent architecture (Planner + Writer + Evidence Memory Bank + dynamic outline + "Attribute First, then Generate" sentence-level citation), enabled by grammar-constrained decoding. It reuses the existing discovery/enricher/extraction/bench assets and preserves the adversarial/evaluation/honesty machinery. Every phase re-measures with the trustworthy `kimi-k2.7-code:cloud` judge and diffs the scorecard. Research basis: `docs/plan/finish_line_research.md`.

## Baseline and Target (kimi judge, the only trustworthy instrument)
| | RACE | Comp | Depth | Inst | Read | FACT c_acc | E.Cit |
|---|---|---|---|---|---|---|---|
| Engine (baseline, N=3) | 21.48 | 19.89 | 17.97 | 23.01 | 30.71 | 20.4% | 1.33 |
| **Claude-3.7 bar (DoD)** | **40.67** | 38.99 | 37.66 | 45.77 | 41.46 | **93.68%** | 32.48 |
| WebWeaver on Qwen3-30B-A3B (proof it's achievable, local MoE) | 46.77 | — | — | — | — | ~93% (Sonnet-4) | ~200 |

**Definition of Done:** on a **10+ task kimi-judged sweep** (`research-engine bench --tasks 10 --judge ollama --judge-model kimi-k2.7-code:cloud`), **RACE > 40.67 AND FACT c_acc > ~90%**, driven by a local lane (`qwen3.6-27b`/`gemma4` class), frontier only as fallback. Anti-cover-up honesty flags remain wired; mypy strict + ruff clean; files < 800 lines; immutable dataclasses; TDD throughout.

## Architecture Mapping (restructure, not rewrite)
| Existing asset | New role |
|---|---|
| `discovery/pipeline.py` + `sources/serp.py` (SearXNG live) | Planner `search` tool |
| `screening/enricher.py::enrich_snippets` (fetches web pages) | Stage 1 of two-stage URL→page filter |
| `extraction/llm_extractor.py` (verbatim-span substring guard) | Evidence extractor → Memory Bank content + attribution source |
| `extraction/structured.py::ExtractedSource.claims[].evidence` | Verbatim spans, keyed into the bank by evidence ID + HTML URL |
| `synthesis/synthesizer.py` (free-form + post-hoc guard) | **Replaced** by Writer (section-by-section, attribute-first) |
| `synthesis/grounding.py::ground_citations` | Retired from the write path (post-hoc; superseded by built-in attribution) |
| `llm/ollama_client.py` | Add structured-output (`format`/GBNF) decoding |
| `llm/provider.py::LLMProvider` | Add `complete_structured(...)` with prompt-based default (model-agnostic) |
| `bench/` + `kimi-k2.7-code:cloud` | Per-phase measurement loop |
| `config/model_lanes.yaml` + `lane_roster.py` | `online_a` (qwen3.6-27b) → Planner lane; `synth_a` → Writer lane |

## Highest-ROI first phase + cheapest falsifying experiment
- **Highest-ROI phase: Phase 1 (Evidence Memory Bank + Attribute-First Writer).** FACT is the largest gap (20% vs 94%) and the citation mechanism is the single cheapest thing to prove because the engine **already produces verbatim evidence spans** and already fetches HTML pages. It isolates the FACT lever before any planner build-out.
- **Cheapest experiment (Task 1.0, the falsification spike):** WITHOUT building the planner, build a minimal Memory Bank from the **existing** extracted spans on the current sources, swap ONLY the writer to attribute-first sentence generation citing the **HTML-verifiable landing page** (not PDF/DOI), and re-measure FACT on the same 3 tasks. **Order gate: FACT c_acc must rise from ~20% to ≥ 40% (2× baseline).** If it does not, the "attribute-first fixes citation" premise is falsified cheaply — STOP and reassess before building Planner/Writer. This runs in one work session + one bench run.

---

## Phase 1 — Evidence Memory Bank + Attribute-First Writer (FACT lever)
**Goal:** Replace free-form synth with sentence-level attribution grounded in verbatim spans that resolve to HTML pages the FACT verifier can re-read. Prove the mechanism before scaling.

| # | Task | Files | Acceptance Criteria (target metric) | Complexity | Deps |
|---|---|---|---|---|---|
| 1.0 | **Falsification spike.** Minimal `EvidenceBank` from existing `ExtractedSource.claims[].evidence`; minimal attribute-first writer; wire behind `--writer attribute_first` flag; run 3-task kimi bench. | `memory/evidence_bank.py`, `synthesis/attribute_writer.py` (spike), `main.py` flag | **GATE: FACT c_acc ≥ 40% on the 3-task set** (was 20.4%). Else STOP + reassess. | Medium | none |
| 1.1 | Define `EvidenceSpan` (id, verbatim_text, source_url, source_title, section, confidence) + `EvidenceBank` (add/get-by-id, group-by-section, keyed by evidence ID **and** HTML URL). Immutable dataclasses. | `memory/evidence_bank.py`, `tests/unit/memory/test_evidence_bank.py` | TDD: add→get-by-id round-trips; duplicate spans dedupe; JSON round-trip; unmatched-substring spans rejected on insert. | Low | 1.0 |
| 1.2 | HTML-verifiable URL preference. When a span's source has a PDF/DOI and a readable landing page, key the span to the **landing page**; flag PDF/DOI-only spans `unverifiable_url`. Reuse `synthesizer.source_url` precedence, inverted to prefer HTML. | `memory/evidence_bank.py`, `discovery/resolver.py` (read landing URL) | Spans whose only URL is a PDF/DOI are labeled; a bench task's cited URLs are HTML where a landing page exists. FACT auto-fail rate on PDFs drops. | Medium | 1.1 |
| 1.3 | Attribute-First Writer: (a) content selection = pull spans for the query; (b) sentence planning = cluster spans (grammar-constrained JSON: cluster→sentence intent); (c) generate each sentence conditioned ONLY on its cluster's spans + preceding sentences; citation `[id]` built-in. Locate-by-substring guard drops unmatched (reuse `_verify_claims` pattern). | `synthesis/attribute_writer.py`, `tests/unit/synthesis/test_attribute_writer.py` | TDD: every emitted sentence carries ≥1 `[id]` resolving to a bank span; a sentence with no locatable span is omitted, not hallucinated; deterministic at temp 0. | High | 1.1, 1.2 |
| 1.4 | Wire writer into `_run_evaluate` as the brief producer when the bank is populated; keep `Reporter` fallback; keep `drop_failed_claims`. Retire `ground_citations` from this path (attribution is built-in). Preserve `screening_yielded_zero/offtopic` flags. | `orchestrator.py`, `main.py` | Existing suite green; brief renders References from bank; honesty flags intact; no post-hoc lexical guard on the write path. | Medium | 1.3 |
| 1.5 | Re-measure N=3 then N=5 kimi. Record scorecard diff vs baseline in HANDOFF. | `bench/`, `HANDOFF.md` | **FACT c_acc ≥ 60% AND E.Cit ≥ 5** at N=5 (directional). RACE not regressed below 21. | Low | 1.4 |

**Order gate:** 1.0 (GATE ≥40%) → 1.1 → 1.2 → 1.3 → 1.4 → 1.5 (GATE FACT ≥60%). Do not start Phase 2 until 1.5 passes — a broken citation mechanism makes planner breadth worthless.

---

## Phase 2 — Grammar-Constrained Decoding Foundation (reliability enabler)
**Goal:** Every agentic step emits schema-valid JSON so small models act reliably. This is the prerequisite that makes the Planner's multi-step ReAct loop trustworthy.

| # | Task | Files | Acceptance Criteria | Complexity | Deps |
|---|---|---|---|---|---|
| 2.1 | Add `complete_structured(messages, schema, model, temperature)` to `LLMProvider` ABC with a **prompt-based default** (embed schema in prompt + parse) so non-Ollama providers still satisfy the interface (model-agnostic). | `llm/provider.py`, `tests/unit/llm/test_structured.py` | ABC compiles; default impl returns parsed dict or raises `SchemaError`. | Low | — |
| 2.2 | Implement Ollama structured outputs: pass JSON Schema via `format` (llama.cpp GBNF) in the `/api/chat` payload; temperature 0. | `llm/ollama_client.py` | Live: a 3-field schema returns valid JSON on `qwen3.6-27b` and `gemma4:12b` with >99% validity across 50 calls. | Medium | 2.1 |
| 2.3 | Validator + repair-with-verifier wrapper: validate against schema; on failure, one repair round-trip; on second failure, escalate to frontier fallback or return typed error (never silently fabricate). | `llm/structured.py`, tests | TDD: malformed→repair→valid; unrepairable→typed error surfaced (honesty). | Medium | 2.2 |
| 2.4 | Retrofit Phase-1 writer's sentence-cluster step + `llm_extractor` evidence extraction to use `complete_structured`. | `synthesis/attribute_writer.py`, `extraction/llm_extractor.py` | Both paths schema-valid; existing tests green; extraction JSON-parse fallback removed where constrained path active. | Medium | 2.3, 1.3 |
| 2.5 | Re-measure N=5 kimi (regression guard — no metric drop from constraining). | `bench/`, `HANDOFF.md` | FACT + RACE within noise of Phase 1.5; validity errors ~0. | Low | 2.4 |

**Order gate:** 2.1 → 2.2 → 2.3 → 2.4 → 2.5.

---

## Phase 3 — Planner Agent (ReAct: search / write_outline / terminate)
**Goal:** Dynamic research cycle that interleaves evidence acquisition with outline optimization — lifts RACE Comprehensiveness/Depth (more effective citations → more coverage) and FACT abundance.

| # | Task | Files | Acceptance Criteria (target metric) | Complexity | Deps |
|---|---|---|---|---|---|
| 3.1 | `Outline` dataclass: ordered sections, each with `title`, `intent`, `evidence_ids: list[str]`. Immutable; JSON round-trip. | `planning/outline.py`, tests | TDD: add/reorder/expand sections; cite evidence IDs; validation rejects unknown IDs. | Low | 1.1 |
| 3.2 | Two-stage URL filter. Stage 1: constrained-decode select relevant URLs from SearXNG titles/snippets. Stage 2: fetch page (reuse `enrich_snippets` fetch path + `URLPolicy`/robots/SSRF), then (a) distill query-relevant summary, (b) extract verifiable evidence spans → `EvidenceBank`. | `planning/url_filter.py`, reuse `screening/enricher.py`, `extraction/llm_extractor.py` | TDD: N URLs in → k selected (constrained) → k pages fetched → spans banked with HTML URLs; policy-blocked URLs skipped; failures non-fatal. | High | 2.4, 3.1 |
| 3.3 | Planner ReAct loop. Actions via constrained decoding: `search(query)` → 3.2; `write_outline(ops)` → refine/expand/restructure + populate section `evidence_ids`; `terminate()` when outline comprehensive + well-supported. Bounded max cycles + Loop Safety (checkpoint, hard-stop on thrash). | `planning/planner_agent.py`, tests | TDD: mock provider drives search→write_outline→terminate; outline sections cite banked IDs; loop halts on max cycles / no-progress; only summaries (not raw spans) held in planner context. | High | 3.2 |
| 3.4 | Planner lane = `online_a` (qwen3.6-27b, MoE tolerates offload). Wire `lane_roster.lane_for_role("planner")`; frontier fallback on constrained-decode failure. | `planning/planner_agent.py`, `main.py`, `config/model_lanes.yaml` | Live: planner runs on qwen3.6-27b via lifecycle switch; one model resident. | Medium | 3.3 |
| 3.5 | Measure planner in isolation on 3 tasks (outline + bank populated; use Phase-1 writer over the outline's flat span set). | `bench/`, `HANDOFF.md` | **E.Cit ≥ 15 and RACE Comp ≥ 28** (toward reference breadth); FACT not regressed. | Medium | 3.4 |

**Order gate:** 3.1 → 3.2 → 3.3 → 3.4 → 3.5 (GATE E.Cit ≥ 15).

---

## Phase 4 — Writer Agent (ReAct: retrieve / write / terminate), section-by-section
**Goal:** Sequential per-section writing with targeted per-section evidence retrieval → high citation accuracy + comprehensiveness + readability simultaneously, at reference-report length (20k+ tokens).

| # | Task | Files | Acceptance Criteria (target metric) | Complexity | Deps |
|---|---|---|---|---|---|
| 4.1 | Writer ReAct loop over the dynamic outline: for each section, `retrieve(section.evidence_ids)` → ONLY that section's spans; `write` using the Phase-1 attribute-first mechanism; `terminate` when all sections done. Sequential (NOT parallel — parallel loses coherence). | `synthesis/writer_agent.py`, tests | TDD: section i writes only from its retrieved spans + preceding text; no cross-section span bleed; every sentence attributed. | High | 3.1, 2.4, 1.3 |
| 4.2 | Length/depth budget: writer targets reference-comparable length; per-section token budget from quality slider / lane `num_ctx`. Memory-bank retrieval keeps only short summaries in writer context (defeats "lost in the middle"). | `synthesis/writer_agent.py`, `config` | Brief length approaches reference scale without context overflow; deterministic. | Medium | 4.1 |
| 4.3 | Writer lane = `synth_a`; lifecycle switch after planner (evict planner, load writer — one resident). | `synthesis/writer_agent.py`, `main.py` | Live: planner→writer VRAM handoff, no stacking. | Medium | 3.4, 4.1 |
| 4.4 | Measure full Planner→Writer on 5 tasks kimi. | `bench/`, `HANDOFF.md` | **RACE ≥ 35 AND FACT c_acc ≥ 80% AND E.Cit ≥ 25** (approaching the bar). | Medium | 4.3 |

**Order gate:** 4.1 → 4.2 → 4.3 → 4.4 (GATE RACE ≥ 35 / FACT ≥ 80%).

---

## Phase 5 — Orchestrator Integration (new WEBWEAVE path, preserve honesty/adversarial)
**Goal:** Fold Planner+Writer into the campaign lifecycle, replacing SCREEN/EXTRACT/SYNTH while keeping ADVERSARIAL/EVALUATE/monitoring/storage and every anti-cover-up flag.

| # | Task | Files | Acceptance Criteria | Complexity | Deps |
|---|---|---|---|---|---|
| 5.1 | Add stages `PLAN_RESEARCH` (Planner) + `WRITE` (Writer) or repurpose `SCREEN/EXTRACT/EVALUATE` handlers; route DISCOVER output into the Planner's `search` seed. Feature-flag the path (`--pipeline webweave`) for A/B vs legacy. | `orchestrator.py`, `state.py` (stage enum), `main.py` | Both pipelines runnable; STAGE_ORDER updated; resume/pause/kill still work. | High | 4.3 |
| 5.2 | Keep ADVERSARIAL (`Devil`/`Verifier`) over the writer's attributed brief; `drop_failed_claims` before deliver; preserve `screening_yielded_zero/offtopic` + new `planner_found_no_evidence` honesty flag. | `orchestrator.py`, `adversarial/*` | Adversarial runs on new brief; unsupported sentences stripped; empty-evidence campaigns flagged not faked. | Medium | 5.1 |
| 5.3 | Telemetry/agent-history for planner cycles + writer sections (model_event, lane switches, evidence counts). Persist Memory Bank + Outline to campaign meta (redacted URLs). | `orchestrator.py`, `monitoring/telemetry.py`, `storage/*` | Status snapshot shows planner/writer models + evidence count; audit log records actions. | Medium | 5.1 |
| 5.4 | Full end-to-end campaign live on the SearXNG stack (Podman); verify deliverable `Research/<slug>/*_Insights.MD`. | e2e test, live run | E2E green (mocked sources) + one live campaign delivers attributed brief. | Medium | 5.2, 5.3 |

**Order gate:** 5.1 → 5.2 → 5.3 → 5.4.

---

## Phase 6 — Certification Sweep + Tuning (beat the bar)
**Goal:** Prove RACE > 40.67 AND FACT c_acc > ~90% on 10+ tasks; tune to close residuals.

| # | Task | Files | Acceptance Criteria (DoD) | Complexity | Deps |
|---|---|---|---|---|---|
| 6.1 | 10-task kimi sweep, archive `bench/out/*.jsonl` first (resume-cache gotcha), purge `data/cache.db` serp rows if blocklist changed. | `bench/`, `HANDOFF.md` | Scorecard vs bar recorded; weakest dim identified. | Low | 5.4 |
| 6.2 | Tune to the weakest dimension: if FACT < 90% → tighten span↔sentence binding + HTML-URL preference; if RACE Comp/Depth low → raise planner search cycles / evidence volume; if Read low → writer coherence prompt. Re-measure each change (no unmeasured wins). | planner/writer configs | Each lever measured; only kept if it moves the metric. | High | 6.1 |
| 6.3 | 20-task confirmation sweep + frontier-judge cross-check (optional) for stability. | `bench/` | Stable across 20 tasks (variance understood). | Medium | 6.2 |
| 6.4 | **DoD certification:** RACE > 40.67 AND FACT c_acc > ~90% on ≥10 tasks, local-lane driven. Update HANDOFF + memory; open PR. | `HANDOFF.md`, PR | Both thresholds met and reproduced; honesty flags intact; mypy+ruff clean. | Low | 6.3 |

**Order gate:** 6.1 → 6.2 → 6.3 → 6.4.

---

## Cross-cutting protocols
- **Measurement (MUST every phase):** `research-engine bench --tasks N --judge ollama --judge-model kimi-k2.7-code:cloud`; archive prior `bench/out/*.jsonl`; diff scorecard vs the RACE ~21 / FACT ~20% baseline; no unmeasured "wins." Session ops: `podman machine start` → `cd beta/search-infra && podman-compose up -d searxng whoogle` → export `RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'`.
- **Honesty (MUST):** attribute-first drops sentences whose spans can't be located (extends the existing substring guard); constrained-decode validator escalates on failure rather than fabricating; `screening_yielded_zero/offtopic` + new `planner_found_no_evidence` flags preserved; never ship an empty/thin brief as a green check.
- **Constraints:** TDD (RED→GREEN), mypy strict, ruff clean, files < 800 lines, immutable dataclasses, model-agnostic LLM interface (`complete_structured` has a prompt-based default), URL/robots/SSRF policy intact, local-first with frontier fallback only.

## Risks and Mitigations
- **Spike gate fails (FACT < 40% at 1.0):** premise falsified cheaply → reassess whether the bottleneck is span quality vs the writer before building Planner/Writer. (This is the point of Task 1.0.) Load-bearing caveat (~75% confidence): the 1.0 gate assumes existing spans are high-quality and most FACT failures are attribution/PDF-URL problems, not span-quality problems. A 30-40% spike = "proceed but front-load 3.2 (page-level evidence extraction)," not a hard stop.
- **Small model can't drive the ReAct loop reliably:** mitigated by Phase 2 constrained decoding first; frontier fallback on repeated schema failure.
- **Planner breadth inflates E.Cit but not accuracy:** measure FACT c_acc alongside E.Cit at every gate; HTML-URL preference (1.2) keeps cites verifiable.
- **VRAM stacking on planner→writer→extract switches:** reuse `ModelLifecycleManager` (one resident) already wired at `_switch_lane`.
- **Benchmark leakage / PDF auto-fail:** keep `RESEARCH_ENGINE_SERP_BLOCKLIST`; prefer HTML landing pages (1.2); purge cache.db serp rows on blocklist change.

## Success Criteria (DoD checklist)
- [ ] Task 1.0 gate: FACT ≥ 40% (mechanism proven) before any planner build
- [ ] Evidence Memory Bank keyed by evidence ID + HTML URL, spans verbatim-guarded
- [ ] Attribute-first Writer: every delivered sentence carries a locatable `[id]`
- [ ] Grammar-constrained decoding on every agentic step, >99% schema validity
- [ ] Planner ReAct (search/write_outline/terminate) with two-stage URL filter, local lane
- [ ] Writer ReAct (retrieve/write/terminate) sequential, per-section evidence
- [ ] Integrated path preserves adversarial/evaluation/honesty flags
- [ ] **10+ task kimi sweep: RACE > 40.67 AND FACT c_acc > ~90%, local-lane driven**
- [ ] mypy strict + ruff clean; files < 800 lines; TDD coverage ≥ 80%
