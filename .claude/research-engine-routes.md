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
| R028 | adversarial | Devil agent, challenge claims, evidence, coverage | `src/research_engine/adversarial/devil.py` | Read devil first | phase-5 | 1 | 2026-07-06 | PROVISIONAL |
| R029 | adversarial | Verifier, hallucination, DOI, quote check | `src/research_engine/adversarial/verifier.py` | Read verifier first | phase-5 | 1 | 2026-07-06 | PROVISIONAL |
| R030 | adversarial | Challenge dispatcher, claim response | `src/research_engine/adversarial/challenge.py` | Read dispatcher first | phase-5 | 1 | 2026-07-06 | PROVISIONAL |
| R031 | evaluation | evaluation harness, reporter, metrics | `src/research_engine/evaluation/harness.py`, `src/research_engine/evaluation/reporter.py` | Read harness then reporter | phase-5 | 1 | 2026-07-06 | PROVISIONAL |
| R032 | orchestrator | ADVERSARIAL stage, EVALUATE stage, DELIVER stage | `src/research_engine/orchestrator.py`, `src/research_engine/adversarial/`, `src/research_engine/evaluation/` | Read orchestrator stage handlers first | phase-5 | 1 | 2026-07-06 | PROVISIONAL |
| R033 | evaluation | deep audit, anomaly, frontier audit | `src/research_engine/evaluation/deep_audit.py` | Read deep auditor first | phase-5 | 1 | 2026-07-06 | PROVISIONAL |
| R034 | llm | lazy provider imports, AnthropicClient, OllamaClient optional deps | `src/research_engine/llm/__init__.py` | Read `__init__.py` `__getattr__` first | phase-6 | 1 | 2026-07-07 | PROVISIONAL |
| R035 | config | default.yaml, engine config, unpaywall, rate limits | `config/default.yaml`, `src/research_engine/config.py` | Read default config then EngineConfig | phase-6 | 1 | 2026-07-07 | PROVISIONAL |
| R036 | routers | FROZEN EVAL, read-only router mode | `.claude/agents/discovery-router.md`, `.claude/agents/browser-router.md`, `.claude/agents/extraction-router.md`, `.claude/agents/evaluation-router.md` | Read relevant router file | phase-6 | 1 | 2026-07-07 | PROVISIONAL |
| R037 | extraction | full-text fetch, PDF bytes, resolved_map, URLPolicy | `src/research_engine/extraction/structured.py`, `src/research_engine/extraction/pdf_converter.py`, `src/research_engine/orchestrator.py` | Read structured extractor + orchestrator EXTRACT stage | phase-6 | 1 | 2026-07-07 | PROVISIONAL |
| R038 | monitoring | progress, ETA, status snapshot, CLI status | `src/research_engine/monitoring/progress.py`, `src/research_engine/monitoring/estimator.py`, `src/research_engine/main.py` | Read progress + estimator + main.py status command | phase-6 | 1 | 2026-07-07 | PROVISIONAL |
| R039 | monitoring | calibrator, telemetry analyzer, alerts | `src/research_engine/monitoring/calibrator.py`, `src/research_engine/monitoring/telemetry.py` | Read calibrator + telemetry analyzer | phase-6 | 1 | 2026-07-07 | PROVISIONAL |
| R040 | cleanup | janitor, finalize, vacuum state DB | `src/research_engine/cleanup/janitor.py`, `src/research_engine/orchestrator.py` | Read janitor + orchestrator FINALIZE stage | phase-6 | 1 | 2026-07-07 | PROVISIONAL |
| R041 | evaluation | improvement proposer, deep auditor, challenge dispatcher | `src/research_engine/evaluation/improvement.py`, `src/research_engine/evaluation/deep_audit.py`, `src/research_engine/adversarial/challenge.py` | Read improvement + deep_audit + challenge dispatcher | phase-6 | 1 | 2026-07-07 | PROVISIONAL |

## LEARNED — empty

## RETIRED — empty
