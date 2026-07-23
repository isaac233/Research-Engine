# Next Session Kickoff — Track B (for fable 5)

You are picking up the **Research Engine** project mid-stream. Read this top-to-bottom,
then read `HANDOFF.md` (the "DeepResearch Bench scoreboard — Track A" section) and
`docs/architecture/benchmark.md`. Everything you need is here.

## The mission (from `Research Engine Prompt1.MD`)
Build a research apparatus so strong that a primitive local model driving it beats
Opus 4.8 at research, at a fraction of the tokens — grounded, citation-rich reports
with adversarial anti-cover-up measures. The user's premium AI only frames the need
and receives verified insights.

## What just happened (Track A — DONE)
We built the **scoreboard first** (you can't beat Opus without measuring against it).
Ported **DeepResearch Bench** (arXiv:2506.11763, Apache-2.0) into a `bench/` package:
- **RACE** = report quality vs a reference report, 4 weighted dims (Comprehensiveness,
  Insight/Depth, Instruction-Following, Readability), 0-100 where **50 = ties reference**.
- **FACT** = citation trustworthiness: extract every (fact, url), fetch the url, judge
  whether it supports the claim → Citation Accuracy % + Effective Citations.
- Model-agnostic judge (`--judge gemini|ollama|anthropic`). CLI: `research-engine bench`.
- Verified: 22 bench tests + full unit suite green, mypy strict + ruff clean, live run.

## The first real number (1 en task, local mistral-small judge — directional, N=1)
`Research/benchmarks/2026-07-09_scorecard.MD`:

| | RACE | Depth | FACT C.Acc | E.Cit |
|---|---|---|---|---|
| Research Engine | 40.5 | 37.8 | **0.0%** | **0** |
| Claude-3.7-Sonnet w/Search | 40.7 | 37.7 | 93.7% | 32 |
| OpenAI Deep Research | 47.0 | 45.3 | 78.0% | 41 |

**Two structural failures the scoreboard exposed (not statistical noise):**
1. **FACT = 0** — the delivered brief has **zero citations**. The engine reads full
   text but never grounds claims to sources in the deliverable.
2. **Off-topic sources** — a "Japan elderly demographics 2020-2050 market size" task
   returned **particle-physics / gravitational-wave arXiv papers**. Discovery is
   arXiv/physics-biased and has no topical relevance gate.
3. RACE ~40 is inflated by a lenient local judge on off-topic prose; FACT + a stronger
   judge (Gemini) expose it. Use `--judge gemini` for trustworthy numbers.

## YOUR JOB — Track B (user chose BOTH options, build then re-measure)

### Option 2 — Discovery relevance (do first; biggest gap)
Off-topic sources are failure #1. Make reports actually on-topic.
- Add a **relevance gate** in screening: score each paper's semantic match to the query
  with the local LLM; drop off-topic sources. Reuse `src/research_engine/screening/ranker.py`
  + add a relevance criterion in `src/research_engine/screening/criteria.py`.
- Fix source selection by topic in `src/research_engine/discovery/query_planner.py` +
  `discovery/source_registry.py` — don't lead with arXiv for non-CS/physics topics
  (prefer OpenAlex/Crossref/web for demographics, finance, policy, etc.).
- Add a `screening_yielded_offtopic` honesty flag (mirror existing `screening_yielded_zero`
  in `orchestrator.py`) so an off-topic run is visible, not silent.
- **Target:** on-topic sources → RACE Comp/Depth up.

### Option 3 — In-pipeline citation grounding (FACT 0 → real)
Every delivered claim must carry a verified claim→source-URL span; unsupported claims
are dropped or flagged before DELIVER.
- `src/research_engine/synthesis/synthesizer.py` + `evaluation/reporter.py`: emit inline
  citations (`[n]` markers + a reference list with URLs) built from
  `ExtractedSource.citations` and each source paper's URL.
- Wire the existing `src/research_engine/adversarial/verifier.py` (already checks quote/URL
  presence + DOI resolution) so claims that fail verification don't ship.
- Reuse the bench `FactScorer` (`bench/fact.py`) logic as the in-loop grounding check.
- **Target:** FACT C.Acc 0 → competitive; E.Cit > 0.

### Verify every change with the scoreboard (this is the loop)
```
# fresh campaigns over N tasks, then RACE+FACT:
research-engine bench --tasks 5 --judge ollama
# re-score a cached engine.jsonl only (fast, after a scoring-side change):
research-engine bench --tasks 5 --judge ollama --reuse-engine
# trustworthy multi-task number (authenticate gemini first: run `gemini` once, or set GEMINI_API_KEY):
research-engine bench --tasks 20 --judge gemini
```
Diff `Research/benchmarks/<date>_scorecard.MD` before/after. Goal: RACE up, FACT > 0,
sources on-topic. Follow TDD (`superpowers:test-driven-development`), keep mypy/ruff green.

## Environment / gotchas
- **Branch:** `feat/deepresearch-bench` (PR to `main` opened this session). Work on a new
  branch off it, or continue on it — check `git log`/`gh pr status`.
- **Ollama is the local judge/engine** (up: gemma4:31b, mistral-small3.2, qwen3.6-27b).
  Judge default is `mistral-small3.2:latest`. Gemini CLI + MCP are **NOT authenticated**
  here — authenticate before `--judge gemini`.
- **Corporate TLS**: `curl` needs `--ssl-no-revoke`; Python is fine (truststore injected).
- A full 100-task bench run is slow (100 local campaigns). Smoke with `--tasks 1..5` first.
- Approved plan: `C:\Users\Isaac\.claude\plans\lexical-bubbling-starfish.md`.

## First moves
1. `git status` / `gh pr status`; read `HANDOFF.md` top section + `docs/architecture/benchmark.md`.
2. Reproduce the finding: `research-engine bench --tasks 1 --judge ollama` and read the scorecard.
3. Start Option 2 (discovery relevance) TDD-first; re-measure; then Option 3; re-measure.
4. End of session: update `HANDOFF.md`, commit, open/refresh the PR.
