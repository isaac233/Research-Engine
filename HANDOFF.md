# HANDOFF — 2026-07-09

## Track B — discovery relevance + citation grounding (2026-07-09, branch `feat/deepresearch-bench`, commits `327a39f` + `1531516`)

**What was built (all TDD, mypy strict + ruff green, full unit suite green):**

*Option 2 — discovery relevance:*
- **Relevance rubric was blind**: the default prompt had no `{query}` placeholder, so `format(query=...)` was a no-op — the LLM scored papers without ever seeing the research query. Fixed; rubric is now a MUST gate.
- **Rubric was unfailable**: `clamped = max(minimum_score, ...)` floored every low score up to passing. Pass/fail now uses the raw score.
- No-LLM environments pass rubrics unchecked (offline CI safe); scorer errors fail visibly.
- Query planner skips arXiv for non-STEM queries (keyword-term heuristic; screening's LLM gate is the backstop).
- `has_full_text` demoted MUST→SHOULD (it excluded every crossref/openalex record wholesale); new `has_abstract` SHOULD (w=2.0) and **`readable` MUST** (abstract OR full text — a relevant-sounding title-only stub cannot be extracted or cited).
- **OpenAlex abstracts were always empty**: adapter read `raw["abstract"]`, which the API never sends; now rebuilds text from `abstract_inverted_index` (live: 7/10 papers gained abstracts).
- New honesty flag `screening_yielded_offtopic` (≥50% of candidates fail relevance) beside `screening_yielded_zero`.

*Option 3 — citation grounding:*
- Synthesizer renders per-source URLs, instructs inline `[n]` citations, and code-appends a deterministic `## References` section (URL-less sources listed so `[n]` never dangles). Reporter fallback same.
- `drop_failed_claims`: Verifier-rejected claims are stripped before synthesis — unverified claims never ship.
- `unique_insight_filter` keeps abstract-only sources that have content but 0 structured claims (they were silently dropped, collapsing briefs to 1 source).

**Measured (1 en task, ollama judge, N=1 directional):** RACE 40.5 (unchanged), FACT extraction now finds (fact,url) pairs (0→2) but 0 supported — the single on-topic readable source is a paywalled IGI DOI the judge cannot verify. **Sources are now on-topic** (was: gravitational-wave papers for a Japan-demographics query; now: population-aging economics).

**THE structural finding (next session's target):** DeepResearch Bench tasks are general web-research questions. For task 51 (Japan elderly market) only 1/30 academic candidates was both relevant and readable; for task 52 (Buffett/Munger investment philosophies) 0/21 — the engine honestly delivered nothing (`screening_yielded_zero` + `_offtopic` both fired; the anti-cover-up works). Academic APIs are the wrong lane for these tasks. **The engine needs the web discovery lane live**: `SERPAdapter` exists but requires a configured endpoint (SearXNG instance or paid API) — none configured. Wiring a SearXNG endpoint (or serper.dev key) + enabling `serp`/`web_crawl` in the planner for non-academic topics is the single highest-value next move for both RACE breadth and FACT (web sources are fetchable, unlike paywalled DOIs).

**Bench gotchas learned:** `bench/out/engine.jsonl` is a resume cache — a re-run with the file present re-scores the OLD article (delete/move it to re-measure after engine changes). The local mistral judge at temp=0 can emit identical RACE grids for different mediocre articles — treat as coarse/directional only.

## DeepResearch Bench scoreboard — Track A (2026-07-09, branch `feat/deepresearch-bench`)

**Why:** the engine had never been scored against any external benchmark or against Opus — "hasn't beaten Opus" was a feeling, not a number. Built the apples-to-apples scoreboard first (measure before upgrading), per the approved plan `C:\Users\Isaac\.claude\plans\lexical-bubbling-starfish.md`.

- **Ported DeepResearch Bench** (arXiv:2506.11763, Apache-2.0) into a new top-level `bench/` package: **RACE** (report quality vs a vendored reference report, 4 weighted dims, 0-100 where 50 = ties reference) + **FACT** (extract cited (fact,url) pairs → fetch via the engine's own `raw_http`+`markdownify` → judge support → citation accuracy + effective citations).
- **Vendored** `bench/data/{query,criteria,reference}.jsonl` (100 tasks / criteria / reference reports) + `LICENSE.md` provenance.
- **Model-agnostic judge**: new `src/research_engine/llm/gemini_cli_client.py` (shells to `gemini -p`, stdin for bulk, auth-error surfaced) + `bench/judge.py build_judge(gemini|ollama|anthropic)`. Registered `gemini` in `model_registry`.
- **CLI**: `research-engine bench --tasks N --judge {gemini|ollama|anthropic} [--reuse-engine --quality]` → writes `Research/benchmarks/<date>_scorecard.MD` (engine row vs published Opus/Gemini/OpenAI bar in `bench/leaderboard.py`, flags weakest dimension = Track B target).
- **Verified:** 22 new bench unit tests + full unit suite green (EXIT=0); mypy strict clean (87 files); ruff clean. RACE math + scorecard render verified with a fake judge.
- **Judge availability in this env:** Gemini CLI + MCP are NOT authenticated (no key/oauth; MCP `spawn EINVAL`). Ollama IS up (gemma4:31b, mistral-small3.2, qwen3.6-27b) — used as the offline validation judge. For the closest-to-official number the user must authenticate `gemini` once (or set `GEMINI_API_KEY`) and run `--judge gemini`.
- **TLS note:** corporate cert revocation blocks `curl`; used `--ssl-no-revoke` to vendor data (engine itself already fixed via truststore).

### FIRST REAL SCORECARD (1 en task, local mistral-small judge — directional, N=1)
`Research/benchmarks/2026-07-09_scorecard.MD`:

| | RACE Overall | Comp | Depth | Inst | Read | FACT C.Acc | E.Cit |
|---|---|---|---|---|---|---|---|
| **Research Engine** | **40.52** | 42.86 | 37.78 | 41.50 | 40.15 | **0.00** | **0** |
| Claude-3.7-Sonnet w/Search | 40.67 | 38.99 | 37.66 | 45.77 | 41.46 | 93.68 | 32 |
| OpenAI Deep Research | 46.98 | 46.87 | 45.25 | 49.27 | 47.14 | 77.96 | 41 |

**What the scoreboard exposed on run one (the whole point of measuring):**
1. **FACT = 0.** The delivered brief had **zero citations** (0 URLs, 0 `[n]` refs). The engine reads full text but does not ground claims to sources in the deliverable — the vision's "citation-rich report" is measurably absent.
2. **Off-topic sources.** Task = "elderly demographic market size in Japan 2020-2050"; the engine returned **particle-physics / gravitational-wave arXiv papers** ($B^0_s$ decay, CMS/LHCb). Discovery has an arXiv/physics bias and failed relevance for a demographics query.
3. **RACE ~40 is judge-inflated.** A lenient local judge scored fluent-but-off-topic prose near Claude's level. FACT + a stronger judge (Gemini) expose what RACE alone hides. Without the scoreboard this run reads "campaign completed, Insights.MD delivered" — a green check over an ungrounded, off-topic result. That is the exact cover-up failure the project fears, now visible.

### CHOSEN TRACK B WORK (user picked both, 2026-07-09) — build next, then re-measure
- **Option 2 — Discovery relevance (biggest gap).** Off-topic sources are the #1 problem. The query planner + source registry over-weight arXiv and don't filter for topical relevance, so a demographics/market query pulled physics papers. Fixes: (a) relevance gate in screening that scores paper-vs-query semantic match and drops off-topic sources (reuse `screening/ranker.py` + a local-LLM relevance criterion in `screening/criteria.py`); (b) query planner should pick sources by topic (OpenAlex/Crossref/web for non-CS topics, not arXiv-first) in `discovery/query_planner.py` + `discovery/source_registry.py`; (c) add a "screening_yielded_offtopic" honesty flag like the existing `screening_yielded_zero`. Target metric: on-topic sources -> RACE Comp/Depth up.
- **Option 3 — In-pipeline citation grounding (FACT 0 -> real).** Every delivered claim must carry a verified statement->source-URL span; unsupported claims dropped/flagged before DELIVER. Fixes: the synthesizer (`synthesis/synthesizer.py`) + reporter (`evaluation/reporter.py`) must emit inline citations (`[n]` + a reference list with URLs) from `ExtractedSource.citations`/paper URLs, and the adversarial `Verifier` (`adversarial/verifier.py`) already checks quote/URL presence — wire its pass/fail so uncited claims don't ship. Reuse the bench `FactScorer` logic as the in-loop grounding check. Target metric: FACT C.Acc 0 -> competitive; E.Cit > 0.

**Verify each with the scoreboard:** after a change, run `research-engine bench --tasks 5 --judge ollama --reuse-engine` (re-score) or without `--reuse-engine` (fresh campaigns), and diff the scorecard. Authenticate `gemini` for a trustworthy multi-task number: `research-engine bench --tasks 20 --judge gemini`.

**Files added this session (branch `feat/deepresearch-bench`):** `bench/` (package + `data/{query,criteria,reference}.jsonl` + `LICENSE.md`), `src/research_engine/llm/gemini_cli_client.py`, `bench` command in `main.py`, gemini branch in `model_registry.py`, `tests/unit/bench/` (22 tests), `docs/architecture/benchmark.md`. Approved plan: `C:\Users\Isaac\.claude\plans\lexical-bubbling-starfish.md`.

## PUSHED — PR #17 open (2026-07-08)
Branch `feat/llm-fulltext-lanes` (29 commits) pushed to origin; **PR #17**: https://github.com/isaac233/Research-Engine/pull/17 (base `main`). Covers golden-eval + anti-poison + self-improvement loops + the full LLM-fulltext 7-lane upgrade (Phases 0-6) + audit TLS/gzip fixes. ~395 tests green, mypy+ruff clean, live campaign verified.

## Whole-Project Audit + "does it actually research?" — 2026-07-08

Audited cohesion/organization/consistency-with-both-prompts and — critically — ran a REAL end-to-end campaign. Found and fixed TWO blockers that made real research impossible; the engine now genuinely performs research.

- **Structure:** clean, domain-organized, no orphan files (only `_run_stub` remains as a safety default; its "future subsystems" comment is now stale — all stages implemented).
- **BLOCKER 1 (TLS) — fixed (`15a5929`):** every HTTPS source failed with CERTIFICATE_VERIFY_FAILED (corporate TLS-inspection root CA absent from certifi). `src/research_engine/__init__.py` now injects `truststore` at import → all httpx/urllib use the OS trust store. Added truststore dependency.
- **BLOCKER 2 (gzip) — fixed (`15a5929`):** crossref/openalex failed "incorrect header check" — `ssrf_guard.safe_request` rebuilt the response with decompressed body but kept `Content-Encoding: gzip` → double-decode. Now strips content-encoding/length on the reconstructed response.
- **PROOF IT WORKS:** live campaign `run "efficient routing in sparse mixture-of-experts models" --sources 3 --quality 0.5` completed end-to-end and delivered `Research/.../*_Insights.MD` with 3 REAL arXiv papers, real quantitative results (e.g. within/across routing similarity 0.8435±0.0879, Cohen's d 1.44), method + data + **replication steps** per source, a source's GitHub code repo, and cross-source synthesis. gemma4:12b (extract) + Mistral-Small (synth) ran on GPU. This is the vision realized (full-text, replication-grade, local-model-driven).
- Discovery now: arxiv + crossref + openalex return papers; semantic_scholar 429s without an API key (graceful, handled). Multi-source works.
- FOLLOW-UP (minor): semantic_scholar needs an API key or backoff for reliability; clean the stale `_run_stub` comment.

## LLM Full-Text Extraction + 7-Lane Plan — 2026-07-08

**Why this work:** user observed the research phase was seconds long and the GPU never spiked. Root cause: the local LLM was **never wired into a run** (`_make_orchestrator` built `SourceRanker()`/`StructuredExtractor()` with no provider), and extraction was regex on abstract-level text — the exact "reads only abstracts, can't replicate" failure the project exists to kill. New spec in `Research Engine Prompt 2.txt`: 7 model lanes, quality/speed + volume sliders, constraint triangle, sequential VRAM load/unload, replication-grade full-text insight.

**Approved plan:** `C:\Users\Isaac\.claude\plans\jolly-wobbling-steele.md` (6 phases). Branch `feat/llm-fulltext-lanes` (cut from `feat/self-research-golden-eval`).

**DONE this session (Phase 0 + Phase 1, live-verified):**
- Phase 0 (`cc1dff2`, `b4fa9a2`): `config/model_lanes.yaml` (7 lanes w/ fallbacks) + `scripts/pull_models.py` (normalize HF tags, pull, record `data/model_pull_report.json`, degrade missing→installed fallback). **All 7 requested tags 404 as written** (`gemma4:12b/26b/31b`, `batiai/qwen3.6-35b:iq3`, etc. are speculative) → every lane currently falls back to an installed model (`gemma4:latest`, `mistral-small3.2:latest`, `qwen2.5-coder:14b`). A real pull is running in the BACKGROUND; check `data/model_pull_report.json` + `data/pull_models.log` next session for any tag that actually resolved.
- Phase 1 (`0849c2c`, `3948e05`): `extraction/llm_extractor.py::LLMSectionExtractor` (chunked map-reduce, defensive JSON parse, ABSENT handling, **verbatim-evidence substring guard** dropping hallucinated claims) + `extraction/chunker.py` + `extraction/prompts.py`. `StructuredExtractor` gained `llm_extractor`; uses LLM path on real full text, regex fallback otherwise, flags `meta.degraded=abstract_only`, sets `extraction_tool=llm:<model>`; added `conclusions`+`replication_notes`. `main.py::_make_orchestrator` wires deep lane via `ModelRegistry` with ping-guarded regex fallback (CI/offline safe).
- **Key fix (`3948e05`):** `gemma4` is a *thinking* model — with a bounded token budget it spent it all on hidden reasoning and returned EMPTY content. Set `think=false` by default on `OllamaClient`. Now clean JSON in ~2.5x fewer tokens.
- **Live acceptance PASSED:** `gemma4:latest` read full text → methodology/data/results/conclusions + 5 evidence-verified claims (0 hallucinated) in ~8s; `ollama ps` showed the model resident with 3.3 GB on the GPU. The GPU-driven full-text extraction the user wanted now works.
- Verification: all tests pass, mypy clean (75 files), ruff clean. New tests: `tests/unit/extraction/test_llm_extractor.py` (8, incl. anti-hallucination + abstract-only skip).

**Phase 2 DONE (`71e162d`), live-verified:**
- `llm/lane_roster.py::LaneRoster.from_yaml` (resolves effective tag from pull report); `llm/lifecycle.py::ModelLifecycleManager` (load/unload keep_alive=0, switch evicts old before loading new, `with_model` ctx-mgr evicts on error, `active()` via `/api/ps`, event hook). `ollama_client.py`: complete() options+keep_alive, `ps/warm/unload`. `model_registry.build_ollama_client()`. `validate-models` now prints a lane table.
- Live: load→switch→unload keeps exactly ONE model resident (no VRAM stacking). Tests added (roster + lifecycle).
- **ALL 7 lanes resolved to REAL models** (`be808af`, `validate-models` all ok): fast `gemma4:12b` (in-VRAM), deep `gemma4:12b` (in-VRAM; the aspirational `gemma4:26b-a4b` MoE does NOT exist, so deep uses 12b — user confirmed fine), overnight `gemma4:31b`, online_a `batiai/qwen3.6-27b:q3` (user-corrected tag), online_b `hf.co/unsloth/Qwen3.6-27B-GGUF:IQ4_XS`, synth_a `hf.co/lmstudio-community/Mistral-Small-3.2-24B-Instruct-2506-GGUF:Q4_K_M`, synth_b `hf.co/KikoCis/gemma-4-31b-it-IQ3_XS-GGUF:IQ3_XS`. Extra installed: `batiai/qwen3.6-35b:iq3` (unused spare).
- **Pull script hardened:** captures raw bytes (no text-mode) to survive ollama's ANSI progress on Windows cp1252; strips control chars from stored errors; incremental report writes. `_resolve_deep_model` in main.py reads the report → deep extraction now runs on gemma4:12b.

**Phase 3 DONE (`23c5cbb`), live-verified:**
- `monitoring/gpu_probe.py::GpuProbe.snapshot()` (nvidia-smi VRAM + `/api/ps` per-model RAM-offload split; None on CI). `telemetry.py`: `model_event`/`gpu_snapshot` + `lifecycle_telemetry_hook`. `orchestrator.status_snapshot` includes live `gpu` + per-stage `models`; `_run_extract` emits model assignment + extractor agent-history action (the deferred P1 item). `status` CLI prints `model[extract]`, VRAM, per-model offload %. Live: probe read 1779/16303 MiB.

**Phase 4 DONE (`dc1ca08`), live-verified:**
- `planning/constraint_triangle.py::solve` (2-of-3 derive 3rd; time governs→no slider→auto-optimize quality; <2 & no time→needs_slider; maps quality tier→per-stage lane assignment). `planning/quality_floor.py::QualityFloor.check` (goal/omission/fabrication). `cli/slider.py` (arrow-key via optional prompt_toolkit, numbered fallback, never hangs/aborts a run — non-TTY/EOF→balanced defaults). `main.py run`: `--quality/--time-budget/--sources`, persists `ResolvedPlan` to campaign meta, volume caps max_sources. `prompt_toolkit` added as optional `[tui]` extra.
- Live: `--time-budget 600`→quality auto 0.63 no slider; `--quality 0.9 --sources 5`→time 409s; bare→balanced default, no hang.
- NOTE: ResolvedPlan.lane_assignment is persisted to meta but stages don't yet READ it to pick lanes — that wiring is Phase 5 (with lifecycle.with_model + handoff docs).

**Phase 5 DONE (`eda41f4`):**
- `synthesis/synthesizer.py::Synthesizer` (deep reads → replication-grade brief via synth lane) + `unique_insight_filter` (drop dup-insight sources, cap at volume). `planning/handoff.py::HandoffDoc` (written on model switch). `main.py`: one Ollama provider drives all lanes — fast-lane `build_llm_scorer` into screening, deep lane into extraction, synth lane into Synthesizer; lane tags via LaneRoster+pull report; heuristic fallback when Ollama absent. `orchestrator`: synthesizer builds the brief (unique-insight sources) w/ reporter fallback + writes extract→evaluate handoff.
- 389 tests pass; mypy+ruff clean (86 files).
- STILL PARTIAL: `ModelLifecycleManager` (Phase 2) is NOT yet wired into the run loop — stages don't call `with_model`/`switch` to sequentially load per-`resolved_plan` lanes; each lane call currently relies on Ollama's own load/keep_alive. Full sequential VRAM handoff per quality-slider lane assignment is the main remaining integration (fold into P6 or a P5.1). Also: LLM query_planner still heuristic (optional, low priority).

**Phase 6 DONE (`44b0bea`) — ALL 6 PHASES COMPLETE:**
- Wired the Phase 2 lifecycle into the run loop (the gap): `orchestrator._switch_lane(stage)` loads the stage's `resolved_plan` lane model via LaneRoster, evicting the previous (one model resident, no VRAM stacking); emits switch telemetry; frees the model at FINALIZE. `main.py` builds ModelLifecycleManager + LaneRoster when Ollama reachable.
- `docs/architecture/model-lanes.md` documents the whole LLM-driven system. Security confirmed (paper text = data, agent-history summaries-only + redaction).
- 392 tests pass; mypy+ruff clean (86 files).

**LOW-PRIORITY REMAINING (optional, next sessions):**
- LLM query planner still heuristic (works fine; low value).
- Overnight/synth_b IQ3 lanes are configured but only used if the quality slider/plan assigns them; not yet exercised live end-to-end.
- Not pushed / no PR — user has not asked to push. Branch `feat/llm-fulltext-lanes` has Phases 0-6.
- Consider a live full campaign on a real OA-paper query at `--quality 0.9` to exercise the full multi-lane handoff path end-to-end (unit-tested; not yet run live as a single campaign).
- **Correct model tags:** user should supply real Ollama tags (or confirm the background-pull resolved ones) to replace the speculative lane tags; IQ3 lanes = synthesis/overnight only, never deep extraction.
- Env: RTX 5080 16GB VRAM + 64GB RAM. Ollama auto-offloads to RAM (no custom bridge). MoE tolerates offload; dense does not.

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
    - `src/research_engine/screening/criteria.py`: `BooleanCriterion`, `NumericCriterion`, `LLMRubricCriterion`, `MatchMode`, `CriterionType`, plus factory + default academic criteria.
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
  - Implemented Phase 5: adversarial verification + evaluation apparatus.
    - `src/research_engine/adversarial/challenge.py`: `Challenge`, `VerificationResult`, `ChallengeDispatcher`, plus dict helpers.
    - `src/research_engine/adversarial/devil.py`: `DevilAgent` rule-based challenger with optional frontier-model deep audit.
    - `src/research_engine/adversarial/verifier.py`: `Verifier` checks quoted evidence, DOI shape, source locators, and URL reachability.
    - `src/research_engine/evaluation/harness.py`: `EvaluationHarness` computes claim, challenge, verification, citation, coverage, and quality metrics.
    - `src/research_engine/evaluation/reporter.py`: `Reporter` produces a Markdown insight brief with claims, evidence, challenges, and caveats.
    - `src/research_engine/evaluation/improvement.py`: `ImprovementProposer` emits candidate R### deltas (never auto-applies).
    - `src/research_engine/evaluation/deep_audit.py`: `DeepAuditor` stub with frontier-model audit path.
    - `src/research_engine/orchestrator.py`: `ADVERSARIAL`, `EVALUATE`, and `DELIVER` stage handlers; persists challenges, verifications, evaluation report, and insight brief.
    - `src/research_engine/extraction/structured.py`: added `paper` to `extracted_source_to_dict()` and `extracted_source_from_dict()` so adversarial stages can reconstruct sources.
    - Tests: 14 new adversarial/evaluation unit tests, total 148 tests, 85% coverage.
  - Updated `.claude/agents/evaluation-router.md` keyword table for orchestrator integration, main.py, and state.
  - Added R028–R033 learned-route deltas to `.claude/research_engine-routes.md` for Phase 5 subsystems.
  - Implemented Phase 6 monitoring/telemetry/status + closed Phase 0–4 gaps.
    - `src/research_engine/llm/__init__.py`: lazy `__getattr__` imports for `AnthropicClient` / `OllamaClient`; no hard runtime dependency on optional clients.
    - `config/default.yaml`: conservative defaults for Unpaywall email, rate limits, browser timeout/retries, and enabled sources.
    - `.claude/agents/{discovery,browser,extraction,evaluation}-router.md`: added `FROZEN EVAL` read-only mode to all four router agents.
    - `src/research_engine/extraction/pdf_converter.py`: `convert_bytes()` for in-memory PDF conversion preserving original byte metadata.
    - `src/research_engine/extraction/structured.py`: URLPolicy-gated full-text fetch with PDF conversion, markdownify HTML extraction, and abstract fallback; wired through `orchestrator.py` via `resolved_map`.
    - `src/research_engine/monitoring/progress.py`: `StageProgressTracker` with uniform/custom weights.
    - `src/research_engine/monitoring/estimator.py`: `TimeEstimator` using per-campaign stage history.
    - `src/research_engine/monitoring/calibrator.py`: `Calibrator` normalizing stage weights from observed durations.
    - `src/research_engine/monitoring/telemetry.py`: `TelemetryAnalyzer` with stuck-stage, stage-failure, and thrashing alerts.
    - `src/research_engine/cleanup/janitor.py`: `CleanupJanitor` vacuums SQLite state DB without touching research artifacts.
    - `src/research_engine/orchestrator.py`: `INIT`, `PLAN`, `FINALIZE` handlers; telemetry/estimator/progress/analyzer integration; `status_snapshot()`; `_run_adversarial` uses `ChallengeDispatcher`; `_run_evaluate` wires `ImprovementProposer` and optional `DeepAuditor`.
    - `src/research_engine/main.py`: `_make_orchestrator` constructs `TimeEstimator`; `status` command prints progress, ETA, remaining stages, and alert count.
    - Tests: 191 tests collected, 88% coverage (`python -m pytest -q`).
  - Added R034–R041 learned-route deltas to `.claude/research-engine-routes.md` for Phase 6 / gap-closure subsystems.
  - Implemented Phase 7: campaign analytics dashboard, model-stack validation, production config loading, and storage cache.
    - `src/research_engine/dashboard.py`: `CampaignDashboard` aggregates campaign status/stage/duration metrics, per-campaign summaries with stage timings, and markdown report generation.
    - `src/research_engine/main.py`: added `report` and `validate-models` CLI commands.
    - `src/research_engine/llm/validator.py`: `ModelStackValidator` pings every configured provider, validates specific model availability, and checks for a small-capacity local model (Gemma/Qwen/Phi/Llama class).
    - `src/research_engine/config.py`: loads `config/default.yaml` with `EngineConfig.get()` dotted access and optional `config_overrides`; added `cache_db_path()`.
    - `src/research_engine/storage/cache.py`: `SourceCache` SQLite-backed cache for discovered `Paper` records keyed by query/source.
    - `src/research_engine/llm/model_registry.py`: moved provider client imports inside `build_provider()` so importing the registry no longer requires optional runtime dependencies.
    - Tests: 31 new unit tests for dashboard, config, validator, and cache; total 219 tests, 88% coverage.
- Open:
  - Continue adversarial review of browser policy and unblocking flow.
  - Wire `SourceCache` into `DiscoveryPipeline` for automatic cache hits/misses (module exists; integration pending).
  - Expand integration tests for `report` and `validate-models` CLI commands.
- Blocked: none.
- Risks:
  - Ethical/legal boundary for "advanced penetration techniques" must remain pinned to authorized/defensive/public-only scope as browser capabilities grow.
  - Local model capability assumption (Gemma/Qwen-class) must be validated during Phase 4 screening/extraction.
  - Unblocking campaigns must not drift into gray-area sources; the SSRF/robots.txt policy is the guardrail.

## v0.1.0 Finish Session — 2026-07-07
- Branch: `finish-v0.1.0` (cut from the `phase-5-adversarial` finish work).
- Bundles A–D audit:
  - ✅ SourceCache wired into `DiscoveryPipeline` (`src/research_engine/discovery/pipeline.py`).
  - ✅ MCP adapter exposes `research_engine_run` and `research_engine_status` with query length / source caps and project-root traversal guard (`src/research_engine/mcp_adapter.py`).
  - ✅ `scripts/github_pr.py` + `scripts/end_session.py` implemented with dry-run default, branch guards, and git-repo validation.
  - ✅ `src/research_engine/cleanup/dedup_files.py` hash-based dedup wired into `CleanupJanitor`.
  - ✅ Architecture docs populated under `docs/architecture/` and Main AI runbook at `docs/runbooks/main-ai-integration.md`.
  - ✅ `Dockerfile` + `docker-compose.yml` added (multi-stage Python 3.12).
  - ✅ E2E campaign test (`tests/e2e/test_campaign.py`) passes with mocked sources.
- Security hardening applied:
  - `URLPolicy._is_public_ip` now rejects multicast/reserved/private/loopback.
  - `URLPolicy._decode_host` percent-decodes hostnames until stable; non-ASCII/IDNA hostnames blocked unless allow-listed.
  - `ssrf_guard.safe_request` reconstructs the response with the original URL so the pinned-IP URL never leaks.
  - `cdp_driver.py`: context-level request routing intercepts every page/popup; popup closes immediately after routing.
  - `discovery/resolver.py`: Unpaywall OA URLs re-validated with `resolve_hosts=True`; RuntimeError from SSRF guard sanitized.
  - `scripts/end_session.py` and `scripts/github_pr.py` validate git repo presence and refuse `main` without `--allow-main`.
- Verification:
  - `pytest -q` → all tests passing, 87% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `.claude/router_eval/*.py` self-checks → all green.
  - `bandit -r src` → 0 HIGH/CRITICAL findings.
  - `scripts/end_session.py` dry-run → completes without touching remotes.
  - `tests/e2e/test_campaign.py` and `tests/integration/test_mcp_adapter.py` pass.
- Security/code review findings fixed in this session:
  - Removed non-existent `WebSocket.close()` handler; HTTP upgrade is already blocked by context-level routing.
  - Prevented internal-IP disclosure in policy / SSRF guard error messages.
  - Fixed `end_session.py` so `github_pr.py` stages/commits/pushes/opens PR instead of committing twice.
  - Added module-level mocked-DNS fixture to `tests/unit/discovery/test_resolver.py` so unit tests no longer hit real DNS.
  - `CDPDriver._fetch` now applies per-action `BrowserAction.headers` via `page.set_extra_http_headers`.

## State of the Build
- **Current work: LLM-driven full-text research engine — PR #17 OPEN** (branch `feat/llm-fulltext-lanes` → `main`, 30 commits).
  - https://github.com/isaac233/Research-Engine/pull/17
  - 7 model lanes + VRAM lifecycle, quality/speed + volume sliders + constraint triangle, replication-grade full-text extraction (methods/data/results), synthesizer + handoff docs, model/GPU telemetry.
  - Audit fixed two blockers that made real research impossible: TLS trust-store (truststore) + gzip double-decode.
  - **Verified:** ~395 tests green, mypy + ruff clean; live end-to-end campaign delivered replication-grade `Insights.MD` from full-text arXiv papers on GPU.
- `main` still at **v0.1.0** (`33c393d`, PR #12, tag `v0.1.0`) until #17 merges.
- To resume next session: `git checkout feat/llm-fulltext-lanes`; read the "PUSHED — PR #17" + audit sections above and `docs/architecture/model-lanes.md`.
- Optional follow-ups: Semantic Scholar API key (429s without it, handled); LLM query planner (still heuristic); a live `--quality 0.9` full multi-lane campaign.

## Next Priority Tasks
1. Gather real-world usage feedback and bug reports from v0.1.0.
2. Plan v0.2.0 scope (likely: DuckDB corpora store, async pipeline, richer browser unblocking, production telemetry sink).
3. Keep router eval baseline current as the codebase grows.

## Decisions / Assumptions
- ADR-001: Python 3.12+ primary; SQLite for state, DuckDB for corpora.
- ADR-002: Port router/eval pattern from Financial Model Training Data.
- Load-bearing assumption: local models can drive deterministic discovery/screening with adversarial oversight.

## v0.1.0+ Standards Document
- Added `Standards.MD` (PR #14) capturing all quality, organization, security, ethics, monitoring, source-management, and session-ritual requirements from `Research Engine Prompt1.MD`.
- It includes pre-change and post-change verification checklists. **Review `Standards.MD` before starting and after completing any future work.**

## v0.1.0+ Source Memory & Agent History Session — 2026-07-07
- Added two searchable SQLite databases to make the engine's prior work reusable and auditable:
  - `src/research_engine/storage/source_memory.py`: `SourceMemory` catalog of good sources with topic/information tags, access methods, reliability scores, search hints, and FTS5 full-text search.
  - `src/research_engine/storage/agent_history.py`: `AgentHistory` append-only audit log of agent actions with URL/API, request/response summaries, outcomes, reasons, evidence links, and redacted headers.
- Added `src/research_engine/storage/_redaction.py` for shared URL/secret/metadata sanitization and `src/research_engine/orchestrator_instrumentation.py` to keep `orchestrator.py` under 800 lines.
- `EngineConfig` gained `source_memory_db_path()` and `agent_history_db_path()`.
- `_make_orchestrator` in `src/research_engine/main.py` now constructs both stores and injects them into `Orchestrator`.
- `Orchestrator` records stage transitions, browser unblocking probes, and discovery search results into `AgentHistory`; discovery sources are remembered in `SourceMemory`.
- Added input-length and URL-policy validation before passing untrusted query/context/URLs to the browser, discovery pipeline, and extractor.
- Added unit tests:
  - `tests/unit/storage/test_source_memory.py`
  - `tests/unit/storage/test_agent_history.py`
  - `tests/unit/storage/test_redaction.py`
  - updated `tests/unit/test_orchestrator.py`
- Updated architecture docs in `docs/architecture/storage.md`.
- Merged via PR #16: https://github.com/isaac233/Research-Engine/pull/16 (commit `efc4e147a48ea3cf13db29427742d335ed4fb57e`).
- Verification:
  - `pytest -q` → all tests passing, 87% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `bandit -r src` → 0 HIGH/CRITICAL findings in changed modules (11 pre-existing LOW/MEDIUM issues elsewhere).

## Self-Research & Golden-Answer Eval Session — 2026-07-08
- Added a deterministic golden-answer evaluation harness and a self-research loop that runs the engine on its own codebase.
  - `src/research_engine/evaluation/harness.py`: `EvaluationReport` gained `precision`/`recall`/`f1_score`; `EvaluationHarness.evaluate()` accepts `expected_claims` and computes precision/recall/F1 via maximum bipartite (Kuhn) claim matching. Paraphrase matching guards against negation, directional opposites, morphological antonyms, qualifier/scope mismatch, numeric mismatch, causal-vs-correlational mismatch, and tautologies.
  - `src/research_engine/main.py`: new `self-eval` CLI command runs a fixture of synthetic sources with known expected claims and reports mean F1, utility mean F1, and a trap robustness score; `--output`/`--force`/`--threshold` options; shared `_validate_output_path` (extracted from `report`).
  - `src/research_engine/extraction/structured.py`: richer claim markers, adjacent-claim merging for multi-sentence findings, confidence scoring (quantitative claims → high), and confidence-based filtering to raise precision.
  - `src/research_engine/evaluation/improvement.py`: R050/R051/R052 delta candidates driven by F1, missing expected claims, and a saturated benchmark.
  - `src/research_engine/evaluation/reporter.py` + `orchestrator.py`: surface precision/recall/F1 in the brief and persisted evaluation report.
  - `scripts/self_research.py`: builds a local doc/source corpus, monkey-patches discovery to return it, drives a full campaign through the orchestrator, then runs the golden-answer benchmark and captures metrics/proposals to JSON. Runtime + F1 thresholds gate exit code.
  - `tests/fixtures/eval_qa.json`: 14 fixtures — 7 utility (all score F1 1.0) + 7 adversarial traps (all correctly score F1 0.0, robustness 1.0).
  - Tests: `tests/unit/evaluation/test_harness.py` (+215), `test_improvement.py`, `test_reporter.py`, `tests/unit/extraction/test_structured.py`, `tests/integration/test_self_eval.py`, `tests/integration/test_self_research.py`.
  - `pyproject.toml`: `pytest.pythonpath` now includes `.` so `scripts.self_research` is importable in tests.
  - `.gitignore`: ignore `data/self_research/` and `coverage.json` generated artifacts.
- Verification:
  - `pytest --no-cov -q` → all tests passing; full run 88% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `bandit -r src scripts` → 0 HIGH/CRITICAL (18 pre-existing LOW, 1 MEDIUM).
  - `research-engine self-eval --fixture tests/fixtures/eval_qa.json` → utility F1 1.0, robustness 1.0.
  - `python scripts/self_research.py` → completes in ~0.25s, 20-doc corpus, campaign `completed`.

## Anti-Poison Hardening + 3× Self-Improvement Loop — 2026-07-08

### Anti-poison audit (pre-loop)
- Verified every learning surface can improve without self-poisoning; fixed two gaps (commit `08b148e`):
  - `SourceMemory.remember`: `reliability_score` now defaults to `None` — an incidental re-remember keeps the learned score (new source → 0.5); explicit score still updates. Kills the destructive `INSERT OR REPLACE` regression.
  - `research-engine-router.md`: added FROZEN EVAL read-only mode (the only router lacking it) so eval runs can't mutate the shared learned-routes memory.
- Safe already: `ImprovementProposer` (all `auto_apply:False`, never applied), router routes log (PROVISIONAL-until-verified, one-delta/miss, `.claude/router_eval/replay` contradiction check), `Calibrator` (0.1 floor, normalized, ETA-only).

### Self-improvement loop (ran the engine on itself 3×, verified each insight, implemented sound ones)
- **Loop 1** (`b729b19`): engine flagged R052 "benchmark saturated at F1 1.0". Probed matcher → found `12 mg` matched `12 kg`. Added unit-aware numeric conflict (compares (number, unit) against a fixed unit set) + `unit-mismatch` trap fixture.
- **Loop 2** (`704e0bd`): R052 again. Found `A outperforms B` matched `B outperforms A`. Added comparative operand-swap guard (same word multiset reordered around a comparative marker → conflict) + `comparative-swap` trap fixture. Benign non-comparative reorders still match.
- **Loop 3** (`a7755ca`): self-research's own metrics came back null. Root cause: corpus screened to 0 included papers (20 scored, 0 kept) → EXTRACT/ADVERSARIAL/EVALUATE/DELIVER silently no-op'd via `_run_stub` reporting "not yet implemented", campaign completed with empty brief and no signal. Added `_run_skipped(reason)` for honest skip reporting + `screening_yielded_zero` meta flag so an empty deliverable is visible, not silent.
- Golden-answer benchmark now 17 fixtures (7 utility + 10 traps); self-eval utility F1 1.0, robustness 1.0. All tests/mypy/ruff clean each loop.

### Known / open for next session
- **Root observation still open:** the default screening criteria exclude the self-research doc corpus entirely (0/20). The loop-3 fix makes this *visible* but does not tune criteria — a docs corpus is genuinely not "academic papers". Next: either (a) add a doc-oriented criteria set for self-research, or (b) have `scripts/self_research.py` assert `screening_yielded_zero` is False so the benchmark exercises the full evaluate path. Until then self-research exercises only the golden-answer benchmark path, not the live-campaign evaluate path.
- Benchmark keeps reporting "saturated" each loop because fixed traps pass; that is expected (bar rises each loop). Real signal is the matcher weaknesses found by probing, not the generic R052 text.
- Branch `feat/self-research-golden-eval`; commits `08b148e`, `b729b19`, `704e0bd`, `a7755ca` on top of `67a21cb`. NOT pushed, no PR.

## Notes for Next Agent
- All routers live under `.claude/agents/` and learned routes under `.claude/research-engine-routes.md`.
- The eval harness under `.claude/router_eval/` must remain isolated from `src/`.
- `scripts/end_session.py` is a stub; do not run it for real until Phase 9.
- The `Research/` folder layout is documented in `docs/plan/master_plan.md` section 4.13 and implemented in `src/research_engine/config.py`.
- Discovery subsystem is fully wired into the orchestrator; start Phase 4 with `screening/criteria.py` and `screening/ranker.py`.
- New Phase 7 modules: `dashboard.py`, `llm/validator.py`, `storage/cache.py`; CLI commands: `report`, `validate-models`.
