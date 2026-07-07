# HANDOFF — 2026-07-06

## This Session
- Done:
  - Read and parsed `Research Engine Prompt1.MD`.
  - Loaded reference/skills/catalog/agents per CLAUDE.md v12.
  - Researched current open-source patterns for research agents, browser automation, and multi-agent orchestration.
  - Used the `planner` agent to produce `docs/plan/master_plan.md`.
  - Created full project directory tree and Phase 0 scaffold (README, HANDOFF, .gitignore, pyproject.toml, routers, eval harness skeleton, GitHub templates).
  - Fixed `router_sim.py` keyword matching and added a load table to `research-engine-router.md` so all `.claude/router_eval/` self-checks pass.
  - Initialized GitHub repo `isaac233/Research-Engine`, opened Pull Request #1, merged it to `main`, and deleted the feature branch.
  - Amended `docs/plan/master_plan.md` to require a consuming-project `Research/` folder with per-campaign sub-folders and differentiated `<campaign>_Insights.MD` files plus an aggregated `Research/Insights.MD`; merged via PR #3.
  - Implemented Phase 1: core orchestrator + model-agnostic LLM layer.
    - `src/research_engine/state.py`: immutable `ResearchRequest`/`Campaign` dataclasses + SQLite append-only store.
    - `src/research_engine/events.py`: append-only event bus.
    - `src/research_engine/llm/`: `LLMProvider` ABC, `OllamaClient`, `AnthropicClient`, `ModelRegistry`.
    - `src/research_engine/orchestrator.py`: campaign lifecycle state machine with pause/resume/kill.
    - `src/research_engine/monitoring/telemetry.py`: sanitized stage telemetry.
    - `src/research_engine/main.py`: `research-engine run/status/pause/resume/kill` CLI.
    - `src/research_engine/config.py`: project path resolution (including `Research/` layout).
    - Tests: 21 unit/integration tests, 80% coverage.
  - Implemented Phase 2: AI-only browser subsystem.
    - `src/research_engine/browser/ai_browser.py`: `AIBrowser` ABC, `BrowserAction`, `BrowserResult`, `BrowserActionType` enum.
    - `src/research_engine/browser/cdp_driver.py`: Playwright/Chromium driver with policy + robots.txt guards.
    - `src/research_engine/browser/raw_http.py`: pooled httpx client with retries, backoff, jitter, header rotation.
    - `src/research_engine/browser/policy.py`: SSRF/ethical URL policy (private IP, localhost, file:// block).
    - `src/research_engine/browser/robots.py`: per-host robots.txt fetcher/cache.
    - `src/research_engine/browser/fingerprint.py`: legitimate header/viewport rotation.
    - `src/research_engine/browser/graphql_client.py`: GraphQL-aware POST helper.
    - `src/research_engine/browser/unblock_probe.py`: browser-based unblocking research probe; never reports "no solution" without an evidence log.
    - `src/research_engine/orchestrator.py`: blocker detection + unblocking campaign dispatch during discovery.
    - `src/research_engine/main.py`: wires `UnblockProbe` as the default browser.
    - Tests: 38 new browser unit tests, total 59 tests, 80% coverage.
  - Implemented Phase 3: discovery + academic search.
    - `src/research_engine/discovery/schema.py`: normalized `Paper`, `SourceQuery`, `SearchResult`, `DuplicateGroup`, `ResolveResult`, `DiscoveryResult` dataclasses.
    - `src/research_engine/discovery/query_planner.py`: decomposes a request into source-specific `SourceQuery` objects.
    - `src/research_engine/discovery/sources/base.py`: `SourceAdapter` ABC.
    - `src/research_engine/discovery/sources/semantic_scholar.py`, `crossref.py`, `arxiv.py`, `openalex.py`, `serp.py`, `web_crawl.py`: academic + web source adapters.
    - `src/research_engine/discovery/dedup.py`: DOI/URL exact match + title fuzzy deduplication with different-DOI guard.
    - `src/research_engine/discovery/snowball.py`: forward/backward citation expansion via source adapters.
    - `src/research_engine/discovery/resolver.py`: full-text resolution through pdf_url, arXiv, Unpaywall, and DOI landing page; never paywalls.
    - `src/research_engine/discovery/source_registry.py`: builds and dispatches adapters by source name.
    - `src/research_engine/discovery/pipeline.py`: end-to-end `DiscoveryPipeline` (plan → search → dedup → snowball → resolve).
    - `src/research_engine/orchestrator.py`: `DISCOVER` stage runs `DiscoveryPipeline`; unblocking campaigns still dispatch browser probe.
    - `src/research_engine/main.py`: constructs `SourceRegistry` + `DiscoveryPipeline` and passes to `Orchestrator`.
    - `pyproject.toml`: added `feedparser>=6.0` dependency.
    - Tests: 56 new discovery unit tests, total 115 tests, 86% coverage.
  - Updated routers with Phase 3 keyword rows and R013–R019 learned-route deltas in `.claude/research-engine-routes.md`.
  - Updated `.claude/agents/discovery-router.md` keyword table for pipeline, schema, registry, orchestrator integration, and main.py.
  - Implemented Phase 4: screening + structured extraction.
    - `src/research_engine/screening/criteria.py`: `BooleanCriterion`, `NumericCriterion`, `LLMRubricCriterion`, `CriterionSet`, `MatchMode`, `CriterionType`, plus factory + default academic criteria.
    - `src/research_engine/screening/ranker.py`: `SourceRanker` applies criteria with optional LLM scorer, returns sorted `SourceScorecard`s; supports must/should/optional weights and `build_llm_scorer` helper.
    - `src/research_engine/extraction/markdownify.py`: HTML → markdown conversion (headings, bold/italic, links, lists, tables) with nav/footer/script/style removal.
    - `src/research_engine/extraction/pdf_converter.py`: `PDFConverter` tries `pdfplumber` then `pypdf`, keeps original on failure.
    - `src/research_engine/extraction/structured.py`: `StructuredExtractor` extracts methodology, data summary, results summary, claims, citations, and conflict detection; abstract fallback when no full text.
    - `src/research_engine/extraction/citation.py`: `extract_citations()`, `normalize_doi()`, `citations_to_dict()`.
    - `src/research_engine/orchestrator.py`: added `SCREEN` and `EXTRACT` stage handlers; persists `scorecards`, `included_papers`, `extracted_sources` to campaign meta; fixed stage-to-stage campaign state freshness.
    - `src/research_engine/main.py`: wires `SourceRanker` and `StructuredExtractor` into `Orchestrator`.
    - `src/research_engine/discovery/schema.py`: added `Paper.to_dict()` / `Paper.from_dict()` for JSON-safe SQLite meta serialization.
    - `src/micro_tools/pdf_to_md/`: standalone PDF → markdown micro-tool with CLI entry point.
    - Tests: 19 new screening/extraction unit tests, total 134 tests, 87% coverage.
  - Updated `.claude/agents/extraction-router.md` keyword table for screening, extraction, orchestrator integration, main.py, and state.
  - Added R020–R027 learned-route deltas to `.claude/research_engine-routes.md` for Phase 4 subsystems.
- Open:
  - Implement Phase 5: adversarial verification (Devil + Verifier + challenge engine).
  - Validate local model stack (Ollama + Gemma/Qwen-class) for screening/extraction workloads.
- Blocked: none.
- Risks:
  - Ethical/legal boundary for "advanced penetration techniques" must remain pinned to authorized/defensive/public-only scope as browser capabilities grow.
  - Local model capability assumption (Gemma/Qwen-class) must be validated during Phase 4 screening/extraction.
  - Unblocking campaigns must not drift into gray-area sources; the SSRF/robots.txt policy is the guardrail.

## State of the Build
- Phase: 4 (complete; PR #10 open)
- Last passing commit: TBD after PR #10 merge
- Last PR: #10 (Phase 4 screening + structured extraction)

## Next Priority Tasks
1. Implement Phase 5: adversarial verification (Devil + Verifier + challenge engine).
2. Validate local model stack (Ollama + Gemma/Qwen-class) for screening/extraction workloads.
3. Continue adversarial review of browser policy and unblocking flow.

## Decisions / Assumptions
- ADR-001: Python 3.12+ primary; SQLite for state, DuckDB for corpora.
- ADR-002: Port router/eval pattern from Financial Model Training Data.
- Load-bearing assumption: local models can drive deterministic discovery/screening with adversarial oversight.

## Notes for Next Agent
- All routers live under `.claude/agents/` and learned routes under `.claude/research-engine-routes.md`.
- The eval harness under `.claude/router_eval/` must remain isolated from `src/`.
- `scripts/end_session.py` is a stub; do not run it for real until Phase 9.
- The `Research/` folder layout is documented in `docs/plan/master_plan.md` section 4.13 and implemented in `src/research_engine/config.py`.
- Discovery subsystem is fully wired into the orchestrator; start Phase 4 with `screening/criteria.py` and `screening/ranker.py`.
