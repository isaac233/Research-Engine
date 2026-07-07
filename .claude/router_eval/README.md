# router_eval — Research Engine Router Evaluation Harness

Makes the `research-engine-router` context-router **measurable and self-improving**
instead of trust-me. Pure stdlib Python, isolated from `src/research_engine/`.

## Run it

```powershell
cd .claude/router_eval
python table_parser.py
python router_sim.py
python capture_outcome.py
python run_benchmark.py
python drift_check.py
python test_log_robustness.py
```

Every module has an assert-based `__main__` self-check; run it to validate.

## Capabilities

| Module | Proves |
|---|---|
| `table_parser.py` | parses every router markdown file into keyword tables + learned log |
| `router_sim.py` | deterministic Python mirror of routing decisions |
| `outcome_record.py` | data model for predicted vs actual file sets |
| `capture_outcome.py` | learns from `git diff` ground truth; proposes calibrated R### deltas |
| `gold_from_git.py` | builds external git-history gold from commit diffs |
| `run_benchmark.py` | scores sim vs gold (precision/recall/F1/waste) |
| `fidelity_gate.py` | flags when the cheap sim diverges from the real agent |
| `drift_check.py` | detects stale paths and uncovered modules |
| `token_estimate.py` | estimates token cost of a file set |
| `measure_savings.py` | token savings vs naive whole-dir load |
| `replay.py` | longitudinal self-improvement + collapse-free proof |
| `test_log_robustness.py` | chaos tests on the learned log |

## v0.1.0 baseline

Recorded 2026-07-07 against the `phase-5-adversarial` finish branch:

| Metric | Value | Notes |
|---|---|---|
| Router sim F1 | 0.00 | Conservative lower bound on last 3 commits (commit messages do not overlap router keyword vocabulary) |
| Naive whole-dir tokens | ~4.9 M | All `src/research_engine/**/*.py` loaded at once |
| Router tokens | ~75 | Predicted leaf set for a representative campaign task |
| Token savings ratio | 65513x | `naive_tokens / router_tokens`; lower bound is a large multiple |

## Honest interpretation

- The Python `router_sim` is a conservative lower bound + regression detector, NOT a faithful mirror of the LLM router. The authoritative score is the real agent run on git-history gold.
- The win that must hold in every view: the router is Pareto-better than the naive whole-dir baseline — higher precision and lower tokens, with competitive F1.
- A baseline F1 of 0.00 on git-history is expected: recent commits are source-level changes, not natural-language router tasks. The token-savings signal is the primary regression guard at this stage.
