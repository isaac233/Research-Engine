# Research Engine

A model-agnostic, locally-driven research apparatus that turns a natural-language
research request from a main AI (Claude Code / Opus / Kimi) into a fully
executed internet research campaign—delivering structured insights, evidence
maps, and status updates while consuming minimal premium-AI tokens.

> **Status:** `main` = v0.1.0. Active branch `feat/llm-fulltext-lanes` (PR #17)
> makes the engine genuinely LLM-driven: local models read **full-text
> methods/data/results** for replication-grade insight, routed across **7 model
> lanes** by a quality/speed + source-volume slider (specify any two of
> quality/time/volume and the third is derived), with sequential VRAM
> load/unload and model/GPU telemetry. ~395 tests, mypy + ruff clean; verified
> by a live end-to-end campaign. See `docs/architecture/model-lanes.md`.

## What it does

1. Accepts a research request from your main AI via MCP or CLI.
2. Plans, discovers, screens, extracts, and challenges sources using local
   models (Ollama/Gemma/etc.) and deterministic adapters.
3. Adversarially verifies every insight so hallucinated claims never reach the
   main AI.
4. Reports progress %, ETA, current stage, and remaining steps on demand.
5. Delivers a Markdown insight brief with numbered claims, source links, and
   confidence labels.
6. **Never gives up on a blocker:** if the main AI says "I can't find…" or hits
   a missing resource, the engine runs an unblocking research campaign and
   returns actionable solutions with sources, access terms, and next steps.
7. Cleans up caches and duplicates at the end of every session, then opens a
   GitHub PR.

## Quick start

```powershell
# Install
pip install -e .

# Run a campaign from the CLI
research-engine run "What are the latest methodological improvements in LLM systematic literature reviews?"

# Check status
research-engine status <campaign-id>

# Generate an analytics report
research-engine report

# Validate configured models
research-engine validate-models
```

The default output layout in the host project is:

```
Research/
├── Insights.MD                                  # folded aggregation of all briefs
└── <campaign-slug>/
    ├── <campaign-slug>_Insights.MD            # individual campaign brief
    └── evidence_map.json
```

## Using the MCP adapter

Claude Code can call the engine as an MCP tool:

```json
{
  "mcpServers": {
    "research-engine": {
      "command": "python",
      "args": ["-m", "research_engine.mcp_adapter"],
      "cwd": "C:/Users/Isaac/OneDrive/Desktop/beta/Research Engine"
    }
  }
}
```

Tools exposed:

- `research_engine_run(query)` — start and run a campaign end-to-end.
- `research_engine_status(campaign_id)` — query current progress and ETA.

See [`docs/runbooks/main-ai-integration.md`](docs/runbooks/main-ai-integration.md)
for a full step-by-step runbook.

## Project norms

- **Model-agnostic:** every LLM interface goes through a provider abstraction;
  swap models in `config/models.yaml`.
- **Local-first:** primitive local AI drives the bulk of the work; frontier
  models only audit and synthesize.
- **Adversarial by default:** a `Devil` agent challenges every claim, and a
  `Verifier` re-runs source lookups.
- **Self-improving routers:** `.claude/agents/*-router.md` use learned routes
  (`R###` itemized deltas) with non-self-poisoning memory.
- **Ethical hard floor:** only public or authorized sources; robots.txt, rate
  limits, and SSRF policy are enforced. No credential bypass, no access-control
  evasion, no law breaking.
- **Elite organization:** no dead files, no dead branches; every session ends
  with a PR.

## Architecture

| Subsystem | Purpose | Key files |
|---|---|---|
| Orchestrator | Campaign lifecycle state machine | [`docs/architecture/orchestrator.md`](docs/architecture/orchestrator.md) |
| Browser | AI-only browser: CDP/Playwright, raw HTTP, GraphQL, robots.txt, SSRF policy | [`docs/architecture/browser.md`](docs/architecture/browser.md) |
| Discovery | Multi-source academic/web search, dedup, snowball, full-text resolution | [`docs/architecture/discovery.md`](docs/architecture/discovery.md) |
| Screening | Criteria-driven source ranking | [`docs/architecture/screening.md`](docs/architecture/screening.md) |
| Extraction | HTML/PDF → Markdown + structured fields + citations | [`docs/architecture/screening.md`](docs/architecture/screening.md) |
| Adversarial | Devil + Verifier + challenge dispatcher | [`docs/architecture/adversarial.md`](docs/architecture/adversarial.md) |
| Evaluation | Harness, reporter, improvement proposer, deep audit | [`docs/architecture/evaluation.md`](docs/architecture/evaluation.md) |
| Monitoring | Progress %, ETA, calibration, anomaly detection | [`docs/architecture/monitoring.md`](docs/architecture/monitoring.md) |
| Storage | SQLite state/cache, artifact manager, cleanup janitor | [`docs/architecture/storage.md`](docs/architecture/storage.md) |
| Benchmark | DeepResearch Bench (RACE + FACT) scoreboard vs the published Opus/Gemini bar | [`docs/architecture/benchmark.md`](docs/architecture/benchmark.md) |

## Development

```powershell
# Run tests with coverage
python -m pytest -q

# Lint
ruff check .

# Type check
mypy src/research_engine

# End-of-session ritual (dry-run by default)
python scripts/end_session.py --message "feat: describe change"

# Open a PR (dry-run by default)
python scripts/github_pr.py --message "feat: describe change" --branch finish/feature
```

## Benchmarking (does it beat Opus?)

The engine scores itself on **DeepResearch Bench** — 100 PhD-level tasks graded by
**RACE** (report quality vs a reference report) and **FACT** (citation accuracy) —
so it can be compared head-to-head against the published Opus/Gemini leaderboard.

```powershell
# Smoke run: 3 English tasks, local Ollama judge (no external auth)
research-engine bench --tasks 3 --judge ollama

# Closest to official: Gemini judge (authenticate `gemini` once first)
research-engine bench --tasks 100 --judge gemini
```

Writes `Research/benchmarks/<date>_scorecard.MD` with the engine's RACE/FACT next
to the published bar and the weakest dimension to improve. See
[`docs/architecture/benchmark.md`](docs/architecture/benchmark.md).

## Docker

```powershell
docker build -t research-engine .
docker run --rm research-engine
```

See `Dockerfile` and `docker-compose.yml` for details.

## Repository

- GitHub: `https://github.com/isaac233/Research-Engine`

## License

MIT
