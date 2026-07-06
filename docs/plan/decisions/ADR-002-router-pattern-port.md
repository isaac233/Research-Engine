# ADR-002 — Router and Evaluation Pattern Port

## Decision
Port the self-improving router/evaluation pattern from `Financial Model/Financial Model Training Data/.claude/router_eval/` to this project.

## What we port
- Top-level + sub-system routers under `.claude/agents/`.
- Learned-routes log with `R###` itemized deltas at `.claude/research-engine-routes.md`.
- Isolated `router_eval/` harness: `table_parser`, `router_sim`, `capture_outcome`, `run_benchmark`, `drift_check`, `replay`, `test_log_robustness`.

## What we change
- Keyword tables target research-engine subsystems (browser, discovery, extraction, evaluation).
- Eval harness imports nothing from `src/research_engine/`; it parses the agent markdown files directly.

## Load-bearing assumption
Context routing precision saves enough tokens on research-engine tasks to justify the maintenance cost of the learned log. If the repo stays small (<50 files), the router may be overkill and should be simplified.
