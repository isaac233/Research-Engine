# Research Engine — Learned Routes Log

> Shared learned-routes memory for all Research Engine routers.
> Schema per item: `R### | subsystem | signal | load | tactic | prov | hits | verified | status`
> Learned items WIN over static KEYWORD TABLE on conflict.
> Status: PROVISIONAL until hits ≥ 2 and path confirmed; CONFIRMED after; NEGATIVE for avoidance items (re-tested each run).
> Apply exactly ONE itemized delta per routing miss. Never wholesale rewrite.

## SEEDED — Confirmed

| ID | Subsystem | Signal | Load | Tactic | Prov | Hits | Verified | Status |
|---|---|---|---|---|---|---|---|---|
| R001 | orchestrator | main.py, CLI, launch campaign | `src/research_engine/main.py` | Read entry point first | seeded | 1 | 2026-07-06 | CONFIRMED |
| R002 | orchestrator | campaign state, events, SQLite | `src/research_engine/state.py`, `src/research_engine/events.py` | Read state schema + latest events | seeded | 1 | 2026-07-06 | CONFIRMED |
| R003 | evaluation | progress, ETA, status | `src/research_engine/monitoring/progress.py`, `src/research_engine/monitoring/estimator.py` | Read progress + estimator | seeded | 1 | 2026-07-06 | CONFIRMED |
| R004 | evaluation | end of session, cleanup, PR | `scripts/end_session.py`, `scripts/github_pr.py`, `docs/HANDOFF.md` | Read ritual scripts + handoff | seeded | 1 | 2026-07-06 | CONFIRMED |
| R005 | orchestrator | SQLite, CampaignStore, ResearchRequest | `src/research_engine/state.py` | Read dataclasses + store first | phase-1 | 1 | 2026-07-06 | PROVISIONAL |
| R006 | orchestrator | LLMProvider, Ollama, Anthropic, model registry | `src/research_engine/llm/`, `config/models.yaml` | Read provider + registry first | phase-1 | 1 | 2026-07-06 | PROVISIONAL |
| R007 | orchestrator | telemetry, EventBus, stage receipts | `src/research_engine/events.py`, `src/research_engine/monitoring/telemetry.py` | Read event bus + telemetry first | phase-1 | 1 | 2026-07-06 | PROVISIONAL |
| R008 | browser | CDP, Playwright, Chromium, accessibility tree | `src/research_engine/browser/cdp_driver.py` | Read driver first | phase-2 | 1 | 2026-07-06 | PROVISIONAL |
| R009 | browser | raw HTTP, retry, backoff, headers | `src/research_engine/browser/raw_http.py`, `src/research_engine/browser/fingerprint.py` | Read HTTP client + fingerprints first | phase-2 | 1 | 2026-07-06 | PROVISIONAL |
| R010 | browser | robots.txt, SSRF, URL policy | `src/research_engine/browser/robots.py`, `src/research_engine/browser/policy.py` | Read policy guards first | phase-2 | 1 | 2026-07-06 | PROVISIONAL |
| R011 | browser | GraphQL, API query | `src/research_engine/browser/graphql_client.py` | Read GraphQL helper first | phase-2 | 1 | 2026-07-06 | PROVISIONAL |
| R012 | browser | unblock, blocker, cannot find, missing source | `src/research_engine/browser/unblock_probe.py`, `src/research_engine/orchestrator.py` | Read probe + orchestrator integration first | phase-2 | 1 | 2026-07-06 | PROVISIONAL |
| R013 | discovery | discovery pipeline, DiscoveryPipeline, end-to-end search | `src/research_engine/discovery/pipeline.py` | Read pipeline first | phase-3 | 1 | 2026-07-06 | PROVISIONAL |
| R014 | discovery | source adapters, Semantic Scholar, Crossref, arXiv, OpenAlex, SERP, web crawl | `src/research_engine/discovery/sources/` | Read adapter directory first | phase-3 | 1 | 2026-07-06 | PROVISIONAL |
| R015 | discovery | dedup, snowball, resolver, full text, DOI, PDF | `src/research_engine/discovery/dedup.py`, `src/research_engine/discovery/snowball.py`, `src/research_engine/discovery/resolver.py` | Read dedup/snowball/resolver first | phase-3 | 1 | 2026-07-06 | PROVISIONAL |
| R016 | discovery | query planner, search strategy, keywords | `src/research_engine/discovery/query_planner.py` | Read query planner first | phase-3 | 1 | 2026-07-06 | PROVISIONAL |
| R017 | discovery | Paper, SourceQuery, SearchResult, DiscoveryResult schema | `src/research_engine/discovery/schema.py` | Read schema first | phase-3 | 1 | 2026-07-06 | PROVISIONAL |
| R018 | discovery | source registry, enabled sources, adapter lookup | `src/research_engine/discovery/source_registry.py` | Read registry first | phase-3 | 1 | 2026-07-06 | PROVISIONAL |
| R019 | orchestrator | DISCOVER stage, discovery integration, campaign search | `src/research_engine/orchestrator.py`, `src/research_engine/discovery/pipeline.py` | Read orchestrator integration first | phase-3 | 1 | 2026-07-06 | PROVISIONAL |
| R020 | screening | criteria, include/exclude, rank, SourceRanker | `src/research_engine/screening/criteria.py`, `src/research_engine/screening/ranker.py` | Read criteria then ranker | phase-4 | 1 | 2026-07-06 | PROVISIONAL |
| R021 | extraction | markdownify, HTML to markdown | `src/research_engine/extraction/markdownify.py` | Read markdownify first | phase-4 | 1 | 2026-07-06 | PROVISIONAL |
| R022 | extraction | PDF conversion, pdfplumber, marker | `src/research_engine/extraction/pdf_converter.py`, `src/micro_tools/pdf_to_md/` | Read pdf_converter + micro tool | phase-4 | 1 | 2026-07-06 | PROVISIONAL |
| R023 | extraction | structured extraction, methodology, data, results, claims | `src/research_engine/extraction/structured.py` | Read structured extractor first | phase-4 | 1 | 2026-07-06 | PROVISIONAL |
| R024 | extraction | citation parsing, DOI, references | `src/research_engine/extraction/citation.py` | Read citation parser first | phase-4 | 1 | 2026-07-06 | PROVISIONAL |
| R025 | extraction | conflict detection, project data discrepancy | `src/research_engine/extraction/structured.py` | Read structured extractor conflict logic | phase-4 | 1 | 2026-07-06 | PROVISIONAL |
| R026 | orchestrator | SCREEN stage, EXTRACT stage, campaign integration | `src/research_engine/orchestrator.py`, `src/research_engine/screening/ranker.py`, `src/research_engine/extraction/structured.py` | Read orchestrator stage handlers first | phase-4 | 1 | 2026-07-06 | PROVISIONAL |
| R027 | orchestrator | main.py CLI, launch screening/extraction | `src/research_engine/main.py` | Read main.py entry point first | phase-4 | 1 | 2026-07-06 | PROVISIONAL |

## LEARNED — empty

## RETIRED — empty
