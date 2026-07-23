# Benchmark — the apples-to-apples scoreboard

**Why this exists.** The engine's ~400 tests prove it *runs correctly*; none prove
it *out-researches Opus*. Without an external, standardized score, "does it beat
Opus?" is a feeling, not a number — and upgrades built on a feeling burn tokens.
The `bench/` package ports **DeepResearch Bench** (arXiv:2506.11763, Apache-2.0)
so the engine is scored on the same 100 PhD-level tasks and the same metrics as
the models on the public leaderboard.

## What it measures

- **RACE** (report quality) — the judge compares the engine's report (article_1)
  against a fixed **reference report** (article_2) on each task's criteria across
  four weighted dimensions: **Comprehensiveness, Insight/Depth,
  Instruction-Following, Readability**. Score is `target/(target+reference)`,
  reported 0–100 where **50 = ties the reference report**.
- **FACT** (citation trustworthiness) — extract every `(fact, url)` cited in the
  report, fetch each URL with the engine's own policy-guarded HTTP + markdownify,
  and have the judge decide whether the source actually supports the claim.
  Yields **Citation Accuracy** (% supported) and **Effective Citations** (count).
  This is the direct measure of the failure the project exists to kill —
  "read only abstracts, waved off discrepancies."

## Layout

```
bench/
├── data/            # vendored, Apache-2.0 (see data/LICENSE.md)
│   ├── query.jsonl        # 100 tasks (50 en + 50 zh)
│   ├── criteria.jsonl     # per-task RACE criteria + weights
│   └── reference.jsonl    # reference reports RACE normalizes against
├── prompts.py       # RACE + FACT judge prompts (ported)
├── score_calc.py    # weighted aggregation + reference normalization
├── judge.py         # build_judge(gemini|ollama|anthropic) + JSON extraction
├── race.py          # RaceScorer
├── fact.py          # FactScorer (reuses browser/raw_http + markdownify)
├── adapter.py       # run one engine campaign -> {id, prompt, article}
├── runner.py        # tasks -> engine reports -> RACE+FACT -> aggregate
├── scorecard.py     # -> Research/benchmarks/<date>_scorecard.MD
└── leaderboard.py   # verified published Opus/Gemini/etc. reference bar
```

## Running

```powershell
# Smoke: 3 English tasks, local Ollama judge (no external auth needed)
research-engine bench --tasks 3 --judge ollama

# Closest-to-official: Gemini judge (authenticate the gemini CLI first:
# run `gemini` once to log in, or set GEMINI_API_KEY)
research-engine bench --tasks 100 --judge gemini
```

Outputs a scorecard at `Research/benchmarks/<date>_scorecard.MD` with the engine's
RACE/FACT next to the published bar, and calls out the **weakest RACE dimension**
— which is the target for the deferred Track B upgrades.

## The judge is model-agnostic

The judge is any `LLMProvider`. Default `gemini` matches the paper's judge family
most closely (Gemini-2.5-Pro was the official RACE judge; Claude-3.7-Sonnet scored
72.28 vs 72.56 human-alignment as a judge too). `ollama` runs fully local for
offline validation but is **not** alignment-validated, so treat local-judge scores
as directional. Swapping to an OpenAI/OpenRouter GPT-5.5 judge (the current
official evaluator) is a config change, not a rewrite.

## Caveats

- A full 100-task run is slow (100 local campaigns + judge calls); start with a
  small `--tasks` subset to validate wiring.
- Cross-judge comparisons are directional, not exact parity. For a
  leaderboard-grade number, use the same judge family the leaderboard uses.
```
