# Research Engine — Master Implementation Plan

**Project:** `C:\Users\Isaac\OneDrive\Desktop\beta\Research Engine`  
**Primary language:** Python 3.12+ (polyglot micro-tools allowed where they win).  
**Core constraint:** Model-agnostic; local Ollama/Gemma is the default driver, but every interface must accept provider swaps without rewrites.  
**Inspiration:** Router/evaluation pattern proven in `C:\Users\Isaac\OneDrive\Desktop\beta\Financial Model\Financial Model Training Data\.claude\router_eval\`.

---

## 1. Project Directory Tree

```
Research Engine/
├── .claude/
│   ├── agents/
│   │   ├── research-engine-router.md       # top-level firewall: routes to sub-routers
│   │   ├── discovery-router.md             # discovery + academic search router
│   │   ├── browser-router.md               # AI-only browser router
│   │   ├── extraction-router.md            # screening/extraction router
│   │   └── evaluation-router.md            # adversarial + eval/improvement router
│   ├── research-engine-routes.md           # learned routes log (R### itemized deltas)
│   ├── router_eval/
│   │   ├── README.md
│   │   ├── table_parser.py
│   │   ├── router_sim.py
│   │   ├── outcome_record.py
│   │   ├── capture_outcome.py
│   │   ├── gold_from_git.py
│   │   ├── run_benchmark.py
│   │   ├── fidelity_gate.py
│   │   ├── drift_check.py
│   │   ├── token_estimate.py
│   │   ├── measure_savings.py
│   │   ├── replay.py
│   │   └── test_log_robustness.py
│   └── settings.local.json
├── docs/
│   ├── plan/
│   │   ├── master_plan.md
│   │   ├── decisions/                      # ADRs only; one file per decision
│   │   └── weekly/
│   ├── architecture/
│   │   ├── browser.md
│   │   ├── orchestrator.md
│   │   ├── adversarial.md
│   │   └── evaluation.md
│   ├── runbooks/
│   │   ├── add_source.md
│   │   ├── deep_audit.md
│   │   └── incident_response.md
│   └── HANDOFF.md                          # living session handoff log
├── src/research_engine/
│   ├── __init__.py
│   ├── main.py                               # single entry point launched by main AI
│   ├── config.py
│   ├── orchestrator.py                       # campaign state machine
│   ├── state.py                              # SQLite/DuckDB campaign state
│   ├── events.py                             # append-only event bus
│   ├── llm/
│   │   ├── provider.py
│   │   ├── ollama_client.py
│   │   ├── anthropic_client.py
│   │   └── model_registry.yaml
│   ├── browser/
│   │   ├── ai_browser.py
│   │   ├── cdp_driver.py
│   │   ├── raw_http.py
│   │   ├── graphql_client.py
│   │   ├── robots.py
│   │   ├── fingerprint.py
│   │   └── policy.py                         # SSRF + ethical URL policy
│   ├── discovery/
│   │   ├── query_planner.py
│   │   ├── sources/
│   │   │   ├── serp.py
│   │   │   ├── semantic_scholar.py
│   │   │   ├── crossref.py
│   │   │   ├── arxiv.py
│   │   │   ├── openalex.py
│   │   │   └── web_crawl.py
│   │   ├── dedup.py
│   │   ├── snowball.py
│   │   └── resolver.py
│   ├── screening/
│   │   ├── criteria.py
│   │   ├── ranker.py
│   │   └── extractor.py
│   ├── extraction/
│   │   ├── markdownify.py
│   │   ├── pdf_converter.py
│   │   ├── structured.py
│   │   └── citation.py
│   ├── adversarial/
│   │   ├── devil.py
│   │   ├── verifier.py
│   │   └── challenge.py
│   ├── evaluation/
│   │   ├── harness.py
│   │   ├── reporter.py
│   │   ├── improvement.py
│   │   └── deep_audit.py
│   ├── monitoring/
│   │   ├── progress.py
│   │   ├── estimator.py
│   │   ├── calibrator.py
│   │   └── telemetry.py
│   ├── storage/
│   │   ├── sources_db.py
│   │   ├── cache_db.py
│   │   └── artifacts.py
│   └── cleanup/
│       ├── dedup_files.py
│       └── janitor.py
├── src/micro_tools/
│   ├── pdf_to_md/
│   ├── html_to_md/
│   └── graphql_probe/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
│   ├── launch.py
│   ├── github_pr.py
│   └── end_session.py
├── config/
│   ├── default.yaml
│   └── models.yaml
├── data/
│   ├── sources/
│   ├── cache/
│   └── deliverables/
├── pyproject.toml
├── README.md
└── HANDOFF.md
```

**Justification:** Every subsystem owns its vertical. Routers live under `.claude/agents/` exactly like the Financial Model project so the main AI can delegate before loading heavy context. The eval harness is isolated under `.claude/router_eval/` and imports nothing from `src/`. Storage defaults to SQLite for campaign state and DuckDB for source corpora because both compress well and are machine-readable. Source documents land as `.md` when possible; raw PDFs stay in `data/sources/<campaign>/<hash>/`.

---

## 2. Design Principles

1. **Main AI is the API surface.** The engine is launched by the main AI and reports back progress, ETA, and stage. The user should feel like Claude is doing the work.
2. **Primitive AI drives; frontier AI audits.** Local models run discovery, screening, and extraction. Opus/Kimi run adversarial deep audits and final insight synthesis.
3. **Adversarial by default.** Every research claim is challenged by a dedicated devil agent before it reaches the main AI.
4. **Non-self-poisoning memory.** Learned routes are itemized deltas (R###), provisional until confirmed, negative items re-tested, never wholesale rewritten.
5. **Ethical hard floor.** No credential bypass, no unauthorized access, no anti-bot evasion, no law breaking. "Stealth" means polite rotation, rate limiting, proper headers, robots.txt respect.
6. **Append-only state.** Every action produces a receipt. Nothing is deleted until the janitor explicitly prunes it at session end.
7. **Project-native deliverables.** When the engine is invoked inside another project, it writes human-readable results into a surface-level `Research/` folder owned by that project. Campaign outputs are differentiated by folder name so users and AI registry searches never confuse a campaign brief with the master brief.
8. **No dead ends.** If the main AI presents a blocker, missing resource, or an "I cannot find…" problem, the engine treats it as a research campaign and does not stop until it returns actionable solutions with sources, docs, and next steps. The engine is never allowed to give up and hand the problem back to the user.

---

## 3. Phase Plan

### Phase 0 — Scaffold (session 1)

**Goal:** A clean repo, a working GitHub remote, the router skeleton, the eval harness skeleton, and a living `HANDOFF.md`.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 0.1 | Create repo structure and `pyproject.toml`. | `pyproject.toml`, `README.md`, `.gitignore` | `pytest --collect-only` runs in an empty test suite; `ruff` passes on generated files. | Low | None |
| 0.2 | Initialize GitHub remote and protect `main`. | `.github/`, remote URL in `README.md` | `git remote -v` shows origin; `main` requires PRs via branch protection rule. | Low | 0.1 |
| 0.3 | Create top-level `research-engine-router.md` with layout, rename map, and keyword table. | `.claude/agents/research-engine-router.md` | Router can be invoked; returns `ROUTE:` schema for each subsystem. | Medium | 0.1 |
| 0.4 | Create sub-routers (`discovery-router.md`, `browser-router.md`, `extraction-router.md`, `evaluation-router.md`) with stub keyword tables and R### schema. | `.claude/agents/*.md` | Each router declares `ROUTE/EXECUTE/FROZEN EVAL` modes and learned-log path. | Medium | 0.3 |
| 0.5 | Create learned-routes log template. | `.claude/research-engine-routes.md` | File contains one seeded confirmed item per subsystem and empty `## RETIRED` section. | Low | 0.3 |
| 0.6 | Create `router_eval` harness skeleton: `table_parser.py`, `router_sim.py`, `capture_outcome.py`, `run_benchmark.py`, `drift_check.py`, `test_log_robustness.py`. | `.claude/router_eval/*.py` | Every module has an `if __name__ == "__main__"` self-check that passes. | Medium | 0.3 |
| 0.7 | Create `HANDOFF.md` template and end-of-session ritual. | `docs/HANDOFF.md`, `scripts/end_session.py` | Template has tables for "Done / Open / Blocked / Next / Risks". | Low | 0.1 |
| 0.8 | Seed `docs/plan/decisions/ADR-001-language-and-storage.md` and `ADR-002-router-pattern-port.md`. | `docs/plan/decisions/*` | Each ADR records the decision, alternatives rejected, and load-bearing assumption. | Low | 0.1 |
| 0.9 | Open Pull Request 1 and merge to `main`. | PR #1 | All Phase 0 files are on `main`; no dead branches remain. | Low | 0.2–0.8 |

**Order gate:** 0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6 → 0.7 → 0.8 → 0.9.

---

### Phase 1 — Core Orchestrator + Model-Agnostic LLM Layer (sessions 2–3)

**Goal:** The main program accepts a research request, spins up a campaign, and can call local and frontier models through a single interface.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 1.1 | Define `ResearchRequest` and `Campaign` dataclasses. | `src/research_engine/state.py` | Immutable dataclasses; JSON round-trip works; validation rejects empty queries. | Low | 0.1 |
| 1.2 | Implement SQLite campaign-state DB with append-only events. | `src/research_engine/state.py`, `src/research_engine/events.py` | Schema migration script exists; events table has `event_id`, `campaign_id`, `type`, `payload`, `timestamp`. | Medium | 1.1 |
| 1.3 | Build model-agnostic `LLMProvider` abstract base plus Ollama and Anthropic implementations. | `src/research_engine/llm/provider.py`, `src/research_engine/llm/ollama_client.py`, `src/research_engine/llm/anthropic_client.py` | Swap provider via `models.yaml`; Ollama ping test passes; Anthropic client validates key presence. | Medium | 0.1 |
| 1.4 | Create `model_registry.yaml` with provider constraints (context window, cost tier, rate limits). | `config/models.yaml` | Registry loaded at runtime; unknown model raises. | Low | 1.3 |
| 1.5 | Implement `Orchestrator`: campaign lifecycle, stage transitions, pause/resume/kill. | `src/research_engine/orchestrator.py` | Unit tests cover start → plan → run → pause → resume → finalize. | High | 1.2, 1.3 |
| 1.6 | Implement `main.py` CLI entry point: `research-engine run <query>`. | `src/research_engine/main.py`, `scripts/launch.py` | CLI parses query, creates campaign, prints campaign ID, exits with orchestrator status. | Low | 1.5 |
| 1.7 | Add telemetry hooks to the orchestrator. | `src/research_engine/monitoring/telemetry.py` | Every stage emits a telemetry event; no PII in payloads. | Medium | 1.5 |
| 1.8 | Update `research-engine-router.md` with Phase 1 keyword rows and R### deltas. | `.claude/agents/research-engine-router.md`, `.claude/research-engine-routes.md` | Router correctly routes "orchestrator", "models.yaml", and "campaign state" queries. | Low | 0.3, 1.6 |
| 1.9 | Run eval harness self-checks and open PR #2. | PR #2 | `pytest` passes; eval harness modules import cleanly. | Low | 1.1–1.8 |

**Order gate:** 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9.

---

### Phase 2 — AI-Only Browser (sessions 4–6)

**Goal:** A browser designed for AI: CDP/Playwright perception, raw HTTP/GraphQL/API paths, polite stealth, and an ethical URL policy.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 2.1 | Define `AIBrowser` interface and `BrowserAction` schema; include `unblocker` mode for problem-solving research. | `src/research_engine/browser/ai_browser.py` | Interface supports `fetch`, `click`, `fill`, `evaluate`, `snapshot`, `graphql`, `api`, `unblock`. | Medium | 1.3 |
| 2.2 | Implement CDP/Playwright driver with accessibility-DOM-first perception. | `src/research_engine/browser/cdp_driver.py` | Can fetch a page and return a semantic tree; headless by default; no human UI chrome. | High | 2.1 |
| 2.3 | Implement raw HTTP client with pooled sessions, backoff, jitter, and header rotation. | `src/research_engine/browser/raw_http.py` | 429/503 retried; 404 distinguished; respects `User-Agent` rotation list from config. | Medium | 2.1 |
| 2.3a | Add browser-based unblocking probe: given a blocker query, search public pages and APIs for concrete solutions, availability, and links. | `src/research_engine/browser/unblock_probe.py` | Returns ranked solution candidates with URLs and access terms; used by unblocking campaigns. | Medium | 2.3, 2.4 |
| 2.4 | Implement GraphQL and JSON API client helpers. | `src/research_engine/browser/graphql_client.py` | Can introspect a GraphQL endpoint and run a query; validates JSON responses. | Medium | 2.3 |
| 2.5 | Build robots.txt parser and policy enforcer. | `src/research_engine/browser/robots.py` | Blocks disallowed paths; caches robots.txt per host; logs allowed/disallowed decisions. | Medium | 2.1 |
| 2.6 | Build ethical URL policy and SSRF guard. | `src/research_engine/browser/policy.py` | Blocks private IP ranges, file://, localhost by default; logs every allow decision. | High | 2.3 |
| 2.7 | Implement legitimate fingerprint rotation (headers, TLS JA3, viewport) without deception. | `src/research_engine/browser/fingerprint.py` | Fingerprint rotates per request; no forged signatures or stolen credentials. | Medium | 2.3 |
| 2.8 | Integrate browser with orchestrator as a tool. | `src/research_engine/orchestrator.py` | Orchestrator can dispatch browser actions and store receipts. | Medium | 1.5, 2.2 |
| 2.9 | Add browser-router keyword rows and R### deltas. | `.claude/agents/browser-router.md`, `.claude/research-engine-routes.md` | Router routes "cdp", "playwright", "graphql", "robots" to the correct files. | Low | 0.4, 2.8 |
| 2.10 | Tests and PR #3. | PR #3 | Unit tests mock HTTP; integration test uses `httpbin.org` via raw HTTP only; unblock probe tested with a known public resource query. | Medium | 2.1–2.9 |

**Order gate:** 2.1 → 2.3 → 2.3a → 2.5/2.6 → 2.2 → 2.4 → 2.7 → 2.8 → 2.9 → 2.10.

---

### Phase 3 — Discovery + Academic Search (sessions 7–9)

**Goal:** Multi-source discovery, deduplication, citation snowballing, and full-text resolution. Inspired by SLR-Engine / pysyrev / synthscholar.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 3.1 | Implement query planner: decompose a research request into source-specific queries. | `src/research_engine/discovery/query_planner.py` | Input: natural-language request. Output: list of `(source, query, rationale, priority)`. | Medium | 1.1 |
| 3.2 | Implement Semantic Scholar source adapter. | `src/research_engine/discovery/sources/semantic_scholar.py` | Fetches papers by query; handles pagination; returns normalized `Paper` schema. | Medium | 2.3 |
| 3.3 | Implement Crossref, arXiv, and OpenAlex adapters. | `src/research_engine/discovery/sources/crossref.py`, `arxiv.py`, `openalex.py` | Each returns normalized `Paper`; rate limits respected. | Medium | 2.3 |
| 3.4 | Implement SERP / web-crawl adapter for non-academic sources. | `src/research_engine/discovery/sources/serp.py`, `web_crawl.py` | Uses raw HTTP or browser; respects robots.txt; no scraping behind paywalls. | High | 2.3, 2.5 |
| 3.5 | Build deduplication engine (title/DOI/URL fuzzy hash). | `src/research_engine/discovery/dedup.py` | Duplicate detection F1 > 0.90 on a hand-labeled sample of 50 pairs. | High | 3.2–3.4 |
| 3.6 | Build citation snowballing (forward/backward citations). | `src/research_engine/discovery/snowball.py` | Given a seed paper, expands to cited/citing papers up to configurable depth. | Medium | 3.2 |
| 3.7 | Build full-text resolver: map discovered paper to downloadable PDF or HTML. | `src/research_engine/discovery/resolver.py` | Uses Unpaywall, DOI, and open access checks; never downloads paywalled content without authorization. | High | 3.2–3.4 |
| 3.8 | Integrate discovery pipeline into orchestrator stage "DISCOVER". | `src/research_engine/orchestrator.py` | Stage runs query planner, adapters, dedup, snowball, resolver; stores results. | Medium | 1.5, 3.5, 3.7 |
| 3.9 | Update discovery-router and eval harness with source rows. | `.claude/agents/discovery-router.md`, `.claude/router_eval/*` | Benchmark runs against synthetic gold; F1 > 0.75 on predicted files. | Medium | 0.4, 3.8 |
| 3.10 | Tests and PR #4. | PR #4 | All source adapters have mocked unit tests; resolver test uses public-domain DOI. | Medium | 3.1–3.9 |

**Order gate:** 3.1 → 3.2 → 3.3 → 3.5 → 3.6 → 3.7 → 3.4 → 3.8 → 3.9 → 3.10.

---

### Phase 4 — Screening + Structured Extraction (sessions 10–12)

**Goal:** Screen sources against criteria, rank them, and extract structured insights plus full-text markdown.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 4.1 | Define reusable screening criteria schema. | `src/research_engine/screening/criteria.py` | Criteria can be boolean, numeric range, or LLM-rubric; YAML-loadable. | Low | 3.1 |
| 4.2 | Implement source ranker using criteria + local LLM scoring. | `src/research_engine/screening/ranker.py` | Ranks sources; returns scorecard; logs reasoning per source. | Medium | 4.1, 1.3 |
| 4.3 | Implement markdownify for HTML pages. | `src/research_engine/extraction/markdownify.py` | Converts HTML to readable Markdown; preserves headings, links, tables. | Medium | 2.3 |
| 4.4 | Implement PDF conversion pipeline (pdfplumber/marker fallback; keep original if corrupt). | `src/research_engine/extraction/pdf_converter.py`, `src/micro_tools/pdf_to_md/` | Converts PDF to `.md` when possible; flags corruption and keeps original + safe format. | High | 2.3 |
| 4.5 | Implement structured extraction: methodology, data, results, conflicts, citations. | `src/research_engine/extraction/structured.py`, `src/research_engine/extraction/citation.py` | Extracts JSON schema per paper; detects conflicts with user-provided data. | High | 4.3, 4.4 |
| 4.6 | Implement conflict detector for extracted claims vs. existing project data. | `src/research_engine/extraction/structured.py` | Flags discrepancies with evidence snippets; does not auto-dismiss. | Medium | 4.5 |
| 4.7 | Integrate SCREEN and EXTRACT stages into orchestrator. | `src/research_engine/orchestrator.py` | Orchestrator runs screening then extraction; stores structured outputs. | Medium | 3.8, 4.2, 4.5 |
| 4.8 | Update extraction-router and eval harness. | `.claude/agents/extraction-router.md`, `.claude/router_eval/*` | Benchmark covers extraction files. | Low | 0.4, 4.7 |
| 4.9 | Tests and PR #5. | PR #5 | Extraction tests run on public-domain PDF sample. | Medium | 4.1–4.8 |

**Order gate:** 4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6 → 4.7 → 4.8 → 4.9.

---

### Phase 5 — Adversarial Review + Evaluation/Improvement Apparatus (sessions 13–16)

**Goal:** Challenge the main agent, report on it, and improve the engine without self-poisoning. Inspired by hybridagents / agent-army / vnx-orchestration.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 5.1 | Implement `Devil` adversarial agent: challenges every insight for evidence, soundness, and coverage; in unblocking mode, challenges whether each solution actually solves the stated blocker. | `src/research_engine/adversarial/devil.py` | Takes a claim + sources; outputs challenge list with severity and requested evidence; blocker mode never accepts "no solution found". | High | 1.3 |
| 5.2 | Implement `Verifier`: re-runs the source lookups the main agent claims to have done. | `src/research_engine/adversarial/verifier.py` | Verifies URL reachability, quote presence, and DOI resolution; flags hallucinated citations. | High | 2.3, 4.5 |
| 5.3 | Implement `Challenge` dispatcher: routes challenged claims back to the main agent for response. | `src/research_engine/adversarial/challenge.py` | Ensures every challenge gets a response or an escalation to frontier model. | Medium | 5.1, 5.2 |
| 5.4 | Implement evaluation harness: compares campaign output to rubric and prior runs. | `src/research_engine/evaluation/harness.py` | Computes precision, recall, coverage, citation quality; stores results. | High | 4.7 |
| 5.5 | Implement evaluation reporter: generates a verifiable report for the main AI. | `src/research_engine/evaluation/reporter.py` | Report includes claims, evidence URLs, confidence, and requested fixes. | Medium | 5.4 |
| 5.6 | Implement improvement proposal pipeline: converts reports into concrete issues/R### deltas. | `src/research_engine/evaluation/improvement.py` | Proposes one itemized delta per issue; never auto-applies without confirmation. | Medium | 5.5 |
| 5.7 | Implement periodic deep-audit trigger and Opus/Kimi audit runner. | `src/research_engine/evaluation/deep_audit.py` | Triggered every N campaigns or on anomaly; audits eval harness, logs, and adversarial chain. | High | 5.1–5.6 |
| 5.8 | Integrate ADVERSARIAL and EVAL stages into orchestrator. | `src/research_engine/orchestrator.py` | Main extraction output is challenged before delivery; eval report is generated. | Medium | 4.7, 5.3, 5.5 |
| 5.9 | Update evaluation-router and eval harness with adversarial rows. | `.claude/agents/evaluation-router.md`, `.claude/router_eval/*` | Router routes "devil", "verifier", "deep audit" correctly. | Low | 0.4, 5.8 |
| 5.10 | Tests and PR #6. | PR #6 | Adversarial tests use synthetic hallucinated claims; deep-audit test uses stub frontier provider. | High | 5.1–5.9 |

**Order gate:** 5.1/5.2 → 5.3 → 5.4 → 5.5 → 5.6 → 5.7 → 5.8 → 5.9 → 5.10.

---

### Phase 6 — Monitoring + Self-Improving Telemetry (sessions 17–19)

**Goal:** Accurate progress %, ETA, stage descriptions, and continuous calibration from completed runs.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 6.1 | Implement progress tracker: stages × tasks with weights. | `src/research_engine/monitoring/progress.py` | Returns `0–100` progress; updates on every event. | Low | 1.2 |
| 6.2 | Implement time estimator: per-stage runtime prediction. | `src/research_engine/monitoring/estimator.py` | Predicts ETA using historical campaign data; falls back to conservative heuristic. | Medium | 6.1 |
| 6.3 | Implement calibrator: compares predicted vs. actual durations and adjusts stage weights. | `src/research_engine/monitoring/calibrator.py` | After each campaign, updates weights; MAPE decreases over 5+ runs. | High | 6.2 |
| 6.4 | Implement status reporter for main AI: progress %, ETA, stage, remaining steps. | `src/research_engine/monitoring/progress.py` | CLI `research-engine status <campaign_id>` prints the four fields. | Low | 6.1, 6.2 |
| 6.5 | Add telemetry dashboard (text/JSON) and anomaly detection. | `src/research_engine/monitoring/telemetry.py` | Detects stuck stages, thrashing, or repeated failures; raises alerts. | Medium | 6.1 |
| 6.6 | Integrate monitoring into orchestrator event bus. | `src/research_engine/events.py`, `src/research_engine/orchestrator.py` | Every stage transition updates progress/ETA. | Medium | 1.5, 6.4 |
| 6.7 | Update routers with monitoring rows; eval harness. | `.claude/agents/*-router.md`, `.claude/router_eval/*` | Benchmark covers monitoring files. | Low | 0.4, 6.6 |
| 6.8 | Tests and PR #7. | PR #7 | Calibration test simulates campaigns and checks weight updates. | Medium | 6.1–6.7 |

**Order gate:** 6.1 → 6.2 → 6.4 → 6.3 → 6.5 → 6.6 → 6.7 → 6.8.

---

### Phase 7 — Storage, Document Conversion, and Cleanup (sessions 20–22)

**Goal:** All source documents saved as `.md` or DB; corrupt files kept original; temp caches and duplicates cleaned every session.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 7.1 | Implement SQLite sources database: papers, web pages, campaigns. | `src/research_engine/storage/sources_db.py` | Schema supports full-text search via SQLite FTS5; migrations versioned. | Medium | 1.2 |
| 7.2 | Implement DuckDB corpora database for large extracted corpora. | `src/research_engine/storage/cache_db.py` | Stores raw text chunks and embeddings-friendly schema. | Medium | 1.2 |
| 7.3 | Implement artifact manager: writes deliverables to `data/deliverables/<campaign>/`. | `src/research_engine/storage/artifacts.py` | Names files by content hash; avoids duplicates. | Low | 7.1 |
| 7.4 | Harden document conversion pipeline with format detection and corruption handling. | `src/research_engine/extraction/pdf_converter.py`, `src/research_engine/extraction/markdownify.py` | If conversion corrupts, keep original + store `.txt` or safe format. | High | 4.4 |
| 7.5 | Implement end-of-session cleanup: deduplicate files, purge temp cache, vacuum DBs. | `src/research_engine/cleanup/dedup_files.py`, `src/research_engine/cleanup/janitor.py`, `scripts/end_session.py` | Removes identical files by hash; keeps at least one copy; logs deletions. | Medium | 7.3 |
| 7.6 | Integrate cleanup into orchestrator finalize stage. | `src/research_engine/orchestrator.py` | Finalize stage runs janitor; reports disk saved. | Low | 5.8, 7.5 |
| 7.7 | Update routers and eval harness. | `.claude/agents/*-router.md`, `.claude/router_eval/*` | Drift check passes; no stale paths. | Low | 0.6, 7.6 |
| 7.8 | Tests and PR #8. | PR #8 | Cleanup test creates duplicate files and verifies one remains. | Medium | 7.1–7.7 |

**Order gate:** 7.1/7.2 → 7.3 → 7.4 → 7.5 → 7.6 → 7.7 → 7.8.

---

### Phase 8 — Main Program Loop + Main AI Integration (sessions 23–25)

**Goal:** A single command the main AI can call to launch a campaign and query status.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---| ---|
| 8.1 | Implement main program loop: parse request → plan → discover → screen → extract → challenge → evaluate → deliver; detect blocker queries and dispatch unblocking campaigns. | `src/research_engine/main.py`, `src/research_engine/orchestrator.py` | Running `research-engine run "..."` completes a full campaign end-to-end; blocker queries trigger unblocking probe and deliver solutions. | High | 3.8, 4.7, 5.8 |
| 8.2 | Implement deliverable formatter: insight brief + evidence map for main AI; create `Research/` layout in host project with `<campaign>_Insights.MD` files and folded master `Research/Insights.MD`. | `src/research_engine/storage/artifacts.py`, `src/research_engine/main.py` | `Research/<campaign-slug>/<campaign-slug>_Insights.MD` exists; `Research/Insights.MD` aggregates all campaign briefs with a TOC. | Medium | 7.3 |
| 8.3 | Implement status query command for main AI. | `src/research_engine/main.py` | `research-engine status <id>` returns JSON or human summary. | Low | 6.4 |
| 8.4 | Implement kill/pause/resume commands. | `src/research_engine/main.py`, `src/research_engine/orchestrator.py` | Signals are persisted in state DB; campaign resumes correctly. | Medium | 1.5 |
| 8.5 | Add MCP/stdio adapter so Claude Code can call the engine as a tool. | `src/research_engine/mcp_adapter.py` | Exposes `research_engine_run` and `research_engine_status` tools. | Medium | 8.1, 8.3 |
| 8.6 | Write runbook: "How Claude Code launches the Research Engine". | `docs/runbooks/main-ai-integration.md` | Step-by-step with example prompts. | Low | 8.5 |
| 8.7 | Update top-level router with main-program rows. | `.claude/agents/research-engine-router.md`, `.claude/research-engine-routes.md` | Router routes "run research", "status", "kill" correctly. | Low | 0.3, 8.1 |
| 8.8 | E2E test: launch a toy research campaign on a public domain topic. | `tests/e2e/test_campaign.py` | Campaign completes; deliverable exists; no errors. | High | 8.1–8.7 |
| 8.9 | PR #9. | PR #9 | E2E test passes in CI. | Low | 8.8 |

**Order gate:** 8.1 → 8.2 → 8.3 → 8.4 → 8.5 → 8.6 → 8.7 → 8.8 → 8.9.

---

### Phase 9 — Hardening, Full Test Suite, GitHub/PR Automation (sessions 26–28)

**Goal:** Elite test coverage, automated PRs at end of every session, no dead branches.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 9.1 | Reach 80%+ unit test coverage. | `tests/unit/*` | `pytest --cov` reports ≥80%. | High | All prior phases |
| 9.2 | Reach integration test coverage for all source adapters. | `tests/integration/*` | Mocked external APIs; no paid calls in CI. | Medium | 3.10 |
| 9.3 | Add GitHub Actions CI: lint, type check, tests, eval harness self-check. | `.github/workflows/ci.yml` | CI green on PR. | Medium | 0.2 |
| 9.4 | Implement `scripts/github_pr.py`: creates branch, commits, pushes, opens PR. | `scripts/github_pr.py` | Can be invoked at session end; uses `GITHUB_TOKEN`. | Medium | 0.2 |
| 9.5 | Wire `scripts/end_session.py` to run cleanup, update `HANDOFF.md`, commit, and open PR. | `scripts/end_session.py`, `docs/HANDOFF.md` | End-of-session ritual runs in one command. | Medium | 7.5, 9.4 |
| 9.6 | Add branch protection, PR template, and issue templates. | `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/*` | Templates enforce test plan and risk note. | Low | 9.3 |
| 9.7 | Run full eval harness benchmark and document baseline scores. | `.claude/router_eval/README.md` | Baseline F1, token savings, and drift report recorded. | Medium | 0.6 |
| 9.8 | Security review: secrets scanning, dependency audit, SSRF tests. | `tests/security/*` | `security-reviewer` agent signs off; no hardcoded secrets. | High | 2.6, 9.1 |
| 9.9 | PR #10. | PR #10 | CI green; security review complete. | Low | 9.1–9.8 |

**Order gate:** 9.1/9.2 → 9.3 → 9.4 → 9.5 → 9.6 → 9.7 → 9.8 → 9.9.

---

### Phase 10 — Production Polish + Ship-Ready Packaging (sessions 29–30)

**Goal:** Documentation, runbooks, distribution, and a first shippable version.

| # | Task | Files | Acceptance Criteria | Complexity | Dependencies |
|---|---|---|---|---|---|
| 10.1 | Write comprehensive `README.md` with install, quickstart, and architecture overview. | `README.md` | New user can install and run one example campaign in <15 min. | Medium | 8.9 |
| 10.2 | Write `docs/architecture/*.md` for every subsystem. | `docs/architecture/*` | Each doc explains interfaces, invariants, and failure modes. | Medium | All prior |
| 10.3 | Create `config/default.yaml` with safe defaults and comments. | `config/default.yaml` | Defaults are conservative (low rate limits, no paid APIs). | Low | 1.4 |
| 10.4 | Build distribution package: `pip install -e .` works. | `pyproject.toml` | Wheel builds; entry points registered. | Low | 0.1 |
| 10.5 | Add Docker/Podman optional container for reproducible deployment. | `Dockerfile`, `docker-compose.yml` | Container starts and runs one E2E campaign. | Medium | 10.4 |
| 10.6 | Final deep audit by frontier model on entire repo. | `docs/runbooks/deep_audit.md` | Opus/Kimi audit report; critical issues fixed. | High | 9.8 |
| 10.7 | Tag `v0.1.0` and merge PR #11. | Git tag | `main` is clean; tag exists. | Low | 10.1–10.6 |

**Order gate:** 10.1–10.5 parallel, then 10.6, then 10.7.

---

## 4. Subsystem Specifications

### 4.1 Router Layer

- **Top-level:** `.claude/agents/research-engine-router.md` mirrors `financial-model-router.md`. It owns the super-project layout and routes to sub-routers.
- **Sub-routers:** `discovery-router.md`, `browser-router.md`, `extraction-router.md`, `evaluation-router.md`.
- **Learned log:** `.claude/research-engine-routes.md` with `R###` items: `signal`, `load`, `tactic`, `prov`, `hits`, `verified`, `status`.
- **Modes:** `ROUTE` (return read-order), `EXECUTE` (do isolated work, return HANDOFF), `FROZEN EVAL` (read-only, no log mutation).
- **Non-self-poisoning rules:** provisional until `hits ≥ 2`; negative items re-tested; one `Edit` per delta; contradiction-free; collapse-free; never wholesale rewrite.

### 4.2 Orchestrator

- Campaign lifecycle: `INIT → PLAN → DISCOVER → SCREEN → EXTRACT → ADVERSARIAL → EVALUATE → DELIVER → FINALIZE`.
- Supports a dedicated **Unblocking** campaign type: when the main AI reports a blocker (`cannot find data`, `no free source`, `unknown API`, `failing dependency`, etc.), the engine treats it as a research request and does not stop until it returns actionable solutions.
- State machine persisted in SQLite; append-only event bus.
- Supports pause/resume/kill and idempotent retries.
- Each stage emits telemetry receipts.

### 4.3 AI-Only Browser

- No human UI; perception is accessibility-DOM + raw HTTP + CDP.
- Tools: `fetch`, `evaluate`, `click`, `fill`, `graphql`, `api`, `snapshot`.
- SSRF-safe URL policy blocks private ranges, file://, localhost.
- robots.txt respected; polite rotation, jitter, proper headers.
- Fingerprint rotation uses legitimate browser headers only.

### 4.4 Discovery / Academic Search

- Sources: Semantic Scholar, Crossref, arXiv, OpenAlex, SERP, focused web crawl.
- Deduplication via title/DOI/URL fuzzy hashing.
- Citation snowballing forward and backward.
- Full-text resolution via Unpaywall/DOI/open-access checks.
- Query planner decomposes natural-language requests into source-specific queries.

### 4.5 Screening + Extraction

- Screening criteria: boolean, numeric, LLM-rubric.
- Ranker scores relevance and quality per source.
- Extraction: markdownify HTML, convert PDF (keep original if corrupt), structured methodology/data/results/conflict/citation extraction.
- Conflict detector flags discrepancies with user data, never auto-dismisses.

### 4.6 Adversarial Review

- `Devil`: challenges claims for evidence, soundness, and coverage.
- `Verifier`: re-runs claimed lookups, checks quote presence and DOI validity.
- `Challenge`: dispatches challenges back to main agent or escalates to frontier model.
- Every deliverable is challenged before it reaches the main AI.

### 4.7 Evaluation / Improvement Apparatus

- `harness.py`: scores campaigns on precision, recall, coverage, citation quality.
- `reporter.py`: generates verifiable reports with evidence links and fix requests.
- `improvement.py`: converts reports into itemized R### deltas or issues; never auto-applies.
- Frequency is high early, then naturally declines as the engine matures.
- `deep_audit.py`: periodic frontier-model audit of the eval harness, logs, and adversarial chain.

### 4.8 Monitoring / Telemetry

- `progress.py`: stage-weighted 0–100 progress.
- `estimator.py`: per-stage runtime prediction.
- `calibrator.py`: adjusts weights from historical MAPE.
- `telemetry.py`: anomaly detection for stuck stages, thrashing, repeated failures.
- Main AI status query returns: progress %, ETA, current stage, remaining steps.

### 4.9 Document Conversion

- HTML → Markdown via `markdownify.py`.
- PDF → Markdown via `pdf_converter.py` with corruption detection.
- If conversion corrupts: keep original + store `.txt` or safe alternative.
- All conversions log hash and provenance.

### 4.10 Storage

- SQLite for campaign state, papers, and events.
- DuckDB for large corpora and embeddings.
- Artifacts named by content hash to deduplicate.
- Full-text search via SQLite FTS5.

### 4.11 Cleanup

- `janitor.py` runs at session end.
- Deduplicates files by hash, purges temp cache, vacuums DBs.
- Logs every deletion; never deletes source-of-truth data.

### 4.12 GitHub / PR Automation

- `scripts/github_pr.py`: branch, commit, push, open PR.
- `scripts/end_session.py`: cleanup → update `HANDOFF.md` → commit → push → open PR.
- Every session ends with a PR; no work stays uncommitted on a local branch.

### 4.13 Consuming-Project Deliverable Layout

When `research-engine` runs inside a host project, it creates a surface-level `Research/` folder and writes every campaign's public output there. The layout guarantees that campaign briefs are unambiguous and that a master brief always reflects the latest combined results.

```
Host Project/
├── Research/
│   ├── Insights.MD                         # folded aggregation of all campaign briefs
│   ├── <campaign-slug>/
│   │   ├── <campaign-slug>_Insights.MD     # e.g. LLM_SLR_Insights.MD
│   │   ├── sources/                        # markdown + PDF cache for this campaign
│   │   └── evidence_map.json
│   └── <another-campaign-slug>/
│       └── <another-campaign-slug>_Insights.MD
```

Rules:

- `Research/` is created at the host project root when the first campaign is launched.
- Each campaign sub-folder is named with a URL-safe slug derived from the campaign query/topic.
- The campaign brief inside a sub-folder is always named `<folder-name>_Insights.MD` so file-name search and project-registry indexing include the topic identifier.
- `Research/Insights.MD` is regenerated at `DELIVER` stage by folding in every `<slug>_Insights.MD`. It contains a table of contents linking to each campaign brief and a dated header.
- Internal engine state (SQLite, DuckDB, cache, temp files) stays inside the engine's own `data/` directory and is never dumped into `Research/`.
- The janitor only removes duplicates and temp files; it never deletes `Research/` or its briefs unless explicitly requested by the user.

### 4.14 Unblocking Research Campaigns

The engine must be able to take a blocker from the main AI and run a focused campaign until it returns a solution. Examples: "find a free data source for X", "identify an API that provides Y", "locate a library that handles Z", "find documentation or examples for W".

Flow:

1. Main AI sends a blocker query, e.g. `research-engine run "Find free public databases for U.S. county-level health statistics"`.
2. The engine classifies it as an `unblocking` campaign type and runs the standard lifecycle with extra emphasis on source availability, access terms, and concrete next steps.
3. The deliverable brief is titled by the campaign slug and contains:
   - A restatement of the problem.
   - A ranked list of solutions/resources with URLs, access terms, and key constraints.
   - Exact commands, API endpoints, or sign-up links where applicable.
   - A "next action" recommendation.
   - Confidence label and caveats per item.
4. The `Devil` agent specifically challenges whether each solution actually solves the blocker and whether the source is still reachable.
5. The engine is not allowed to return a brief that says "no solution found"; it must either find solutions or escalate to a frontier model with a detailed evidence log.

---

## 5. Risk + Mitigation Table

| Risk | Impact | Mitigation |
|---|---|---|
| **Local AI hallucinates sources or covers up failures.** | High | Adversarial `Devil` + `Verifier` on every claim; frontier deep audits; append-only receipts. |
| **Evaluation apparatus is compromised by local AI.** | High | Deep audits by Opus/Kimi; eval harness isolated from `src/`; learned-log chaos tests. |
| **Ethical/legal boundary crossed (crawling paywalls, bypassing auth, violating robots.txt).** | Critical | SSRF policy, robots.txt enforcement, no credential bypass, explicit allow-list for non-public data, legal review in ADR. |
| **Rate limits or bans from sources.** | Medium | Polite rotation, backoff, jitter, cache, user-agent rotation, configurable concurrency caps. |
| **Storage bloat from raw PDFs and cache.** | Medium | Hash-based dedup, session-end janitor, DuckDB compression, markdown-first policy. |
| **Router learned-log becomes contradictory or collapse-poisoned.** | Medium | R### itemized deltas, provisional until confirmed, negative re-testing, `replay.py` contradiction check. |
| **Model-agnostic abstraction leaks provider-specific code.** | Medium | Strict `LLMProvider` interface; all provider-specific logic in one module per provider. |
| **Progress/ETA inaccurate, undermining user trust.** | Medium | Self-calibrating stage weights; conservative defaults; MAPE tracked across campaigns. |
| **Git branch hygiene degrades (dead branches, uncommitted work).** | Medium | End-of-session PR ritual; branch protection; PR templates. |
| **Scope creep beyond what local AI can reliably drive.** | High | Tight phase gates; adversarial review stops overreach; frontier model audits architecture. |

---

## 6. HANDOFF.md Conventions + End-of-Session Ritual

At the end of **every** session, update `docs/HANDOFF.md` with this structure:

```markdown
# HANDOFF — <YYYY-MM-DD>

## This Session
- Done: <bullet list>
- Open: <bullet list>
- Blocked: <bullet list with blocker and owner>
- Risks: <bullet list>

## State of the Build
- Phase: <current phase>
- Last passing commit: <hash>
- Last PR: <#>

## Next Priority Tasks
1. <task>
2. <task>

## Decisions / Assumptions
- <ADR or load-bearing assumption>

## Notes for Next Agent
- <anything a cold-start agent needs>
```

### End-of-Session Ritual (run via `scripts/end_session.py`)

1. **Clean:** run janitor (`cleanup/dedup_files.py`, `janitor.py`).
2. **Document:** update `HANDOFF.md`.
3. **Test:** run `pytest -q`, `ruff check .`, `python -m claude_monitor` if long.
4. **Commit:** stage changes; write conventional commit message.
5. **Branch:** if on `main`, create session branch first.
6. **Push:** `git push -u origin <branch>`.
7. **Pull Request:** open PR with test plan and risk note via `scripts/github_pr.py`.
8. **Memory:** write ≤1 routing feedback item to `.claude/research-engine-routes.md` if warranted.

---

## 7. Definition of Done for v0.1.0

- [ ] Repo initialized on GitHub with branch protection and CI.
- [ ] All five routers (`research-engine-router` + four sub-routers) route correctly.
- [ ] Learned-routes log uses R### schema and passes chaos tests.
- [ ] `router_eval` harness runs `table_parser.py`, `run_benchmark.py`, `drift_check.py`, and `test_log_robustness.py` green.
- [ ] Model-agnostic LLM layer supports Ollama and Anthropic via config.
- [ ] AI-only browser can fetch HTML, run raw HTTP, query GraphQL, and respect robots.txt/SSRF policy.
- [ ] Discovery pipeline can search Semantic Scholar, Crossref, arXiv, OpenAlex, and SERP; deduplicate; snowball; resolve full text.
- [ ] Screening + extraction produce structured Markdown/JSON deliverables with conflict detection.
- [ ] Adversarial chain challenges every insight; verifier catches hallucinated citations.
- [ ] Evaluation apparatus generates a verifiable report and proposes itemized improvements.
- [ ] Deep-audit trigger can run a frontier model audit of the eval chain and logs.
- [ ] Monitoring reports progress %, ETA, stage, and remaining steps; self-calibrates.
- [ ] Document conversion handles HTML and PDF without corrupting originals.
- [ ] Storage uses SQLite/DuckDB; cleanup deduplicates and vacuums at session end.
- [ ] `research-engine run <query>` completes an end-to-end research campaign and writes `Research/<campaign-slug>/<campaign-slug>_Insights.MD` plus `Research/Insights.MD` in the host project.
- [ ] `research-engine run "Find a solution for <blocker>"` returns actionable solutions with sources, access terms, and next steps; the engine never reports "no solution found" without a full evidence log and escalation path.
- [ ] Claude Code can call the engine via MCP/stdio tools.
- [ ] 80%+ test coverage; CI green; security review complete.
- [ ] `README.md`, architecture docs, and runbooks are complete.
- [ ] `v0.1.0` tag exists on `main`.

---

**Load-bearing assumption:** Local models (Gemma/Qwen-class) are capable enough to drive deterministic discovery, screening, and verification when given small, structured prompts and adversarial oversight. If this assumption is wrong, Phase 5 will need heavier fallback to frontier models and the cost/token model changes.
