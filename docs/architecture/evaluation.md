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

Claims are matched to golden answers with maximum bipartite matching over a
paraphrase-aware predicate. Semantic-conflict guards reject opposite-meaning
matches: negation parity, directional opposites, morphological antonyms,
qualifier/scope mismatch, numeric **and unit** mismatch (`12 mg` ≠ `12 kg`),
causal-vs-correlational, comparative operand swap (`A outperforms B` ≠
`B outperforms A`), and tautologies. Fixtures are tagged `utility` or `trap`;
traps must score F1 0 (robustness), so a saturated benchmark (all pass) signals
the need for a harder fixture.
- `token_savings` — tokens the main AI did not have to spend because the engine
  handled discovery and synthesis.

## Baseline

v0.1.0 records an evaluation baseline in `docs/eval/baseline_v0.1.0.md`.
Subsequent releases must not regress the baseline without an explicit note.

## Usage

```powershell
research-engine self-eval --fixture tests/fixtures/eval_qa.json
```

Reports mean F1, utility mean F1, and trap robustness; `--output` writes a JSON
report and `--threshold` fails the command below a mean-F1 floor. The harness is
also exercised by CI on every PR.
