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

## LEARNED — empty

## RETIRED — empty
