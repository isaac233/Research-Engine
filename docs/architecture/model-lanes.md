# Model Lanes & LLM-Driven Pipeline

How the engine drives local models to produce replication-grade insight.

## Lanes

`config/model_lanes.yaml` declares seven lanes, each a task role mapped to a
model tag with an installed fallback:

| Lane | Role | Default use |
|---|---|---|
| `fast` | reviewer | high-volume screening (relevance/authority/currency) |
| `deep` | worker | full-text methods/data/results extraction |
| `overnight` | worker | max-quality batch runs |
| `online_a` / `online_b` | planner | online research / query planning |
| `synth_a` / `synth_b` | synthesizer | insight synthesis from deep reads |

`scripts/pull_models.py` pulls each tag and writes `data/model_pull_report.json`;
`LaneRoster.from_yaml` resolves each lane's *effective* tag from that report, so
a missing/speculative tag degrades to its installed fallback instead of 404ing.
Run `research-engine validate-models` for a live per-lane availability table.

## One provider, sequential residency

A single `OllamaClient` drives every lane via a per-call `model` override
(`think=false` — thinking models otherwise return empty content). Seven models
cannot co-reside in 16 GB VRAM, so `ModelLifecycleManager` loads one model, runs
its stage, and evicts it (`keep_alive=0`) before loading the next — at most one
resident, no VRAM stacking. The orchestrator calls `_switch_lane(stage)` before
extraction and synthesis (using the stage's lane from the resolved plan) and
frees the model at `FINALIZE`. Ollama auto-offloads to the 64 GB system RAM when
a model exceeds VRAM (MoE tolerates this; dense is slow).

## Full-text extraction (the core)

`StructuredExtractor` fetches + converts full text, then `LLMSectionExtractor`
(deep lane) extracts **methodology / data / results / conclusions** plus claims
with **verbatim evidence quotes**. A substring guard drops any claim whose
evidence is not literally in the source (anti-hallucination). Long papers are
chunked (map-reduce). When only an abstract is available it is flagged
`meta.degraded = abstract_only` — no fabricated methods section. Falls back to
regex extraction when no local model is reachable (CI/offline).

## Constraint triangle & sliders

`planning/constraint_triangle.solve` reconciles {quality, time_budget,
source_volume}: specify any two → the third is derived. A time budget governs
(no slider, auto-optimize quality). With fewer than two and no budget, the `run`
CLI shows a quality/speed + volume slider (`cli/slider.py`: arrow-key via
optional `prompt_toolkit`, numbered fallback, never blocks a non-interactive
run). Quality tier → per-stage lane assignment, persisted to campaign meta.

## Synthesis & quality floor

`Synthesizer` (synth lane) turns the kept sources' deep reads into a brief
biased toward reproduction; `unique_insight_filter` enforces the source-volume
contract (≥1 new insight per kept source). `QualityFloor.check` is the speed-mode
backstop: goal addressed, no omission, no fabrication. `HandoffDoc`s are written
on model switches so intent survives lane changes.

## Visibility

`GpuProbe` reports VRAM + per-model RAM-offload split; telemetry emits
`model_load/unload/switch`, `model assignment`, and `gpu_snapshot` events. The
`status` command shows which model ran each stage and live VRAM — so the local
model's work is visible.

## Security

Fetched paper text is treated as DATA, not instructions (prompt-injection guard
in `extraction/prompts.py`). URLs pass `URLPolicy`; agent-history stores
summaries, never raw full text, and redacts secrets/headers.
