# Evaluation

Evaluation measures campaign quality and produces an improvement signal. It is
the engine's self-improvement loop.

## Components

- `EvaluationHarness` — runs a campaign against a golden answer or human
  judgment set and returns precision/recall/F1.
- `Reporter` — renders results to JSON/Markdown, including token usage and
  wall-clock time.
- `ImprovementProposer` — suggests concrete changes to prompts, adapters, or
  thresholds based on failure patterns.
- `DeepAudit` — adversarial re-review of a completed campaign looking for
  silent failures and coverage gaps.

## Metrics

- `precision@k` — fraction of top-k claims that are supported.
- `recall@k` — fraction of expected claims found.
- `F1` — harmonic mean of precision and recall.
- `token_savings` — tokens the main AI did not have to spend because the engine
  handled discovery and synthesis.

## Baseline

v0.1.0 records an evaluation baseline in `docs/eval/baseline_v0.1.0.md`.
Subsequent releases must not regress the baseline without an explicit note.

## Usage

```powershell
python -m research_engine.evaluation.harness --dataset tests/fixtures/eval_qa.json
```

The harness is also exercised by CI on every PR.
