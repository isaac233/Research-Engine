# HANDOFF — 2026-07-17

## 🧪 2026-07-17 (LATE-5) — v7 WEAPONS COMMITTED (`684ac3c`) after adversarial review; measured NEGATIVE/NOISE on task 53

Built + committed 5 env-gated (default-OFF) levers from the v7 online SOTA scan
(`docs/plan/finish_line_research_v7.md`): **W1** MiniCheck citation abstain gate
(`RESEARCH_ENGINE_ABSTAIN_GATE=flan|minicheck`, `synthesis/minicheck.py` +
`abstain_citations()`), **W2** coverage ledger (`RESEARCH_ENGINE_COVERAGE_LEDGER`,
`planning/coverage_ledger.py`), **W3** section-locked write (`RESEARCH_ENGINE_SECTION_LOCKED_WRITE`,
`Outline.partitioned()` + skip deepen), **W4** grounding brief (`RESEARCH_ENGINE_GROUNDING_BRIEF`,
`planning/grounding_brief.py`), **W5** PDF ingest (`RESEARCH_ENGINE_PDF_INGEST`). Adversarial
review (review-suite) caught a CRITICAL (abstain regex dropped SUPPORTED cites on glued
punctuation `2024.[e1]` — fixed with a char-scan splitter that keeps the cite on any parse-miss)
+ 4 HIGH/MED (guarded MiniCheck load, Ollama fast-timeout, 6000-char PDF cap, non-fatal ledger).
`minicheck` pip-installed (torch/transformers/accelerate/nltk-punkt); flan verified. `ckpts/` gitignored.

**MEASURED task 53, N=1 isolation matrix (winning env + CDP, kimi judge) — spans / RACE / FACT:**
| config | spans | RACE | FACT |
|---|---|---|---|
| baseline (CDP+plan-then-fill) | 54 | **32.68** | 32.5% (13/40) |
| W1 abstain only | 62 | 31.31 | 36.4% (12/33) |
| W5 PDF only (inert, 0 pdfs read) | 49 | 21.05 | 20.0% (8/40) |
| W3 section-lock only | 39 | 22.49 | 17.5% (7/40) |
| combined W1+W2+W4+W5 | 33 | 24.19 | 39.1% (9/23) |

**KEY FINDING = N=1 VARIANCE ~±11 RACE.** W5 was inert (no PDF surfaced = baseline-equivalent
config) yet scored 21.05 vs baseline 32.68 → single-task deltas are NOT trustworthy. Mechanistic
reads that survive: **W1 = neutral/safe** (keep opt-in; drops ~7 unsupported cites, RACE flat,
FACT precision +noise); **W2+W4 = net-negative** (grounding brief built an 80-cell grid → ledger
diluted retrieval to 33 spans → RACE −8); **W3 = likely-negative** (skips deepen, the comp/insight
driver → retune to section-SCOPED deepen, not skip); **W5 = inert** unless PDFs appear.

### ⏭️ NEXT SESSION — START HERE
1. **Fix the instrument before more runs.** N=1 live task 53 swings ±11 RACE. Either (a) N≥3-5 per
   config (hours), (b) make serp deterministic (cache serp rows so a config re-banks the same pages
   — the biggest variance source), or (c) use the bounded cache A/B (`bench/writer_eval`) for
   writer/FACT levers. Do NOT trust another single live-task delta.
2. **Retune, don't discard:** W2/W4 → gap-query ONLY after core objectives are banked + cap entities
   (~5) & gap-budget (~2/round) so the ledger ADDS depth. W3 → section-scoped deepen instead of
   skipping deepen. W1 → keep as-is (opt-in), maybe sweep τ on the cache A/B.
3. Everything committed default-OFF → `main`/default path unharmed. Winning env unchanged (HANDOFF
   below). All weapon env flags in `docs/plan/finish_line_research_v7.md` §1.

---

## 🚀 2026-07-17 (LATE) — PLAN-THEN-FILL BREAKTHROUGH: live RACE 14.66 → 29.42 mean N=3 (DOUBLED), IF 8.65 → 33.0 (×3.8)

**The biggest single RACE gain in the project, on the LIVE path, task 51 (N=1, kimi judge).**
Distilled the core SOTA gap (research v5, `docs/plan/finish_line_research_v5.md`): **SOTA
plans-then-fills at reference scale (63k-char reference); we gathered-then-organized at 1/5
scale (13k)** and drifted off-task. Built 3 coupled levers + 2 infra unlocks, all env-gated,
TDD, mypy+ruff, **582 unit tests green**, committed on `feat/deepresearch-bench` (unpushed).

**Monotonic across 3 runs of increasing retrieval depth (this is a real signal, not N=1 noise):**
| run | RACE | comp | insight | IF | read | FACT | pages/sec |
|---|---|---|---|---|---|---|---|
| STEP 1 plain react | 14.66 | 14.1 | 7.5 | 8.65 | 33.1 | 79% | 17 / 6 (health-essay drift) |
| StepD3 combined (wedge-limited) | 20.51 | 21.4 | 17.6 | 20.5 | 24.5 | 41% | 8 / 3 |
| **StepE combined + fast-fail** | **29.18** | 29.6 | 23.8 | **33.0** | 32.4 | **70%** | 12 / 4 |

Bar = Claude-3.7 RACE 40.67 / FACT 93.7%. **Gap to bar now ~11 RACE (was ~26).** Sections became
the ASKED dims (Population 2020-2050 / clothing / food / housing) instead of a healthcare essay.

**✅ N=3 CONFIRMED (StepF, tasks 51/52/53, same winning env):**
| task | RACE | FACT | note |
|---|---|---|---|
| 51 Japan elderly | 31.47 | 45% | |
| 52 Buffett/Munger | **37.36** | 70% | **near the bar** |
| 53 wealthiest govs | 19.44 | 4% | only 14 spans banked — THIN fetchable evidence |
| **MEAN** | **29.42** | 39.8% | confirms N=1 29.18 — not noise |
Task 52 nearly hit the bar; task 53 dragged the mean because its query had sparse *fetchable*
evidence (14 spans, most reads 403/thin). **This pinpoints the #1 remaining gap: retrieval
FETCHABILITY, not the writer/outline (now strong).**

**The levers (all env-gated, default OFF — default linear path unchanged):**
1. **Lever 3 — reference-scale writing** (`9320ebc`): `SectionWriter.max_sentences` +
   `RESEARCH_ENGINE_WRITER_MAX_SENTENCES` / `_WRITER_MAX_TOKENS`. Writer was hard-capped at
   ~8 sent / 1200 tok / section (→13k brief vs 63k reference).
2. **Lever 1 — task-seeded outline** (`9320ebc`): `ReactPlanner.seeded_outline` = one section
   per objective (`RESEARCH_ENGINE_REACT_SEEDED_OUTLINE`). Kills the evidence-drift that made
   the report follow the banked evidence's dominant topic instead of the question.
3. **Lever 2 — balanced retrieval** (`9320ebc`): `ReactPlanner.per_objective_searches` retries
   a refined search per objective (`RESEARCH_ENGINE_REACT_PER_OBJECTIVE_SEARCHES`) so every
   asked dimension gets evidence.
4. **perf — collect-skip** (`5dd6ed4`, `f3acccf`): `RESEARCH_ENGINE_REACT_SKIP_COLLECT` skips
   the whole linear DISCOVER→SCREEN→EXTRACT (unused by react + the screen ranker is what WEDGES
   Ollama). react starts in ~60s vs ~10min. NB the fix also had to let `_run_evaluate` proceed
   with empty linear sources for react (else it bailed "no extracted sources" → RACE 0.00).
5. **infra — fast-fail timeout** (`c17dcd0`): per-call `request_timeout` on `LLMProvider.complete`;
   react's summarize/refine use `RESEARCH_ENGINE_REACT_REASONING_TIMEOUT` (default 90s) so a
   wedged Ollama call fails fast (excerpt/objective fallback) instead of hanging 300s. THIS
   unblocked retrieval from 8 → 12 pages → RACE 20.51 → 29.18.

**THE WINNING ENV (reproduce / build on):**
```
RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json' \
RESEARCH_ENGINE_PLANNER=react RESEARCH_ENGINE_REACT_MAX_PAGES=48 \
RESEARCH_ENGINE_REACT_SEEDED_OUTLINE=1 RESEARCH_ENGINE_REACT_PER_OBJECTIVE_SEARCHES=3 \
RESEARCH_ENGINE_REACT_REASONING_TIMEOUT=90 \
RESEARCH_ENGINE_WRITER_MAX_SENTENCES=16 RESEARCH_ENGINE_WRITER_MAX_TOKENS=2400 \
RESEARCH_ENGINE_REACT_SKIP_COLLECT=1 RESEARCH_ENGINE_MAX_WORKERS=1 RESEARCH_ENGINE_PROGRESS=1 \
RESEARCH_ENGINE_REACT_DEBUG=1 RESEARCH_ENGINE_ITEM_TIMEOUT=120 \
research-engine bench --tasks 1 --language en --judge ollama --judge-model kimi-k2.7-code:cloud --quality 0.3
```

### ⏭️⏭️ NEXT SESSION — START HERE (push from 29.18 toward the 40.67 bar)
**Session ops:** `podman machine start` → `cd ../search-infra && (podman-compose up -d searxng || podman compose up -d searxng)` → warm SearXNG (`curl "localhost:8080/search?q=x&format=json"` results>0). Ollama up (24 models; `mistral-small3.2:latest` synth lane). **ALWAYS archive `bench/out/engine.jsonl`+`scores.jsonl` and purge serp rows before a re-run** (else bench re-scores the stale task). Attach `bench/watchdog.py` via Monitor (stall 300s ok now that fast-fail caps calls at 90s).

1. ~~CONFIRM N≥3~~ **✅ DONE (StepF): mean RACE 29.42 across 51/52/53, task 52 peak 37.36.** The doubling is confirmed, not N=1 noise. Next confirmation would be N≥5 with a wider task set once the fetchability lever (below) lands.
2. **RETRIEVAL FETCHABILITY = the #1 remaining lever (pinpointed by task 53).** Task 53 scored 19.44 / FACT 4% because only **14 spans** banked — its query returned sparse *fetchable* evidence (most reads 403/thin) while tasks 51/52 banked 120-194 spans and scored 31-37. So the writer/outline are strong; the binding constraint is now getting on-page evidence for every asked dimension. Levers, highest-ROI first: (a) **CDP/headless 403-recovery** in the react `read_fn` (browser subsystem) to recover the ~50% bot-blocked reads — directly fills the dropped dimensions and lifts the weak tasks; (b) raise `REACT_PER_OBJECTIVE_SEARCHES` to 4-5 so a thin objective tries more queries; (c) dedup the `objectives_fn` output (task 51 emits 8 objectives with ~4 dupes → only ~4 distinct sections — dedup → more distinct sections → more coverage); (d) a fetchability-aware serp rerank (prefer HTML that returns content over PDFs/paywalls). This is where the next ~11 RACE to the bar lives.
3. **Readability/length polish** — StepE read 32.4 (bar 41.5); brief 16k vs reference 63k. Push `WRITER_MAX_SENTENCES`/`_MAX_TOKENS` higher and re-measure (watch FACT doesn't drop).
4. **Ollama wedge discipline** ([[ollama-recovery-discipline]]): the scheduler still wedges under sustained sequential load. fast-fail(90s) makes runs robust, but if a whole run hangs: py-spy the PID FIRST (names the blocked frame — it's `ranker`/`summarize_page` → `ollama_client.complete` → httpx.post), GPU 0% + /api/tags-still-UP = wedge → graceful tray restart (`Stop-Process 'ollama app','ollama'` → relaunch `ollama app.exe`; NEVER `taskkill //F` or manual `ollama serve`). Do NOT kill a bench mid-Ollama-call (wedges the server).

**Unmeasured/deferred (both lower priority than the fetchability lever #2 above):** writer LENGTH lever in isolation (StepC killed by wedge); react-vs-linear at these settings.

**TL;DR for the next session:** the plan-then-fill levers are BUILT, committed, and CONFIRMED at N=3 (mean live RACE 29.42, up from 14.66). Nothing to rebuild. Just: bring infra up (Session ops above) → run the WINNING ENV → then attack **retrieval fetchability (step 2)** — that's the ~11 RACE still between us and the 40.67 bar. Everything is env-gated and default-off, so `main`/linear behavior is untouched.

---

## ✅ 2026-07-17 — FIRST complete end-to-end react campaign: RACE 16.3 / FACT 52.5% (N=1); 4 stall bugs fixed

**Milestone:** a full react campaign RAN to completion and scored — the thing that never finished
before. react banked **122 spans / 16 pages / 8 iters IN-CAMPAIGN** (`_react_plan: DONE spans=122
… read_chars=87217`), wrote a 6-section brief, judged by kimi:
| metric | value |
|---|---|
| RACE overall | **16.3** (comp 17.0, insight 10.2, IF 14.9, read 27.8) |
| FACT c.acc | **52.5%** (40 pairs, 21 supported) |

**Reads (honest):**
- **"react banks 0 in-campaign" = definitively NOT a code bug.** 122 spans banked in a real
  campaign. It was infra (SearXNG) + the stall stack below.
- **FACT 52.5% healthy** (historical 44-53% band; real, not the degenerate 0.0%).
- **Volume thesis NOT validated — arguably negative at this budget.** react used only 16 pages while
  linear collected 40 sources; the earlier broken runs' LINEAR-fallback brief scored RACE ~26 on
  this same task 51. So react-at-16-pages < linear-at-40 on RACE. To test the thesis, `REACT_MAX_PAGES`
  must go WELL above 40 (toward WebWeaver ~100) AND N≥4 (single task is deep in the noise).

**FOUR stall bugs fixed this session (each caught in minutes via watchdog→py-spy→netstat, all TDD):**
1. `256234e` **connection churn (the big recurring one)** — `ollama_client.complete` opened a FRESH
   httpx.Client per call; ranker/extractor loops churned connections until some hung in SYN_SENT
   (GPU idle, blocked in create_connection). Now: ONE reused keep-alive client.
2. `8025ba7` **citation Author-Year regex exponential backtracking** — `\s+…\s*` overlap around an
   optional group hung (CPU-bound, GIL-held → item-timeout can't preempt) on capitalized-word runs.
   Now bounded/unambiguous + 200k cap.
3. `642f5c4` **markdownify O(Ntags·n)** on unclosed inline `<svg>` icons. Now skips a noisy tag's
   DOTALL sub when its close is absent.
4. `83b879c` **extract batch froze on a hung LLM** — `parallel_map` now has a per-item wall-clock
   timeout (works for IO-bound hangs; GIL caveat documented).
- Plus: `849bfb7` **bench/watchdog.py** (stall detector via Monitor), `c30d270`+`0ffda4a` **[progress]
  logging** (RESEARCH_ENGINE_PROGRESS, per-stage + per-extract-item incl. timeouts), `61d0771` react
  first-dry-objective loop fix.

**Ollama-under-load limit (not a code bug):** 4 concurrent extract workers wedge Ollama's scheduler
(reads hang, GPU idle) while a fresh curl answers in <1s. Ran with `RESEARCH_ENGINE_MAX_WORKERS=1`
(serial) to sidestep. Consider `OLLAMA_NUM_PARALLEL` tuning or capping default extract workers to 2.

### ⏭️⏭️ NEXT SESSION — START HERE (runs COMPLETE now; do these in order)

**Session ops first (both likely already UP — verify):**
- SearXNG: `curl -s "http://localhost:8080/search?q=x&format=json"` returns results>0. If down:
  `podman machine start` → `cd ../search-infra && (podman-compose up -d searxng || podman compose up -d searxng)` → warm it.
- Ollama UP (`curl http://localhost:11434/api/tags`). Models: `mistral-small3.2:latest`, `gemma4:12b`, Tongyi Q4.
- **ALWAYS run under the watchdog** ([[monitor-long-processes]]): launch the bench in background, then attach
  `python bench/watchdog.py --watch data/state.db --watch <log> --done-file <log> --done-regex "RACE overall" --stall-secs 240` via the **Monitor** tool. Do NOT passively wait on the completion notification (a wedge never sends one). If STALL fires: **py-spy dump the PID FIRST** (names the exact blocked frame — don't guess), check GPU + netstat, then kill.
- **Run SERIAL** (`RESEARCH_ENGINE_MAX_WORKERS=1`) — 4 workers wedge Ollama's scheduler.
- **Archive `engine.jsonl` + `scores.jsonl` BEFORE any re-run** (they now hold task 51 → bench SKIPS it and re-scores the stale article — this faked a result this session):
  `mv bench/out/engine.jsonl bench/out/engine_$(date +%s).bak.jsonl; mv bench/out/scores.jsonl bench/out/scores_$(date +%s).bak.jsonl` and purge serp cache (`python -c "import sqlite3;c=sqlite3.connect('data/cache.db');c.execute(\"DELETE FROM source_cache WHERE source='serp'\");c.commit()"`).

**STEP 1 — Fast thesis falsification (~35 min, 1 task).** Does MORE pages beat tonight's 16 pages (RACE 16.3)?
```
RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json' \
RESEARCH_ENGINE_PLANNER=react RESEARCH_ENGINE_REACT_MAX_PAGES=48 RESEARCH_ENGINE_REACT_DEBUG=1 \
RESEARCH_ENGINE_PROGRESS=1 RESEARCH_ENGINE_ITEM_TIMEOUT=120 RESEARCH_ENGINE_MAX_WORKERS=1 \
research-engine bench --tasks 1 --language en --judge ollama --judge-model kimi-k2.7-code:cloud --quality 0.3
```
GATE: if RACE does NOT rise meaningfully above 16.3, the volume thesis is likely DEAD at this stack —
do not spend 3-4h on N=4. Pivot the lever to the writer/FACT side or a trained backbone (Tongyi).

**STEP 2 — only if STEP 1 promising: proper N≥4 react-vs-linear (~3-4h).** Same env, `--tasks 4`, run BOTH
`RESEARCH_ENGINE_PLANNER=react` and `=linear` (archive engine.jsonl between arms), same kimi judge, same scale.
Gate: react RACE **and** FACT ≥ linear as pages rise.

**Context for the number:** tonight react@16pg = RACE 16.3 / FACT 52.5% (N=1) vs the broken runs' LINEAR-fallback
~26 RACE on the same task — so react must scale pages WELL past linear's 40 sources to win. FACT is already healthy;
RACE (comprehensiveness/insight/depth) is the gap. If pages don't move RACE, retrieval breadth is NOT the lever.

---

## 🔧 2026-07-16 (LATER) — the "#1 blocking bug" was INFRA, not code (react banks fine); loop-abort fix shipped

**The prior "#1 BLOCKING BUG" (react banks ~174 standalone yet ~0 in-campaign) is DISPROVEN as a
code bug.** Instrumented `_react_plan`/`_react_brief` (env `RESEARCH_ENGINE_REACT_DEBUG=1`,
`[react-dbg]` to stderr) and ran a controlled isolation:
- **Arm A** — `_react_plan` on a FRESH orchestrator, SearXNG up: **67 spans / 4 pages** (max_pages=4).
- **Churn** — one `discovery.run` (mimics the campaign collection stage): 120 groups, no error.
- **Arm B** — `_react_plan` on the SAME orchestrator AFTER churn: **67 spans** — IDENTICAL.

→ Campaign-accumulated state does NOT break react. The 2-min / FACT-0.0% campaigns
(`ab_hybrid_live*.log`) were **SearXNG down/unreachable** at that time → `registry.search("serp")`
empty → react banks 0 → `_react_brief` returns "" → thin linear fallback with unsupported cites →
FACT 0.0%, fast finish. With SearXNG up, react banks in-campaign exactly as standalone. See
[[react-banking-not-a-bug]].

**GOTCHA that faked a 3rd FACT-0.0% this session:** `research-engine bench` SKIPS a task already in
`bench/out/engine.jsonl` (resume cache, `runner.py:83`) and just re-scores the stale article. Archive
`engine.jsonl`+`scores.jsonl` (and purge serp rows in `data/cache.db`) BEFORE any real re-run, else
you measure the old article. (Archived this session → `*_20260716_231204.bak.jsonl`.)

**SHIPPED (TDD, mypy+ruff+571 unit green):** `ReactPlanner.run` aborted the WHOLE loop on the first
dry objective (`if added==0: break`). With ~50% of live reads returning **403** (sciencedirect / imf /
cgdev block bots), a dry FIRST objective zeroed the whole run. Now: `break` only if pages already
banked, else `continue`. Test `test_dry_first_objective_does_not_abort_the_run`. + diagnostic
instrumentation in `orchestrator._react_plan/_react_brief` (env-gated, kept for the volume measurement).

### ⏭️ REAL NEXT STEP (the phantom bug is gone → do the actual goal)
1. **Measure the volume lever** (the true #1): with SearXNG UP + `engine.jsonl` archived, run the real
   react bench (`RESEARCH_ENGINE_PLANNER=react RESEARCH_ENGINE_REACT_MAX_PAGES=16 … bench --tasks N`)
   and compare RACE/FACT vs linear. **BLOCKED THIS SESSION by the collection stall (see #2):** a
   1-task react bench froze at ~7 min in the LINEAR collection stage (`data/state.db` stopped writing
   at 23:19, Ollama idle, log 0 bytes) — a pathological page hangs `extraction/markdownify`
   (catastrophic backtracking) or a fetch never returns. The react-banking question is already
   answered by the Arm A/B churn probe (67==67); this is a separate collection bug that must be
   fixed before a full react campaign will complete.
2. **THREE real ceilings found (fix #2a FIRST — it blocks the measurement):**
   (a) **Collection stall** — one bad page freezes the whole collect; the 2M-char markdownify cap
   from a prior session is NOT enough (still hung). Add a per-item WALL-CLOCK timeout in
   `util/parallel.py` (`as_completed(timeout=)`, let the hung daemon thread leak) so one page can't
   wedge the run. This is the prerequisite for ANY full campaign.
   (b) ~50% of reads 403 (bot-hostile hosts) — a CDP/headless fetch could recover some.
   (c) react campaigns DOUBLE-PAY retrieval (linear collection runs before react at evaluate) —
   short-circuit collection when `planner=react` to cut ~30 min/task AND sidestep (a) for react runs.
3. FACT ceiling (writer-side) still open — cache A/B (`bench/writer_eval`) is the fast loop.

---

## ⏭️⏭️ NEXT SESSION — START HERE (SUPERSEDED for the react-bug item above; volume/FACT levers still valid)

### Frame of reference (the overarching plan)
**Goal:** beat Opus on DeepResearch Bench — **RACE > 40.67 AND FACT c.acc > ~90%**, driven by
LOCAL models. Master plan: `docs/plan/finish_line_plan.md` (WebWeaver restructure — Evidence
Bank + section writer + ReAct planner, all BUILT). The bar is achievable on a local 30B-MoE
(proof: WebWeaver on Qwen3-30B-A3B = RACE 46.77). Two gaps vs the bar: **RACE (report
depth/breadth, driven by evidence VOLUME)** and **FACT (citation accuracy)**.

### THE #1 NEXT STEP (data-driven pivot from this session): the react VOLUME lever
This session proved the **ReAct planner banks ~174 verbatim spans from 16 pages LIVE**
(direct `_react_plan` probe, task 51) — vs the fixed cache's ~20 spans. **That ~8× evidence
is the biggest untapped RACE lever, and it's model-agnostic (mistral drives it, stable).**
BUT there is a BLOCKING BUG: **react banks ~174 standalone yet ~0 inside the full campaign**
(`research-engine bench` → FACT 0.0%, 2-min finish). Fix that first.

**Do this, in order:**
1. **DEBUG the full-campaign react-banking bug.** `orchestrator._react_plan` banks 174 spans
   when called directly (with `RESEARCH_ENGINE_PLANNER=react` + SERP env), but the same path
   via `_react_brief` (called at `orchestrator.py:824` inside `_build_report_and_brief`) banks
   ~0 during a `research-engine bench` campaign. Find why (likely: a prior campaign stage
   consumes/changes state, an exception is swallowed, or discovery/browser differs in the
   campaign context). Cheap repro: `research-engine bench --tasks 1 --judge ollama` with the
   env set, add logging to `_react_plan`/`_react_brief`, compare to the standalone probe.
2. **Measure the volume lever** (once banking works end-to-end): full RACE/FACT with react ON,
   on **mistral** (stable), and try raising `RESEARCH_ENGINE_REACT_MAX_PAGES` (16 → 24/32).
   Gate: does 174 live spans lift RACE-Comp/Depth/E.Cit toward the bar?
3. **Fix the writer-side FACT ceiling in tandem** (still ~44-50%): the cache A/B loop
   (`bench/writer_eval`) is the fast tool. #13 verify/regenerate was a MEASURED NEGATIVE this
   session ([[verify-regen-negative]]) — span-level entailment ≠ the FACT judge's claim-vs-
   full-PAGE check. If retrying FACT, check the claim against the FULL source page, not the span.

### Tongyi-DR hybrid — scoped but DEPRIORITIZED (spike weakened it)
`docs/plan/hybrid_tongyi_plan.md`: route Tongyi-DR-30B-A3B into the ReactPlanner's reasoning
seams. Phase 0.1 BUILT (env `RESEARCH_ENGINE_REACT_REASONING_MODEL` routes objectives/refine/
outline/summarise to a second model; unset = no-op). **Phase 0.2 spike RAN and weakened the
thesis:** at fixed page-budget, Tongyi Q4 (146 spans, 7-sec outline) ≈ mistral (174 spans, 6-sec)
— **volume is budget-bound, not model-bound.** Tongyi's only edge = quality-at-equal-volume
(unproven) + a modest writer-role FACT bump (44.3→49.8, [[trained-deepresearch-models]]).
Revisit ONLY after the volume lever is proven, and only if a write+FACT/RACE-score of the two
banks shows Tongyi's bank yields a materially better report. Tongyi tags pulled:
`hf.co/mradermacher/Tongyi-DeepResearch-30B-A3B-GGUF:Q4_K_M` (18GB) / `:Q3_K_M` (14GB, degrades).

### Session ops (READ [[ollama-recovery-discipline]] + [[diagnose-before-escalate]] FIRST)
- SearXNG: `podman machine start` → `cd ../search-infra && (podman-compose up -d searxng || podman compose up -d searxng)` → warm it (first query is slow) → `export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'`.
- **OLLAMA DISCIPLINE (hard rule, learned the hard way):** NEVER `taskkill //F` Ollama or run
  manual `ollama serve` on Windows (the tray app owns :11434 → conflict → reinstall). If wedged,
  restart the tray app gracefully. **Don't thrash the 18GB Tongyi:** run each big model in its
  OWN process, load once, `keep_alive=0` unload before the next big load. Never alternate an
  18GB offloaded model with another inside one process/campaign (that wedges the server).
- **Verify the instrument before an expensive run:** confirm react actually banks (>0 spans) via
  a direct `_react_plan` probe before trusting a full-bench number. Degenerate metrics
  (FACT 0.0% both arms) = broken harness, not a real result.
- Judge = `kimi-k2.7-code:cloud` (works via Ollama Cloud; not in `/api/tags` but responds —
  [[kimi-judge-tag]]). Local: `mistral-small3.2:latest`, `gemma4:12b`.
- Fast measure loops: cache A/B `python -m bench.writer_eval score --variant … --judge ollama
  --judge-model kimi-k2.7-code:cloud` (writer/FACT); direct `_react_plan` probe (retrieval).

### Current state (what is TRUE right now)
- **Default writer = `section_synth`** (`SectionWriter(synthesis=True)`) — UNCHANGED this session.
  Best cache A/B: RACE ~28-29 / FACT ~44-50% / E.Cit ~14-18 (kimi N=4; ±2 RACE / ±10pt FACT run-to-run).
- **#13 verify/regenerate** (`synthesis/verify_regen.py` + variants `section_synth_verify/_regen`)
  = MEASURED NEGATIVE, kept but unused ([[verify-regen-negative]]).
- **Hybrid Phase 0.1 wiring** = built, `RESEARCH_ENGINE_REACT_REASONING_MODEL` env (default no-op).
- **`_strip_reasoning`** added to `ollama_client.py` — strips leaked `<think>` (reasoning GGUFs
  ignore think=false); no-op for non-reasoning models.
- **`--writer-model`** override added to `bench/writer_eval`.
- Branch `feat/deepresearch-bench`. Suite + mypy(106) + ruff green. **This session's work COMMITTED
  + PUSHED** (see git log). Docs: `finish_line_research_v4.md`, `hybrid_tongyi_plan.md`.

---

## 2026-07-16 — research run v4 → #13 verify/regenerate BUILT + MEASURED NEGATIVE; strategic model scan

Standing-order research run done. Read the FACT scorer + 3 papers in full (VeriCite
2510.11394, FullCite 2606.07130, FineRef 2602.18437) → `docs/plan/finish_line_research_v4.md`.

**KEY REFRAME:** FACT is judge-**entailment** of claim vs the **full re-fetched page
(6000 chars)** — NOT a substring/verbatim check (`bench/fact.py` + `FACT_SUPPORT_PROMPT`).
Built #13 = VeriCite-style verify-and-regenerate (`synthesis/verify_regen.py`, TDD 8
tests, mypy+ruff clean): per cited sentence, local-model entailment vs its bank span;
verify=strip unsupported `[eN]`, regenerate=rewrite toward span then drop. Variants
`section_synth_verify` / `section_synth_regen`.

**MEASURED — same-run cache A/B (kimi, N=4) — #13 FAILS the gate:**
| variant | RACE | FACT | E.Cit |
|---|---|---|---|
| **section_synth (champion)** | **29.27** | **43.9%** | **15.00** |
| section_synth_verify (drop) | 29.13 | 42.0% | 6.25 |
| section_synth_regen (rewrite) | 26.67 | 42.3% | 11.75 |
| section_faithful_deepen | 24.17 | 37.4% | 11.00 |
→ v4 hypothesis instructively WRONG: local entailment vs the LONE SPAN ≠ the FACT
judge's claim-vs-FULL-PAGE check (span is a subset → too strict). Drops/rewrites the
wrong cites; regen degrades the synth prose that won RACE. **section_synth stays
champion + default; no promotion.** Code kept (harmless, documents lesson).
[[verify-regen-negative]]. NB this run's synth baseline (29.27/43.9) vs historical
(28.31/49.3) = the known ±2 RACE / ±10pt FACT run-to-run swing.

**Model viability scan (user asked):** deepseek-r1:14b, WebThinker 8/14B, MiroThinker
14B all hardware-viable but agentic REASONING models that conflict with the engine's
`think=false` + passive-writer design → as writers they regress FACT. The gap vs the
WebWeaver/WebThinker proof is **TRAINING, not architecture**. Best obtainable trained
model = **Tongyi-DeepResearch-30B-A3B** (3.3B-active MoE, GGUF + Ollama
`huihui_ai/tongyi-deepresearch-abliterated` ready, fits 16GB+64GB offload). Pays off
only if wired to DRIVE the ReAct loop (`think=true` lane, our search/browser as tools)
— Phase 3-4 with a trained backbone. Verify its DeepResearch-Bench RACE first.
[[trained-deepresearch-models]].

### ⏭️ NEXT SESSION options
1. **Page-aware verify** (not the lone span): if retrying FACT, check the claim against
   the FULL source page text, mirroring the grader — the span-only check just failed.
2. **Tongyi-DR ReAct integration spike** (the strategic bet): wire it into the react
   planner lane as the loop driver; measure retrieval depth + RACE. Bigger swing than
   writer tweaks; FACT is likely retrieval/structural-bound now.
3. Retrieval volume via the (fast) react live path — still open.

**Branch:** `feat/deepresearch-bench`, unpushed. New files `synthesis/verify_regen.py`
+ test + 2 writer_eval variants + `docs/plan/finish_line_research_v4.md`. Suite green.

---

## 2026-07-15 (NIGHT) — Online research → diagnosis + #10-12 built + speed fix + FAST cache A/B (no more hanging smokes)

User asked: research online WHY we're not getting results + what methods; build #10-12;
and STOP wasting time on unfinished smoke tests. All three done. Research doc:
`docs/plan/finish_line_research_v3.md`. Commits on `feat/deepresearch-bench` (unpushed),
all TDD, mypy(108) + ruff clean.

**THE MEASUREMENT UNLOCK (fixes the "smoke never finishes" waste):** writer/citation
changes are measured with `bench/writer_eval.py score` over the CACHED
`fixed_evidence.jsonl` (4 tasks, 20 src each) — a BOUNDED cache run (no network fetch,
no hang), finishes in ~35 min with the kimi judge. Only *retrieval* changes need the
live pipeline, which now has a hard wall-clock deadline + serp-only search so it
finishes too. **Use the cache A/B for all writer work; never the slow live path.**

**RESEARCH DIAGNOSIS (online, evidence-backed — full detail in the v3 doc):**
- **FACT (~53%→bar 93%) — we cite the wrong WAY.** G-Cite vs P-Cite (arXiv:2509.21557):
  post-hoc citation (draft → attach/verify separately) beats generation-time on
  coverage+correctness. Catalogue #10 "attribute-first" is the *inferior* paradigm.
- **Cheap fix: CiteFix (arXiv:2504.15629)** — post-hoc re-point each sentence's cite
  to its best-supporting span, no training, +8-15% on open models.
- **RACE depth shallow — untrained local model failure mode.** Step-DeepResearch
  (arXiv:2512.20491) names it exactly ("short, loosely connected sentences, superficial
  bullets") and fixes it with **synthesis-driven drafting** (analytical paragraphs, ban
  list-as-body) + a coverage-preserving depth gate. Their real moat is RL/SFT (no budget).

**BUILT (#10-12, research-informed):**
1. **#10 P-Cite citation correction** `synthesis/cite_fix.py` — lexical re-point of each
   sentence's `[eN]` to its best-supporting BANK span (not a re-fetch — that failed
   before), drop unsupportable. + `section_deepen_pcite` writer variant.
2. **#11 synthesis-driven drafting** `section_writer.py` `synthesis=True` — cohesive
   analytical paragraphs with inline per-claim cites (NOT the grouped-end-cite paragraph
   variant that halved FACT). + `section_synth` / `section_synth_pcite` variants.
3. **#12 prefer HTML over PDF/DOI** — already covered (react `read_fn` skips PDF/DOI,
   `_citable_url` prefers HTML). No new work.

**MEASURED — #10 cite_fix, clean same-run cache A/B (kimi, N=4):**
| Variant | RACE | FACT | E.Cit | Read |
|---|---|---|---|---|
| section_deepen (baseline) | 25.36 | 40.9% | 12.75 | 29.2 |
| section_deepen_pcite (#10) | 25.86 | **41.0%** | 11.50 | 30.5 |
→ **#10 is FLAT on FACT — NEGATIVE result.** Diagnosis (important): our writer ALREADY
emits `[eN]` for the span it restates, so citations are already span-aligned — there's
little *misattribution* for CiteFix to correct (its setting is a loosely-citing general
LLM; ours is attribute-grounded). **Our FACT ceiling is PARAPHRASE DRIFT** (the writer
reWORDS the span → the cited page's support is judged weak), not wrong-span citations.
So the FACT lever is verbatim-tightness (`section_faithful` direction) or a
verify-and-DROP pass, NOT citation re-pointing. cite_fix kept (harmless, helps if a
future writer drifts) but is not the lever. NB FACT 40.9% this run vs historical 53% =
the known ±10pt judge/run variance — weight RACE, treat FACT directionally.

**MEASURED — #11 synthesis drafting, clean same-run cache A/B (kimi, N=4) — WIN:**
| Variant | RACE | FACT | E.Cit |
|---|---|---|---|
| section_deepen (baseline) | 27.13 | 45.0% | 14.00 |
| **section_synth (#11)** | **28.31** | **49.3%** | **16.75** |
→ **synthesis-driven drafting lifts ALL THREE: RACE +1.18 (28.31 = project best), FACT
+4.3pt, E.Cit +2.75.** Cohesive analytical paragraphs + inline per-claim cites beat the
choppy one-span-per-sentence default, exactly as Step-DeepResearch predicted. **PROMOTED
to the engine default writer** (`SectionWriter(..., synthesis=True)` in both the
attribute_first and react paths). Note this run's baseline (27.13/45.0) differs from the
#10 run's (25.36/40.9) — run-to-run variance is why same-run A/Bs are mandatory.
section_synth_pcite (synth + #10) = 28.00/44.7%/12.0 — **#10 HURTS synth** (FACT
49.3→44.7, E.Cit 16.75→12.0): cite_fix's lexical threshold drops genuinely-supported
paraphrased cites. Definitive: **#11 ON, #10 OFF** — exactly the promoted config
(synthesis=True, no cite_fix). synth also owns Readability (33.3, project best).

### ⏭️ NEXT SESSION — the real FACT lever + push RACE
1. **FACT is paraphrase drift, not misattribution (measured above).** Try: (a)
   `section_faithful` (quote-tight) + deepen — near-verbatim per span keeps the cited
   page verifiable; (b) a verify-and-DROP pass that removes a cite whose delivered
   sentence no longer contains enough of the span's verbatim text (compare to the BANK
   span, no re-fetch); (c) generate sentence-conditioned-on-one-span. Measure on cache.
2. **RACE:** `section_synth` won (28.31) and is the new writer floor + engine default.
   Combine with the FACT lever above (verbatim-tight synth?) and push evidence volume
   via the (now fast) react planner live path.
3. **Retrieval:** the serp-only react search + deadline now finish — run the live
   react-vs-linear bench (`RESEARCH_ENGINE_PLANNER=react`, budgets env-tunable).

**Branch:** `feat/deepresearch-bench`, unpushed. writer_eval variants: baseline
`section_deepen`; new `section_deepen_pcite`, `section_synth`, `section_synth_pcite`.
Judge `kimi-k2.7-code:cloud` ([[kimi-judge-tag]]). Cache A/B is the fast measurement loop.

---

## 2026-07-15 (EVE) — SOTA mechanisms #7-9 BUILT (ReAct planner subsystem) + markdownify stall fixed

Implemented the three deferred ceiling mechanisms from the catalogue
(`~/.claude/plans/peaceful-popping-pancake.md`) as ONE subsystem — a ReAct
research planner. All TDD, mypy(107) + ruff clean, full unit suite green, committed
on `feat/deepresearch-bench` (NOT pushed). 7 commits this session:

1. `87e9067` **markdownify HTML-size cap** (`extraction/markdownify.py`, `_MAX_HTML_CHARS=2M`)
   — the HANDOFF-prereq: a multi-MB page ran the DOTALL passes into catastrophic
   backtracking and froze collect. Now bounded. (ponytail: size cap, not a
   backtracking fix; adversarial unclosed-tag input still O(n²) within the cap —
   upgrade = per-item wall-clock timeout in `util/parallel.py`.)
2. `c5f021b` **#9 Memory Bank split** — `memory/summary_bank.py::SummaryBank`
   (per-page summaries = planner context) alongside verbatim `EvidenceBank`
   (writer). `digest()` for planner prompt, dedup-by-url, `covered_objectives()`.
3. `a3f7785` **#7 Summary-feedback** — `planning/summary_feedback.py`:
   `summarize_page` (page→short summary, grammar-constrained, excerpt fallback) +
   `refine_query` (objective + summary digest → sharper gap query).
4. `e99eeca` **#8 ReAct planner** — `planning/react_planner.py::ReactPlanner`:
   objective-driven iterative loop, gap queries from summary feedback, banks
   verbatim spans + summaries, **rebuilds the outline each productive round**
   (co-evolution), evidence-based termination (objectives covered / page budget /
   stall). Pure DI over injected search/read/summarise/refine/outline fns → fully
   unit-tested with fakes (9 tests). `d545412` refactor made the co-evolution
   genuine (was building outline once at end).
5. `f9b8f9a` **Wiring** — behind `RESEARCH_ENGINE_PLANNER=react` (default off), in
   `orchestrator._build_report_and_brief` (Option B: planner's bank+outline feed the
   tuned SectionWriter+deepen directly, zero `extracted_sources` schema coupling).
   `DEFAULT_VOLUME` 20→40 (constraint_triangle) — the HANDOFF's linear-path unlock.
   + `tests/unit/test_orchestrator_react.py` (wiring glue).
6. `e3fc67e` **ReAct tuning** — env-tunable budget (`RESEARCH_ENGINE_REACT_MAX_PAGES` def 16,
   `_PER_OBJECTIVE` def 3), `prefer_fetchable` reorder + skip PDF/DOI in the react
   `read_fn` (don't spend the read budget on 403s/paywalls — the same lever `_run_screen` uses).

**LIVE-VALIDATED end-to-end:** react loop ran a full task 51 live (Ollama gemma4:12b +
SearXNG) — objectives → gap-refined serp searches → fetched real public pages (akiya
article, JapanCaseStudies, nippon) → summarised each → banked verbatim spans →
outline → section writer → deepen → scored brief. **No stall, no crash.** The
markdownify fix held. Confirms the wiring is correct against real models/web.

**SPEED REALITY — TWO cost drivers measured (both real, ranked):**
1. **BIGGEST, and the clear fix: `search_fn` runs the FULL discovery pipeline
   per objective.** Each of ~8 objectives calls `discovery.run` = academic APIs +
   serp + snowball + resolve + **LLM relevance-ranking of every candidate**
   (`ranker.rank`, ~10 gemma4 calls/objective). Measured: **606 gemma4 calls in
   ~60 min for ONE task** at `max_pages=10`, still collecting. The linear pipeline
   does this discovery+rank ONCE; react does it ~8×. **FIX (next session, the
   thing that makes react practical): give the react loop a LIGHTWEIGHT serp-only
   search — hit the serp adapter directly, order by `prefer_fetchable` heuristic,
   DROP the per-candidate LLM ranker** (the read→summarise step + query-ranked
   verbatim banking already filter relevance; serp is pre-ranked). This is a
   retrieval-QUALITY change, so it needs a live A/B (does dropping LLM ranking hurt
   RACE/FACT?) — that's why it was NOT shipped blind this session. The current
   search_fn is correct, just heavy; behind the default-off flag it harms nothing.
2. Sequential Ollama summarisation + the deepen write pass over a bigger bank
   (untuned `max_pages=40` = **>75 min**, killed). GPU-parallel summariser is the
   real upgrade (out of scope). **Both cap practical N until #1 lands.**

**HONEST STATE of the live measurement:** the react mechanism is end-to-end
VALIDATED (collection ran, banked real fetchable pages, no stall/crash) but a
SCORED number was NOT obtained — two 1-task smokes (40-page and 10-page) each ran
>60 min without finishing, dominated by cost driver #1. Did NOT fabricate a number.
The scored react-vs-linear comparison is gated on the serp-only search fix above.

**Judge + infra confirmed UP this session:** Ollama local (gemma4:12b,
mistral-small3.2), SearXNG :8080, `kimi-k2.7-code:cloud` judge reachable (returns
clean output; NB it does NOT list in `/api/tags` but works).

### ⏭️ NEXT SESSION — measure react vs linear (the grind), then push volume
The subsystem is IN, correct, and live-proven. What remains is the multi-hour
apples-to-apples measurement (react is default-off; nothing changed for the default
path except DEFAULT_VOLUME 20→40).

1. **Session ops:** `podman machine start` → `cd ../search-infra && podman-compose up -d searxng whoogle`
   → `export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'`.
   Archive `bench/out/engine.jsonl` + `scores.jsonl` first; purge serp rows
   (`sqlite3 data/cache.db "DELETE FROM source_cache WHERE source='serp'"`).
2. **Full-bench comparison (NOT writer_eval — react produces its brief at
   evaluate-time, so writer_eval's single-pass cache can't see it).** Run the full
   bench both ways, N≥4 en, same kimi judge:
   ```
   # control (linear, current default)
   RESEARCH_ENGINE_SERP_ENDPOINT=... python -m research_engine.main bench --tasks 4 --language en --judge ollama --judge-model kimi-k2.7-code:cloud
   # treatment (react) — archive engine.jsonl between runs
   RESEARCH_ENGINE_PLANNER=react RESEARCH_ENGINE_REACT_MAX_PAGES=16 RESEARCH_ENGINE_SERP_ENDPOINT=... python -m research_engine.main bench --tasks 4 ... 
   ```
   GATE: react RACE **and** FACT rise vs linear (and vs the writer_eval V2 24.7/53.0/17.25
   frame, treating full-bench vs cache numbers as different scales).
   **PREREQUISITE — do this FIRST or react is impractically slow (>60 min/task):**
   replace the react `search_fn`'s full `discovery.run` with a lightweight serp-only
   search (see "SPEED REALITY" #1 above) + a small unit test, then a 1-task live
   smoke to confirm it finishes in minutes AND doesn't tank quality vs the heavy path.
3. **If react wins:** push `RESEARCH_ENGINE_REACT_MAX_PAGES` up (toward WebWeaver's
   ~100) overnight; the summary-feedback + co-evolving outline should keep lifting
   coverage. **If not:** the lever is elsewhere (writer/judge), not retrieval breadth.

**Branch:** `feat/deepresearch-bench`, 7 unpushed commits. Default writer
`section_deepen`, default planner `linear`. Judge `kimi-k2.7-code:cloud`
([[kimi-judge-tag]]). SearXNG left UP.

---

## 2026-07-15 (PM) — Methodology catalogue → 5 changes shipped; live test INCONCLUSIVE (volume stayed cap-bound)

Full methodology audit (their SOTA systems vs ours) → catalogue of 12 differences →
priority list → **5 changes built, all TDD, 247 unit tests green, mypy(101) + ruff
clean, committed** on `feat/deepresearch-bench` (NOT pushed). Catalogue + priority +
plan: `~/.claude/plans/peaceful-popping-pancake.md`.

**The 5 (commits):**
1. `464c46a` **Fetchable-URL filter** (`screening/url_filter.py`) — deterministic
   re-rank floating public HTML above PDF/DOI/paywall within the relevance-passed
   set before the source cap. `_run_screen`.
2. `464c46a` **Bounded-parallel extraction** (`util/parallel.py`) — ThreadPoolExecutor
   (ordered, per-item errors→None) over the pure fetch+LLM extract work; URL
   validation/events/SQLite stay on the main thread. `_run_extract`. Env
   `RESEARCH_ENGINE_MAX_WORKERS` (default 4).
3. `e2456f6` **Paragraph-granularity writer variant** (`section_writer.py`
   `paragraph_cite`) — cite the span SET per paragraph (arXiv:2604.01432).
4. `edd8167` **Grammar-constrained JSON decoding** — optional `format` JSON-schema
   through `LLMProvider.complete`/Ollama (`format` field); wired on decompose /
   outline / deepen. gemini+anthropic accept+ignore.
5. `c53f09e` **Objective-driven decomposition** (`query_decomposer.py`) — enumerate
   the report's information objectives BEFORE retrieval, one query per objective
   (arXiv:2604.24978); `plan_objectives()`; tolerates legacy `{queries}` shape.

**MEASURED — #3 paragraph writer (clean same-run kimi A/B, cached rich 4-task evidence):**
| Writer | RACE | FACT | E.Cit | Read |
|---|---|---|---|---|
| section_deepen (default) | 25.55 | **50.6%** | **16.25** | 30.7 |
| section_deepen_paragraph | **27.20** | 32.5% | 8.50 | 32.6 |
→ Paragraph grouping lifts RACE +1.65 (best-ever) but **halves FACT/E.Cit** — our
paragraph prompt licenses cross-span paraphrase and grouped end-cites cut verifiable
pairs. **NEGATIVE result; NOT promoted; section_deepen stays default.** The 2604.01432
finding did NOT transfer to our stack. Confirms the writer is not the FACT lever.

**MEASURED — collection changes (#1/#2/#4/#5), live collect tasks 51-52, N=2, same kimi run:**
| Pipeline (both 20 src/task) | RACE | FACT | E.Cit | Read |
|---|---|---|---|---|
| V2 baseline (old) | 21.22 | 49.1% | 15.50 | 25.1 |
| NEW (#1/#2/#4/#5) | 18.80 | 54.4% | 16.50 | 28.8 |
→ FACT +5.3, E.Cit +1.0, Read +3.8, **RACE −2.4 — ALL within known noise (RACE ±~2,
FACT ±10pt) at N=2. NO CLEAN SIGNAL.**

**WHY inconclusive (the real finding — 3 causes):**
1. **`#1` fetchability filter is INERT at pool ≈ cap.** It reorders `included` before
   `[:max_sources]`, but with ~20 relevance-passed candidates and `DEFAULT_VOLUME=20`,
   nothing gets cut → reorder is a no-op. Fetchable fraction barely moved (V2 11/15 →
   NEW 10/17 of 20). **Evidence volume did not grow** → the amplifier the whole set of
   changes targets never engaged. NB: the prior HANDOFF's "t51 2→11" were *fetchable*
   counts; BOTH caches cap at 20 total.
2. **Collect STALLED on task 53 (~99 min, no log/IO)** — a huge/pathological HTML page
   hung `extraction/markdownify` (regex `.*?` + `re.DOTALL`, catastrophic backtracking,
   pure-CPU so no fetch/Ollama timeout fires). Killed + salvaged 2 tasks. **This caps
   the volume lever: 1 bad page freezes the whole collect.**
3. **N=2 is below the noise floor** (HANDOFF has warned N=3 is noise for months).

**THE TWO UNLOCKS (next session, ranked — these make the shipped changes actually bite):**
1. **Make volume actually grow: raise the candidate pool ABOVE the cap.** More
   sub-queries (objective decomposer already emits more) + raise `DEFAULT_VOLUME`
   (e.g. 20→40) so screening passes >cap and **#1 selects the fetchable top-N from a
   bigger pool** (its whole point). Only then does the proven volume lever move.
2. **Fix the markdownify/parse stall** (prerequisite for #1 above — can't scale volume
   if 1 page hangs the run). Cheapest: cap HTML input size before `markdownify`
   (skip/truncate pages > ~2 MB) and/or wrap extract in a per-item wall-clock timeout
   in `parallel_map` (use `as_completed(timeout=…)`, let hung daemon threads leak).
Then re-run the live test at N≥4 with pool>cap and confirm RACE/FACT move together.

**Artifacts:** new-pipeline 2-task evidence `bench/out/fixed_evidence_v3_new2task.jsonl`;
canonical 4-task baseline restored to `bench/out/fixed_evidence.jsonl` (= v2_highvol,
24.7/53.0). A/B log `bench/out/ab_paragraph.log`; collect log
`bench/out/collect_v3_newpipeline.log` (shows the stall). Web stack (SearXNG) left UP.

### ⏭️ NEXT SESSION — START HERE (exact steps to make the shipped changes bite)
The 5 changes are IN and correct; they don't move metrics until evidence volume
actually grows. Do these in order:

1. **Fix the stall FIRST (prereq — else high-volume collects hang).**
   `extraction/markdownify.py` — cap input before the regex passes (top of the
   public `markdownify(...)` fn: `if len(html) > 2_000_000: html = html[:2_000_000]`).
   Optionally also make `util/parallel.py` use `concurrent.futures.as_completed`
   with a per-item `timeout=` so a wedged item can't block the batch (let the hung
   daemon thread leak; the batch process exits anyway). TDD: a 5 MB pathological
   HTML returns fast, doesn't hang. (Root cause: regex `.*?`+`re.DOTALL` catastrophic
   backtracking, pure-CPU, no fetch/Ollama timeout fires.)

2. **Grow the pool ABOVE the cap so `#1` fetchable-filter selects (not no-ops).**
   Raise `DEFAULT_VOLUME` at `planning/constraint_triangle.py:17` (20 → 40). The
   objective decomposer already emits ~8 sub-queries → many candidates; with cap 40,
   screening passes >prior-cap and `_run_screen`'s `prefer_fetchable` picks the
   fetchable top-N from a bigger pool → banked fetchable evidence actually rises.
   (At cap=20 with ~20 candidates the filter reorders then keeps all → inert.)

3. **Session ops** (SearXNG is UP now; per fresh session):
   `podman machine start` → `cd ../search-infra && podman-compose up -d searxng whoogle`
   → `export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'`.

4. **Fresh live collect** — archive `bench/out/fixed_evidence.jsonl` first (it's the
   canonical 24.7/53.0 baseline, DON'T overwrite); purge serp rows
   (`sqlite3 data/cache.db "DELETE FROM source_cache WHERE source='serp'"`), then:
   ```
   RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json' \
   RESEARCH_ENGINE_SERP_BLOCKLIST='deepresearch-bench,zhipuai-infra.cn,huggingface.co/datasets' \
   RESEARCH_ENGINE_MAX_WORKERS=4 python -m bench.writer_eval collect --tasks 4
   ```
   Watch for the stall (log goes silent) — step 1 must be done first.

5. **Score + compare** (judge = `kimi-k2.7-code:cloud`, the ONLY trustworthy judge):
   `python -m bench.writer_eval score --variant section_deepen --judge ollama --judge-model kimi-k2.7-code:cloud`.
   GATE: RACE **and** FACT rise together vs the 24.7/53.0/17.25 baseline. Measure
   N≥4 (N=2/3 is below the noise floor — RACE ±~2, FACT ±10pt).

**Branch state:** `feat/deepresearch-bench`, pushed (this session's 7 feature/doc
commits are on origin). Default writer = `section_deepen`. `section_deepen_paragraph`
kept in `bench/writer_eval.py` as a measured negative. Judge = kimi via Ollama Cloud
([[kimi-judge-tag]]). Do NOT re-chase the writer for FACT — #3 proved it's not the
lever; the lever is evidence volume (steps 1-2 unlock it).

---

## 2026-07-15 — DRASTIC LEVER CONFIRMED: evidence volume lifts ALL metrics (RACE 24.7, project best)

The mined finding (WebWeaver banks ~106 pages/task, we banked ~3.5 = 30× gap) is now BUILT + PROVEN. Shipped the first evidence-volume increment: **LLM query decomposition** (`discovery/query_decomposer.py`) — one task → ~8 facet sub-queries (each a web search) via QueryPlanner `subquery_fn`; source cap 10→20 (`DEFAULT_VOLUME`). Wired in `main._make_orchestrator` (online_a lane, web+LLM present).

**Collection effect (per-task, controlled): fetchable sources ~3× up** — t51 2→11, t52 5→15, t53 4→11, t54 6→8.

**Controlled A/B — section_deepen, SAME tasks 51-54, evidence volume the ONLY variable (kimi judge):**
| | RACE | FACT | E.Cit |
|---|---|---|---|
| V1 sparse (~4 src/task) | 22.5 | 43.4% | 12.5 |
| **V2 rich (~11 src/task)** | **24.7** | **53.0%** | **17.25** |

**~3× evidence → RACE +2.2, FACT +9.6pt, E.Cit +4.75 — ALL THREE rise.** Definitive: evidence volume is the drastic lever; the writer was starved. **RACE 24.7 = project best** (trajectory: legacy 21.5 → page-bound 12.7 → outline+section 20 → deepen 21.1 → deepen+3×evidence **24.7**; bar 40.7). Going from 3× toward the full 30× should keep lifting.

**PRACTICAL NOTE:** high-volume collect is SLOW — ~30 min/task (20-candidate sequential ollama screening + 20 extractions). The benchmark doesn't score speed so it's pure win for the goal, but the pipeline is minutes/query. **Screening/extraction parallelism is needed** before pushing evidence much higher.

**NEXT (keep closing the 30× gap):** (1) two-stage URL filter — LLM selects relevant+FETCHABLE URLs from the bigger candidate pool, drop 403/paywall up front, fetch+bank many more; (2) summary-feedback loop — each page → summary → informs next sub-query (WebWeaver); (3) parallelize screening/extraction (the speed ceiling); (4) grammar-constrained decoding for ReAct reliability. Evidence: `docs/plan/finish_line_research_v2.md`. Caches: `bench/out/fixed_evidence_v2_highvol.jsonl` (rich), `_v1_lowvol.jsonl` (sparse).

---

## 2026-07-14 (NIGHT+) — Methodology mining → section_deepen is the best writer (RACE 21.1)

Deep-read WebWeaver (2509.13312) + AgentCPM-Report (2602.06540, 8B LOCAL beats Gemini-2.5-Pro). Turned two methods into variants, measured on the SAME fixed N=9 evidence:

| Writer | RACE | FACT | E.Cit | Read |
|---|---|---|---|---|
| flat | 14.8 | 36.9% | 9.8 | 21.8 |
| section (prev default) | 19.8 | 53.4% | 12.2 | 28.9 |
| section_faithful (verbatim) | 16.2 | **58.5%** | 11.1 | 25.4 |
| section_coherent (narrative carry) | 18.9 | 55.3% | 12.2 | 29.1 |
| **section_deepen (WARP) — NEW DEFAULT** | **21.1** | 51.6% | **14.6** | 28.6 |

**`section_deepen` wins RACE (21.1, best) + E.Cit (14.6, best)** — the WARP draft→diagnose-shallow-sections→expand-from-bank loop (`synthesis/deepen.py`) lifted RACE +1.3 and E.Cit +2.3 vs `section` on identical evidence; FACT within noise. **Promoted to the orchestrator default** (outline → SectionWriter(carry_context) → deepen_report). Coherence carry-over alone was ~neutral (reports too short to benefit). Verbatim (`section_faithful`) still owns FACT (58.5%) at a RACE cost.

**Signal note:** on fixed evidence, RACE is stable (~±0.2 across batches); **FACT has ~±10pt variance** from the live cited-URL re-fetch in the FACT scorer — weight RACE for writer A/Bs, treat FACT directionally.

**Writer levers still open:** (a) `deepen` + `faithful` combo (deepen with quote-tight) for RACE 21 + FACT ~58; (b) more deepen iterations (WARP plateaus ~9 — we do 1 pass, ≤2 sections); (c) paragraph-granularity citation. **Next big lever = live Planner breadth** (summary-feedback adaptive search + retrieval-driven deepening → more fetchable sources → the RACE ceiling). Research: `docs/plan/finish_line_research_v2.md`.

---

## 2026-07-14 (NIGHT) — CLEAN SIGNAL: fixed-evidence writer harness overturns the N=3 conclusion

**Built `bench/writer_eval.py`** — runs discovery+extraction ONCE per task, caches sources (with `page_text`), rebuilds the bank deterministically (no re-fetch), and scores any writer variant over IDENTICAL evidence. Removes the discovery/fetch variance that made N=3 useless. `collect` (once) → `score --all`. Cached N=10 (9 usable, 32 fetchable sources).

**CLEAN 3-way writer comparison (N=9 fixed evidence, kimi judge):**
| Variant | RACE | Read | FACT | E.Cit |
|---|---|---|---|---|
| flat (verbatim, no outline) | 14.60 | 20.9 | 46.2% | 11.44 |
| **section (outline+coherent) — DEFAULT** | **19.98** | **28.8** | 52.7% | 11.78 |
| section_faithful (outline+verbatim) | 16.38 | 24.4 | **56.6%** | 11.33 |

**Corrects the record:** the earlier N=3 "section writer regressed FACT to 16.7%" was NOISE (empty-bank contamination — 2/3 tasks had no evidence, fell back). On identical good evidence: (1) the outline structure beats the flat writer on BOTH RACE and FACT; (2) `section` (coherent) is the best writer overall (best RACE + Readability, strong FACT) and is the wired default — KEEP IT; (3) `section_faithful` (verbatim) trades ~3.6 RACE for +3.9 FACT — verbatim helps attribution (matches arXiv:2604.01432 directionally) but coherent prose wins here. On decent evidence the engine now does **RACE ~20 / FACT ~53% / E.Cit ~12** — the real trustworthy baseline (vs bar 40.7 / 93.7 / 32).

**The harness is the key infra win** — writer variants now A/B in ~40 min (no campaigns). Use it for all writer tuning; use a larger-N headline sweep for the breadth work.

**NEXT (ceiling lever, research-backed):** the Planner-breadth half — **objective-driven outline built from the query BEFORE retrieval, then iterative gap-driven search with evidence-based termination** (arXiv:2604.24978, ablated on DeepResearch Bench: outline+reflection+termination each add coverage). More fetchable sources → higher Comp/Depth/E.Cit → RACE toward 40. Research detail: `docs/plan/finish_line_research_v2.md`.

---

## 2026-07-14 (LATE) — Planner/Writer rebuild: Writer half BUILT + proven; binding constraint = FETCHABILITY

**User greenlit the WebWeaver-style Planner/Writer rebuild.** Built the Writer half this session (all TDD, mypy+ruff clean, committed on `feat/deepresearch-bench`):
- `planning/outline.py` — `Outline`/`OutlineSection` (sections: title/intent/evidence_ids; prune hallucinated IDs).
- `planning/outline_builder.py` — LLM organizes the Evidence Bank's verified spans into 4-7 grounded sections; tolerant JSON parse; flat-fallback.
- `synthesis/section_writer.py` — walks the outline, retrieves ONLY each section's evidence, writes attribute-first prose per section (verbatim-tight to protect FACT), headers + References.
- Orchestrator `attribute_first` path: bank → outline → section-writer → (fallback) flat writer → (fallback) legacy synth. Empty bank no longer drops to the bare Reporter.

**LIVE-PROVEN the writer works:** from ONE WHO page, 20-span bank → 4-section outline (Global Aging Trends / Demographics / Regional / Health) → 4110-char coherent cited brief. Night-and-day vs the old ~535-char one-sentence-per-span list.

**RESULT — when banks have evidence, the rebuild is the BEST RACE of the session.** rebuild-v1 (before synth-fallback) scored 10.3 only because 2/3 tasks had empty/zero banks (fetchability variance) → fallback. The FINAL run (synth-fallback + verbatim-tightened section writer) got fetchable banks on ALL 3 tasks → **RACE 23.29 (Comp 20.6 / Depth 17.3 / Read 32.6), above legacy 21.48 and 2× the flat writer's 12.66. Readability 32.6 vs 18.9.** The outline+section structure is a VALIDATED RACE lever. **Tradeoff: FACT dropped to 16.7%** (flat writer was 35%) — coherent section prose paraphrases spans so citations verify less than near-verbatim restating, despite the verbatim-tightening. FACT is also high-variance run-to-run (which sources fetched).

**DEFINITIVE binding constraint = SOURCE FETCHABILITY + COUNT.** Academic sources (researchgate, crossref/openalex DOIs) dominate screening inclusion but 403/paywall on fetch → empty page-bound banks. Public web pages (serp lane: tokyoesque, WHO, etc.) fetch clean. WebWeaver gets ~200 effective citations by *iteratively searching for more*; we get 0.5-7 from ONE discovery pass over mostly-unfetchable sources.

**TWO NEXT BUILDS (ranked):**
1. **Recover FACT without losing the RACE win.** Section prose paraphrases → citations verify at 16.7% vs the flat writer's 35%. Options: (a) re-add a verify pass over the section-writer output — for each cited `[eN]`, check the delivered sentence still contains enough of the span's verbatim text; drop/re-tighten if not (spans are page-bound so this needs no re-fetch — compare against the bank span, not the live page); (b) push the writer even closer to verbatim per sentence; (c) generate sentence-by-sentence conditioned on one span (true attribute-first) inside each section. Target: keep RACE ≥ 23 AND lift FACT back toward 35%+.
2. **Breadth via the Planner half** (the ceiling on Comp/Depth/E.Cit): iterative ReAct loop + **two-stage URL filter that SELECTS FETCHABLE public sources** (drop researchgate/DOI-only up front, prefer HTML) and keeps searching until the outline is well-supported (many sources, not 1-4). WebWeaver ~200 cites vs our 3.7. This fills the bank so the Writer covers more.

Then grammar-constrained decoding (ReAct reliability) + policy-refinement review (commit 00e4798). Re-measure N≥10 (N=3 FACT/source variance is large — this session saw 0-4 sources/task run-to-run).

**Rebuild scoreboard (kimi N=3):**
| Run | RACE | Read | FACT | E.Cit | note |
|---|---|---|---|---|---|
| legacy synth | 21.48 | 30.71 | 20.4% | 1.33 | baseline |
| page-bound flat writer (20 spans) | 12.66 | 18.91 | 35.0% | 7.33 | FACT↑ RACE↓ |
| outline+section writer v1 | 10.31 | 21.94 | 25.0% | 0.50 | 2/3 banks empty (fetchability) |
| **outline+section (all 3 fed)** | **23.29** | **32.56** | 16.7% | 3.67 | **best RACE this session, > legacy; FACT is the tradeoff** |

---

## 2026-07-14 (EVENING) — FIRST scored page-bound run; FACT ↑ but RACE ↓ (autonomous session)

**Measured (N=3 en, kimi judge, page-bound attribute-first path, all fixes below active):**
| Run | RACE | Comp | Depth | Read | FACT c_acc | E.Cit |
|---|---|---|---|---|---|---|
| Legacy baseline | 21.48 | 19.89 | 17.97 | 30.71 | 20.4% | 1.33 |
| **Page-bound v1 (6 spans/src)** | **9.56** | 9.11 | 6.76 | 16.73 | **34.26%** | 4.33 |
| Claude bar (DoD) | 40.67 | 38.99 | 37.66 | 41.46 | 93.68% | 32.48 |

**Read:** page-bound citation mechanism WORKS — FACT 20→34% (~1.7×), E.Cit 1.3→4.3. But RACE CRASHED 21→9.6: the minimal spike writer emits ~1 sentence per span over only 1-3 fetchable sources → tiny briefs (~1k chars vs ~20k reference). **Below the 40% FACT gate AND a RACE regression.** The tradeoff is now measured: accuracy up, breadth down. Net-win needs the comprehensive Writer (plan Phase 4) + more fetchable sources.

**Fetchability is the breadth ceiling:** per task only 1-3 of ~3-6 included sources yield page text — researchgate 403s bots, igi-global 429s (rate-limited this session), publisher DOIs paywalled. Public web pages (e.g. tokyoesque.com) fetch clean and give full page_text. So discovery/source-mix toward fetchable PUBLIC pages is a real lever.

**v2 (20 spans/src, 3000-tok writer) — MEASURED:** RACE **12.66** (↑ from 9.56), FACT **35.0%** (≈flat), E.Cit **7.33** (↑ from 4.33). Briefs bigger (task52 9251 chars/4 src) but task51 stuck 3012/1 src — **source-fetchability variance dominates breadth**, and choppy 1-span-per-sentence writing keeps Readability at 18.9 (vs 41 bar). **Diminishing returns: 3× spans → only +3 RACE.** Span-density is not the lever that reaches 40.

**CONCLUSION (data-backed):** page-bound evidence is a validated FACT lever (20→35%, ~1.75×) but the minimal spike writer cannot carry RACE — briefs stay ~1/5 reference length, choppy. Cheap tuning is exhausted. **The path to the bar is the structural rebuild the finish-line plan already specifies:**
- **Phase 3.3 Planner (breadth):** more fetchable sources per task. The #1 constraint is fetchability — researchgate 403s, publisher DOIs paywall; PUBLIC web pages (serp lane) fetch clean. Bias discovery/inclusion to fetchable public pages; raise source count well above the current 1-4.
- **Phase 4 Writer agent (RACE):** section-by-section, reference-length, COHERENT prose (not 1-sentence-per-span) — this is what lifts Comp/Depth/Readability together. Needs Phase 2 grammar-constrained decoding for reliable section planning.
- Do NOT keep micro-tuning span caps at N=3 (noise + diminishing returns). Next real work is the Writer build; measure at N≥10.

**Session commits (all TDD, mypy+ruff clean, on `feat/deepresearch-bench`, NOT pushed):**
`9fb15ce` from_pages · `70043e6` UnblockProbe fetch-bug fix (was gutting extraction/enrichment engine-wide) · `adc32b0` fetch-once (store page_text) · `3f02931` e2e chain test · `00e4798` extraction reads public HTML landing pages (POLICY REFINEMENT — refuse non-OA PDF/DOI, allow public HTML; review) · density-tune commit.

---

## 2026-07-14 (PM) — Phase 3.2 shipped + 2 latent bugs fixed; live FACT number blocked UPSTREAM

**Code state (all committed, TDD + mypy + ruff clean):**
- `9fb15ce` — `EvidenceBank.from_pages()`: page-bound evidence (fetch page → verbatim spans bound to that URL).
- `70043e6` — **CATASTROPHIC BUG FIXED:** the default browser (`UnblockProbe`) raised on EVERY normal fetch. `_fetch_page_text`, snippet enrichment, AND full-text extraction all silently failed to fetch across the whole engine. Added `_resolve_byte_fetcher(browser)` (uses `UnblockProbe.http`, the inner RawHTTPBrowser). This bug alone was gutting the engine — fixing it should lift results regardless of Phase 3.2.
- `adc32b0` — fetch-once: extraction stores fetched page markdown in `meta["page_text"]`; `from_pages` reuses it (no re-fetch), runs over ALL screened sources (not the claim-filtered subset), verify-by-construction (dropped the redundant verify re-fetch).
- `3f02931` — end-to-end test: page-bound bank → writer → multi-source attributed brief. **Phase 3.2 delivery chain is unit-CERTIFIED.**

**Live measurement NOT achieved — blocked upstream, not in Phase 3.2.** Every N=3 attribute-first run collapsed to a ~535-char, 1-source brief. Root causes found (all upstream of the writer):
1. **Resolver hands extraction `doi.org` URLs (`is_oa=False`)** → the DOI fetch yields a paywalled page → extraction falls to `abstract_only` → stores NO `page_text` → `from_pages` must re-fetch the HTML landing page every time. Fetch-once can't help until extraction fetches the readable HTML landing (`paper.url`), not the DOI.
2. **Screening variance:** included-source count swung 2↔6 across runs (fresh serp results + LLM scorer noise, caches purged each run). N=3 is far below the noise floor.
3. **Rate-limiting (partly self-inflicted):** heavy diagnostic fetching this session got igi-global (and others) returning HTTP 429; WHO/IMF still fetch fine. A clean run needs un-throttled sources.

**THE isolated proof it works:** with reliable page text, `from_pages` builds a 26-span bank across 6 sources and the writer delivers a multi-source cited brief (unit test `3f02931`; live repro earlier this session). The mechanism is sound; the linear pipeline's resolver/extraction/screening fight it.

**NEXT LEVER (highest value, next session):** make **EXTRACTION fetch + store the HTML landing page** (`paper.url`) text when the resolved content_url is a DOI/non-OA — then `from_pages` reuses it (true fetch-once, no 429), AND extraction gets real full text (better claims → RACE too). This is the bridge to the plan's Phase 3.3 Planner (two-stage URL→page→span→bank done ONCE). Do NOT chase a live N=3 number until (a) that fix lands and (b) a fresh/un-rate-limited session; measure at N≥10 with the kimi judge.

**Ops fixed this session:** Ollama was reinstalled (`OllamaSetup.exe /VERYSILENT`) — the runner `lib/ollama/llama-server.exe` had been wiped by an interrupted self-update during a GamerZone 3-day suspend; gemma4:12b runs clean now. **GamerZone:** falsely detects `LockApp` (lock screen) as a fullscreen game and suspends ollama; fix = add `lockapp`,`logonui` to `fullscreenIgnore` in `beta/GamerZone/GamerZone.config.json` (ACL-protected — needs elevated write) then `Start-ScheduledTask GamerZone`. The watcher is currently STOPPED (I stopped it; auto-restarts at logon). Podman+SearXNG were up.

---

## ⛔ BLOCKER (2026-07-14 earlier) — Ollama local runner missing; RESOLVED via reinstall (see above)

**Phase 3.2 (page-bound evidence extraction) is BUILT + committed + unit-green (`9fb15ce`)** — the pinned next build. But it **cannot be measured**: the local Ollama install is broken.

**Diagnosis (airtight):** every local-model call returns `500` from `/api/chat` with `error starting llama-server: llama-server binary not found`. The runner tree `…/Programs/Ollama/lib/ollama/` (holding `llama-server.exe` + GPU backend DLLs, modified Jul 13) is **gone** — `lib/` now contains only `Ollama.lnk`. The `.exe` launchers (Jul 8) survive and `ollama serve` runs, so `/api/tags` lists models and **`:cloud` models still work** (they route to Ollama Cloud, no local binary) — which is why the kimi *judge* ran but every *engine* stage (screening scorer, extraction, synth, writer) 500s. Result: screening scorer raises on all candidates → all rejected → `screening_yielded_zero` → empty briefs → bench scored 0/3. Two N=3 runs void (archived `bench/out/void_20260714_noenv/`, `bench/out/prev_20260714_phase32/`).

**FIX (user action — reinstall restores the runner):** download latest `OllamaSetup.exe` from ollama.com/download and run it (in-place repair, keeps pulled models in `~/.ollama`). Then verify: `curl -s http://localhost:11434/api/chat -d '{"model":"gemma4:12b","messages":[{"role":"user","content":"say 4"}],"stream":false}'` returns content, not a 500. THEN re-run the Phase 3.2 measurement below.

**Re-run cmd (env INLINE — `export … && nohup &` did NOT propagate the SERP endpoint; that void'd the first run):**
```
podman machine start && (cd ../search-infra && podman-compose up -d searxng whoogle)
# purge serp cache rows + archive bench/out/*.jsonl first
PYTHONUNBUFFERED=1 RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json' RESEARCH_ENGINE_WRITER=attribute_first \
  python -m research_engine.main bench --tasks 3 --language en --judge ollama --judge-model kimi-k2.7-code:cloud
```
**Gate (plan Task 1.0/3.2):** FACT c_acc ≥ 40% (baseline 20%). Then wire Planner (Phase 3.3).

---

## ⏭️ NEXT SESSION — START HERE

**Goal (user's finish line):** local-model (gemma4/qwen) engine BEATS Opus on DeepResearch Bench. **Proven achievable** — WebWeaver on Qwen3-30B-A3B (local MoE) scores RACE 46.77 > Claude 40.67; architecture hits 93% citation accuracy. Full evidence + architecture: `docs/plan/finish_line_research.md`. Granular 6-phase build plan: `docs/plan/finish_line_plan.md`.

**Trustworthy baseline (kimi judge):** RACE 21.48 / FACT 20.4% vs Claude 40.67 / 93.68%. Gap is ARCHITECTURAL (quality slider gave no lift). Measure everything with `kimi-k2.7-code:cloud` (the ONLY trustworthy judge; local mistral is a mirage). Bench cmd: `research-engine bench --tasks N --judge ollama --judge-model kimi-k2.7-code:cloud`.

**Where we stopped:** Phase 1.0 spike CONCLUSIVE (below). Attribute-first citation mechanism validated (67% where spans aligned); root cause of low FACT pinned = **evidence spans not bound to their cited URL**. Committed, tested primitives (default-off flag `RESEARCH_ENGINE_WRITER=attribute_first`): `memory/evidence_bank.py`, `synthesis/attribute_writer.py`, `synthesis/verify_citations.py` — reuse these.

**THE NEXT BUILD (do this first):** **page-bound evidence extraction** (plan Phase 3.2). Fetch a specific page → extract verbatim spans FROM that fetch → bank each span WITH that exact URL. Then verify-before-cite passes by construction. After that: Planner ReAct loop (search/write_outline/terminate) + Writer (retrieve/write, section-by-section) + grammar-constrained decoding (plan Phase 2). Then 10-task kimi sweep for DoD (RACE > 40.67 AND FACT > ~90%).

**Session ops:** `podman machine start` → `cd beta/search-infra && podman-compose up -d searxng whoogle` (sibling of repo; use `podman-compose` pip pkg) → `export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'`. Archive `bench/out/*.jsonl` + purge `data/cache.db` serp rows before each measure. Ollama Cloud signed in (kimi/deepseek `:cloud` models work via localhost:11434).

---

## Phase 1.0 spike — CONCLUSIVE: mechanism sound, needs page-bound evidence (2026-07-13, v4 commit 2134bef)

**v4 (quote-tight writer + verify-before-cite) settled it.** verify-before-cite re-fetches each span's URL the FACT way and strips any citation whose verbatim span is not on the page. Result: it stripped nearly EVERY citation (t51 0/0, t52 1/4, t53 0/0; FACT 8%). This is the working primitive doing its job and exposing the ROOT CAUSE: **the engine's evidence spans are not bound to the URL they are cited to.** Spans are mined from `paper.abstract`, but that is NOT the live content of `paper.url` (what gets cited and what FACT re-fetches) — they are disconnected, so spans don't re-verify on their cited page.

**Conclusion (4 spike runs):** attribute-first is sound (t51 v1 verbatim claim-spans = 67%); verify-before-cite is a correct honesty primitive to KEEP; the mandatory fix is **page-bound evidence extraction** — fetch a specific page, extract verbatim spans FROM that fetch, bank each span WITH that exact URL (the plan's Phase 3.2 two-stage URL→page→span→bank). No reuse-existing-spans shortcut works because the current extraction doesn't bind span↔URL. This is NOT a spike tweak; it is the real Planner build. Spike primitives (EvidenceBank, AttributeFirstWriter, verify_citations) are committed behind `RESEARCH_ENGINE_WRITER=attribute_first` (default off; legacy synth path unchanged) and are the reusable foundation for that build. **Next: build page-bound evidence extraction per `docs/plan/finish_line_plan.md` Phase 3.2, then the Planner/Writer.**

## Phase 1.0 falsification spike — earlier attempts + diagnosis (2026-07-13, commits 594258d/6e79eeb/397bcfd)

Built the attribute-first writer + Evidence Bank spike (`RESEARCH_ENGINE_WRITER=attribute_first`). Gate = FACT c_acc ≥ 40% on 3-task kimi. **Did not pass; 3 honest attempts, declining:**
- v1 claims-only (verbatim `claims[].evidence` spans): overall 22%, but **t51 = 2/3 = 67%** (up from 50% baseline) — verbatim spans verify. t52/t53 = empty bank (finance pages yield no structured claims) → 0 cites.
- v2 + summary-field spans (results_summary/conclusions): FACT 17.6% — paraphrased summaries DON'T re-verify (t51 crashed 67%→8%).
- v3 + verbatim page-spans from `paper.abstract`, query-ranked: FACT 8.1%.

**Diagnosis (from reading t51 v3's delivered brief):** three concrete leaks — (1) **writer distortion**: local synth model expands spans into fluent claims not literally on the page (not true attribute-first); (2) **bad citable URLs**: `_citable_url`'s "not .pdf/not doi.org ⇒ verifiable" heuristic trusted a paywalled `igi-global.com/viewtitle.aspx` stub → 6 citations to one unverifiable page; (3) coverage additions multiplied cites against unverifiable sources, dragging the ratio down.

**Verdict:** direction validated (verbatim claim-spans → 67% on the one HTML-rich task), naive implementation leaks. Real fix = a proper build, not a spike tweak: **(a) verify-before-cite** — re-fetch each span's URL the FACT way, keep the span only if its verbatim text is found on the page (auto-drops paywalled stubs, guarantees every cite verifies); **(b) quote-tight writer** — delivered sentence must track the verbatim span; **(c) real readability gate** (fetch+check, not URL-suffix); needs **grammar-constrained decoding** (plan Phase 2) so the local writer stops distorting. Spike code is committed behind the flag (default off — legacy synth path unchanged). Next: build the corrected Phase 1 per `docs/plan/finish_line_plan.md`.

## TRUSTWORTHY BASELINE established — kimi judge (2026-07-13 PM)

**Judge unblocked:** user's Ollama Cloud key → judge = **`kimi-k2.7-code:cloud`** (the real tag; no plain `kimi-k2.7:cloud` — see [[kimi-judge-tag]] / memory). Returns clean JSON (`think=false`). Replaces the degenerate local mistral (which reported a mirage RACE 52.82).

**First trustworthy number (3 en tasks, kimi judge, enricher + safe guard active):**
| | RACE Overall | Comp | Depth | Inst | Read | FACT C.Acc | E.Cit |
|---|---|---|---|---|---|---|---|
| **Research Engine** | **21.48** | 19.89 | 17.97 | 23.01 | 30.71 | **20.37%** | 1.33 |
| Claude-3.7 w/Search (bar) | 40.67 | 38.99 | 37.66 | 45.77 | 41.46 | 93.68% | 32.48 |

Per task: t51 RACE 15.0 / FACT 2-of-4 (50%); t52 25.8 / 0-of-6 (0%); t53 23.7 / 2-of-18 (11%). Differentiated, non-degenerate → trustworthy.

**HONEST STATE:** the engine is **~half** Claude-3.7's RACE and **~1/5** its citation accuracy. Beating Opus is a large, multi-lever gap, NOT one session. Weakest RACE dims = Depth (18) + Comprehensiveness (20); best = Readability (31). FACT is the biggest gap (20 vs 94). **This is the real starting line** — the mistral 52.82 was judge inflation, now exposed (the anti-cover-up working as designed). Roadmap levers: (1) FACT — cite HTML-verifiable pages + tighter claim↔source binding (raises c_acc + e_cit); (2) Depth/Comp — more sources + deeper synthesis (quality slider → bigger synth lane, higher volume); (3) re-measure every change with `--judge ollama --judge-model kimi-k2.7-code:cloud`.

## Lever results — what moved the benchmark and what didn't (2026-07-13 PM, kimi judge, N=3 en)

| Run | RACE | FACT c_acc | commit |
|---|---|---|---|
| baseline (default quality) | 21.48 | 20.4% | enricher+guard |
| `--quality 1.0` (best 7-lane models) | 19.78 | 19.2% | — |
| synth-specificity + conservative guard + 3500-tok briefs | 21.17 | 13.8% | `a388367` |
| **Claude-3.7 w/Search (bar)** | **40.67** | **93.68%** | — |

**Honest conclusion: no session-scale lever closed the gap.** Engine is pinned at RACE ~21 / FACT ~15-20% across every config. At N=3 the ±3-pt moves are noise. Two findings worth keeping:
- **The quality slider does NOT improve the benchmark** — bigger models per lane gave flat/worse RACE+FACT. The bottleneck is structural (discovery breadth, report comprehensiveness, per-sentence citation binding), not model size. Important negative result about the Prompt-2 investment.
- **Local-model synthesis is the ceiling**: it writes reports ~half as comprehensive as the reference and citations that mostly don't verify. Specific-claim prompting + longer budget did not fix it at N=3.

**Roadmap to actually beat the bar (multi-session, structural):** (1) **Discovery breadth+depth** — more relevant sources per task (the reference reports draw on many); current campaigns deliver ~5-9 sources. (2) **Per-sentence retrieval-grounded synthesis** — bind each sentence to the exact source span (RAG-style), not free-form synth then post-hoc guard; this is the only reliable path to Claude's 93.68% c_acc. (3) **Cite HTML-verifiable pages** — the FACT verifier can't read PDFs/DOIs; prefer/relabel citations to the readable landing page. (4) **Longer multi-pass reports** for RACE Comp/Depth. (5) **Always measure with `--judge ollama --judge-model kimi-k2.7-code:cloud`** at N>=10 to beat the noise floor. What NOT to repeat: the lexical/word-overlap grounding (proven harmful), the quality slider as a benchmark lever (no effect).

## "Beat Opus" grind — honest findings (2026-07-13 PM, commits `e2274a1`, `8962181`, `0d7aef9`)

**Goal reframed by user:** finish = accomplish the Prompt-1 vision — gemma4-class local models drive the whole campaign and deliver **better insights than Opus**, measured by the DeepResearch Bench scoreboard vs the Claude-3.7-Sonnet-w/Search bar (RACE 40.67 / FACT c_acc **93.68%** / e_cit 32).

**What shipped (all tested green, mypy+ruff clean):**
1. **Snippet enricher** (`e2274a1`) — thin web snippets (<300 char) replaced with capped page-text excerpts before SCREEN. Real web sources now reach screening.
2. **Citation grounding** (`8962181` + `0d7aef9`) — post-synthesis guard that strips `[n]` a source doesn't support. **The re-fetch-based variant was built, measured, and REMOVED**: on an isolated A/B (same article, same judge) it *helped* task 51 (12%→22%) but *hurt* task 52 (16%→7%, dropped 3 of 4 genuinely-supported HTML citations) — lexical overlap on re-fetched page boilerplate ≠ semantic support. Kept only the conservative same-source anti-hallucination guard (checks a claim against its OWN extract); it keeps unreadable/PDF/DOI citations (can't disprove → don't hide a real source) and a floor prevents stripping every citation.

**THE BLOCKER (why a certified win can't be produced autonomously):** the measurement instrument is untrustworthy. Local **mistral judge** returns **degenerate RACE** (identical 52.82 across three different runs) and **non-reproducible FACT** (same task 51 read 12% / 36% / 50% across passes). No frontier judge is available in-repo: `API_KEYS.MD` holds only financial-data keys (no ANTHROPIC/GEMINI/OPENAI), `gemini` CLI is unauthenticated, ollama is local-only. **Certifying "beats Opus" needs a trustworthy judge = a user-provided `GEMINI_API_KEY` (free, AI Studio) or `ANTHROPIC_API_KEY`, plus a 10-20 task sweep.**

**Structural verdict (honest):** the *vision* is demonstrably working — local models run discovery→full-text extraction→grounded synthesis and deliver citation-rich briefs from real web sources (task 51: Carnegie/WHO/PMC/UNDP/nippon; task 52: 7 HTML finance sources). The specific FACT **93.68%** number is NOT yet hit: the engine cites PDFs/DOIs the FACT verifier can't re-read (auto-fail) and local-model synthesis mis-attributes some claims. **Next real lever (not done): bias discovery + citation to HTML-verifiable pages and use an LLM (not lexical) claim↔source alignment — then measure with a real judge.** Infra note: SearXNG web lane confirmed live this session (`beta/search-infra`, sibling of the repo, Podman).

## Snippet enrichment — next lever DONE (2026-07-13, commit `e2274a1`, branch `feat/deepresearch-bench`)

**The HANDOFF's top-ranked remaining lever is shipped.** "Resolver full-text fetch for web URLs pre-screening (snippet→page text)" is now `src/research_engine/screening/enricher.py::enrich_snippets`. A red TDD test (`tests/unit/screening/test_enricher.py`, was untracked/unbuilt) drove it green (7/7).

- Fetches the page for thin **web** sources (`serp`/`web_crawl`/`web`) whose abstract is <300 chars (`SNIPPET_TEXT_CHARS`), replaces the snippet with a capped `markdownify` page excerpt (default 2000 chars), preserves the original snippet in `meta["snippet"]`, flags `meta["enriched_from_page"]`. Immutable (`dataclasses.replace`), `URLPolicy`-gated (blocks link-local/private before fetch), `max_fetches`-capped (default 8), non-fatal on fetch failure, academic sources untouched.
- Wired into `orchestrator._run_screen`: enriches before `ranker.rank` when a browser is present (`self.browser.fetch_bytes`). So the relevance rubric + extraction now see real page text, not a 150-char snippet.
- **Verified:** full unit suite green (`pytest -q --no-cov`), mypy clean, ruff clean.
- **NOT exercised live** — the enricher's path only fires on the web/serp lane, which needs the Podman+SearXNG stack up (per-session manual, see below). Unit-proven; a live bench run with the stack up is the confirmation.

## Finish-line status (2026-07-13) — user chose STOP HERE

Branch `feat/deepresearch-bench` is **47 commits ahead of `main`** (v0.1.0). It subsumes PR #17's 7-lane full-text work + benchmark scoreboard + Track B + web lane + this enricher. All green. Local ~3 commits ahead of origin (**unpushed**; no PR to main).

**The finite objectives (v0.1.0 DoD, the 7-lane prompt-2 spec) are met.** What remains is not finite code work — it forks into (a) **release**: push branch → PR → merge → tag v0.2.0 (irreversible; user-gated), and (b) **benchmark grind** ("beat Opus"): open-ended, needs the stack up + `gemini` auth for trustworthy numbers. User elected to defer both. Next session: pick a fork. Remaining ranked levers if grinding: authenticated `--judge gemini` run; `--tasks 20` sweep; task-52-class FACT variance (fetch result pages before support judging). LLM query planner still heuristic (low value).

## Snippet-rubric calibration — lever 1 DONE (2026-07-09 night, commit `8ce0309`)

**The task-51 blocker is fixed.** Web snippets (~150 chars) can never "directly address" a query, so the strict relevance rubric MUST-failed every good web source. New `LLMRubricCriterion.snippet_prompt`: when source text is snippet-thin (<300 chars, `SNIPPET_TEXT_CHARS` in ranker.py), the rubric judges **topic match** of title+snippet instead of answer completeness. Still 1-5, still MUST — off-topic floodgate stays closed (test-guarded). Also neutralized scorer labels (Title/Text, "research sources" system prompt — the old "academic papers"/"Abstract:" framing biased against web results).

**Measured (2 en tasks, ollama judge, fresh caches):** RACE 52.82 (~flat, within judge noise) | **FACT c.acc 50.0%** (was 33.3), e.cit total 8 (was 6).
- Task 51 (Japan demographics): **0 → 5/8 supported citations (62.5%)**, 6 real web sources included (Carnegie, WHO, UNDP, AARP, EU-Japan report) — exactly the ones previously rejected. RACE stuck at 40.5: known mistral-judge coarseness (identical grids), treat directional.
- Task 52 (Buffett/Munger/Duan): RACE 65.1, FACT 3/8 (was 6/9 — run variance; different serp results each run).

**Remaining levers, ranked:** (1) resolver full-text fetch for web URLs pre-screening (snippet→page text, makes rubric + extraction stronger); (2) authenticated `--judge gemini` run for trustworthy numbers; (3) `--tasks 20` sweep; (4) task-52-class FACT variance — consider fetching result pages before support judging.

**Session ops reminder:** `podman machine start` → `cd beta/search-infra && podman-compose up -d searxng whoogle` (pip `podman-compose`, NOT `podman compose`); export `RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'`; archive `bench/out/*.jsonl` before re-measuring (resume caches). Old runs parked in `bench/out/prev_20260709/`.

## Web lane LIVE + FACT>0 (2026-07-09 evening, branch `feat/deepresearch-bench`, commits `2d54dbe`, `2f8f5c9`, `2752d84`)

**Container stack + loop closed.** `beta/search-infra`: `searxng` + `whoogle` containers running (websurfx/yacy skipped — flaky image / empty index). SearXNG JSON verified at `http://localhost:8080/search?q={query}&format=json`. Bench invocation: `export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'` then `python -m research_engine.main bench --tasks 2 --judge ollama`.

**Container engine = PODMAN (switched from Docker Desktop 2026-07-09).** Podman 5.8.3 + Podman Desktop, own WSL2 VM (`podman-machine-default`), no license tier/login. Same compose file, verified byte-identical SearXNG/SERPAdapter behavior. **Per session:** `podman machine start` (or Podman Desktop auto-start), then `cd beta/search-infra && podman-compose up -d searxng whoogle`. **Use `podman-compose` (pip pkg), NOT `podman compose`** — the built-in subcommand silently borrows Docker's `docker-compose.exe` if present. Docker Desktop being uninstalled; engine is container-agnostic (only needs the localhost:8080 HTTP endpoint). Full setup in `beta/search-infra/README.md`.

**Three real bugs found only by running live (each TDD-fixed, suite+mypy+ruff green):**
1. **SSRF policy blocked the local endpoint** (`2d54dbe`): localhost + non-80/443 ports rejected before the allow-list could apply, and `ssrf_guard` DNS-pinned everything to public IPs. New `URLPolicy(trusted_origins=[...])` — exact (scheme,host,port) from operator's endpoint config; bypasses localhost/port/DNS-pinning gates only, never scheme/credential checks; SERPAdapter endpoint calls also skip robots.txt (SearXNG ships `Disallow: /*?*q=*` for external crawlers — meaningless for the operator's own instance). Result-URL fetches stay fully gated.
2. **Benchmark leakage** (`2f8f5c9`): web-searching the verbatim task prompt returned pages republishing the benchmark's own dataset/reference reports (huggingface datasets page, `research-hb.zhipuai-infra.cn/samples/...`) — and they beat real sources on the relevance rubric (verbatim match → 5/5). New `RESEARCH_ENGINE_SERP_BLOCKLIST` (comma-separated URL substrings) filtered in SERPAdapter; bench runner sets a default leakage blocklist. **Purge `data/cache.db` serp rows when changing the blocklist** — cached results bypass the adapter filter.
3. **Brotli corruption** (`2752d84`): fingerprint headers advertise `Accept-Encoding: br` but the decoder wasn't installed — httpx silently returned raw brotli bytes and ssrf_guard strips Content-Encoding, hiding it. Every br-served page (tikr, substack) was garbage for extraction AND for FACT support checks. Dep now `httpx[brotli]`.
   Also: scorecard reasons printed the CLAMPED rubric score (everything below minimum displayed as "3.0 vs minimum 3.0") — now prints the raw score.

**RESULT (2 en tasks, ollama judge, directional):** RACE overall **52.96** (was 40.5; 50 = ties reference) | FACT c.acc **33.3%**, eff.cit 6 (was 0 / 0).
- Task 52 (Buffett/Munger/Duan): 0 included → **6 real web sources** (tikr/gainify/yahoo/llmquant), RACE 65.4, FACT 6/9 supported (67%).
- Task 51 (Japan demographics): unchanged 40.5, 1 source. Web lane found excellent sources (Carnegie, WHO, UNDP, EU-Japan consumer report) but **screening rejects them: raw relevance <3 on the strict "directly addresses" rubric** while snippet-thin. THE next lever: relevance-rubric calibration for web snippets (score topical relevance of title+snippet; don't demand the full answer in a 150-char snippet). Careful: don't re-open the off-topic floodgate Track B closed.

**Next levers, ranked:** (1) rubric calibration above → task-51-class breadth; (2) resolver full-text fetch for web URLs pre-screening (snippet→page text makes rubric fair); (3) authenticated `--judge gemini` run for trustworthy numbers; (4) `--tasks 20` sweep.

## Track B — discovery relevance + citation grounding (2026-07-09, branch `feat/deepresearch-bench`, commits `327a39f` + `1531516`)

**What was built (all TDD, mypy strict + ruff green, full unit suite green):**

*Option 2 — discovery relevance:*
- **Relevance rubric was blind**: the default prompt had no `{query}` placeholder, so `format(query=...)` was a no-op — the LLM scored papers without ever seeing the research query. Fixed; rubric is now a MUST gate.
- **Rubric was unfailable**: `clamped = max(minimum_score, ...)` floored every low score up to passing. Pass/fail now uses the raw score.
- No-LLM environments pass rubrics unchecked (offline CI safe); scorer errors fail visibly.
- Query planner skips arXiv for non-STEM queries (keyword-term heuristic; screening's LLM gate is the backstop).
- `has_full_text` demoted MUST→SHOULD (it excluded every crossref/openalex record wholesale); new `has_abstract` SHOULD (w=2.0) and **`readable` MUST** (abstract OR full text — a relevant-sounding title-only stub cannot be extracted or cited).
- **OpenAlex abstracts were always empty**: adapter read `raw["abstract"]`, which the API never sends; now rebuilds text from `abstract_inverted_index` (live: 7/10 papers gained abstracts).
- New honesty flag `screening_yielded_offtopic` (≥50% of candidates fail relevance) beside `screening_yielded_zero`.

*Option 3 — citation grounding:*
- Synthesizer renders per-source URLs, instructs inline `[n]` citations, and code-appends a deterministic `## References` section (URL-less sources listed so `[n]` never dangles). Reporter fallback same.
- `drop_failed_claims`: Verifier-rejected claims are stripped before synthesis — unverified claims never ship.
- `unique_insight_filter` keeps abstract-only sources that have content but 0 structured claims (they were silently dropped, collapsing briefs to 1 source).

**Measured (1 en task, ollama judge, N=1 directional):** RACE 40.5 (unchanged), FACT extraction now finds (fact,url) pairs (0→2) but 0 supported — the single on-topic readable source is a paywalled IGI DOI the judge cannot verify. **Sources are now on-topic** (was: gravitational-wave papers for a Japan-demographics query; now: population-aging economics).

**UPDATE (2026-07-09, commit `f9aae42`): web lane now CODE-WIRED.** `SERPAdapter` parses SearXNG JSON (HTML fallback kept); `EngineConfig.serp_endpoint` reads `RESEARCH_ENGINE_SERP_ENDPOINT`; when set, `main.py` enables the `serp` source + planner emits a web query. A shared self-hosted stack lives at `beta/search-infra/` (SearXNG/Whoogle/Websurfx/YaCy compose + `search_router.py`). **Not yet exercised live** — Docker Desktop is not installed on this machine. To close the loop and prove FACT>0: install Docker, `cd beta/search-infra && docker compose up -d`, `set RESEARCH_ENGINE_SERP_ENDPOINT=http://localhost:8080/search?q={query}&format=json`, then re-run the bench. That is the remaining step of the finding below.

**THE structural finding (next session's target):** DeepResearch Bench tasks are general web-research questions. For task 51 (Japan elderly market) only 1/30 academic candidates was both relevant and readable; for task 52 (Buffett/Munger investment philosophies) 0/21 — the engine honestly delivered nothing (`screening_yielded_zero` + `_offtopic` both fired; the anti-cover-up works). Academic APIs are the wrong lane for these tasks. **The engine needs the web discovery lane live**: `SERPAdapter` exists but requires a configured endpoint (SearXNG instance or paid API) — none configured. Wiring a SearXNG endpoint (or serper.dev key) + enabling `serp`/`web_crawl` in the planner for non-academic topics is the single highest-value next move for both RACE breadth and FACT (web sources are fetchable, unlike paywalled DOIs).

**Bench gotchas learned:** `bench/out/engine.jsonl` is a resume cache — a re-run with the file present re-scores the OLD article (delete/move it to re-measure after engine changes). The local mistral judge at temp=0 can emit identical RACE grids for different mediocre articles — treat as coarse/directional only.

## DeepResearch Bench scoreboard — Track A (2026-07-09, branch `feat/deepresearch-bench`)

**Why:** the engine had never been scored against any external benchmark or against Opus — "hasn't beaten Opus" was a feeling, not a number. Built the apples-to-apples scoreboard first (measure before upgrading), per the approved plan `C:\Users\Isaac\.claude\plans\lexical-bubbling-starfish.md`.

- **Ported DeepResearch Bench** (arXiv:2506.11763, Apache-2.0) into a new top-level `bench/` package: **RACE** (report quality vs a vendored reference report, 4 weighted dims, 0-100 where 50 = ties reference) + **FACT** (extract cited (fact,url) pairs → fetch via the engine's own `raw_http`+`markdownify` → judge support → citation accuracy + effective citations).
- **Vendored** `bench/data/{query,criteria,reference}.jsonl` (100 tasks / criteria / reference reports) + `LICENSE.md` provenance.
- **Model-agnostic judge**: new `src/research_engine/llm/gemini_cli_client.py` (shells to `gemini -p`, stdin for bulk, auth-error surfaced) + `bench/judge.py build_judge(gemini|ollama|anthropic)`. Registered `gemini` in `model_registry`.
- **CLI**: `research-engine bench --tasks N --judge {gemini|ollama|anthropic} [--reuse-engine --quality]` → writes `Research/benchmarks/<date>_scorecard.MD` (engine row vs published Opus/Gemini/OpenAI bar in `bench/leaderboard.py`, flags weakest dimension = Track B target).
- **Verified:** 22 new bench unit tests + full unit suite green (EXIT=0); mypy strict clean (87 files); ruff clean. RACE math + scorecard render verified with a fake judge.
- **Judge availability in this env:** Gemini CLI + MCP are NOT authenticated (no key/oauth; MCP `spawn EINVAL`). Ollama IS up (gemma4:31b, mistral-small3.2, qwen3.6-27b) — used as the offline validation judge. For the closest-to-official number the user must authenticate `gemini` once (or set `GEMINI_API_KEY`) and run `--judge gemini`.
- **TLS note:** corporate cert revocation blocks `curl`; used `--ssl-no-revoke` to vendor data (engine itself already fixed via truststore).

### FIRST REAL SCORECARD (1 en task, local mistral-small judge — directional, N=1)
`Research/benchmarks/2026-07-09_scorecard.MD`:

| | RACE Overall | Comp | Depth | Inst | Read | FACT C.Acc | E.Cit |
|---|---|---|---|---|---|---|---|
| **Research Engine** | **40.52** | 42.86 | 37.78 | 41.50 | 40.15 | **0.00** | **0** |
| Claude-3.7-Sonnet w/Search | 40.67 | 38.99 | 37.66 | 45.77 | 41.46 | 93.68 | 32 |
| OpenAI Deep Research | 46.98 | 46.87 | 45.25 | 49.27 | 47.14 | 77.96 | 41 |

**What the scoreboard exposed on run one (the whole point of measuring):**
1. **FACT = 0.** The delivered brief had **zero citations** (0 URLs, 0 `[n]` refs). The engine reads full text but does not ground claims to sources in the deliverable — the vision's "citation-rich report" is measurably absent.
2. **Off-topic sources.** Task = "elderly demographic market size in Japan 2020-2050"; the engine returned **particle-physics / gravitational-wave arXiv papers** ($B^0_s$ decay, CMS/LHCb). Discovery has an arXiv/physics bias and failed relevance for a demographics query.
3. **RACE ~40 is judge-inflated.** A lenient local judge scored fluent-but-off-topic prose near Claude's level. FACT + a stronger judge (Gemini) expose what RACE alone hides. Without the scoreboard this run reads "campaign completed, Insights.MD delivered" — a green check over an ungrounded, off-topic result. That is the exact cover-up failure the project fears, now visible.

### CHOSEN TRACK B WORK (user picked both, 2026-07-09) — build next, then re-measure
- **Option 2 — Discovery relevance (biggest gap).** Off-topic sources are the #1 problem. The query planner + source registry over-weight arXiv and don't filter for topical relevance, so a demographics/market query pulled physics papers. Fixes: (a) relevance gate in screening that scores paper-vs-query semantic match and drops off-topic sources (reuse `screening/ranker.py` + a local-LLM relevance criterion in `screening/criteria.py`); (b) query planner should pick sources by topic (OpenAlex/Crossref/web for non-CS topics, not arXiv-first) in `discovery/query_planner.py` + `discovery/source_registry.py`; (c) add a "screening_yielded_offtopic" honesty flag like the existing `screening_yielded_zero`. Target metric: on-topic sources -> RACE Comp/Depth up.
- **Option 3 — In-pipeline citation grounding (FACT 0 -> real).** Every delivered claim must carry a verified statement->source-URL span; unsupported claims dropped/flagged before DELIVER. Fixes: the synthesizer (`synthesis/synthesizer.py`) + reporter (`evaluation/reporter.py`) must emit inline citations (`[n]` + a reference list with URLs) from `ExtractedSource.citations`/paper URLs, and the adversarial `Verifier` (`adversarial/verifier.py`) already checks quote/URL presence — wire its pass/fail so uncited claims don't ship. Reuse the bench `FactScorer` logic as the in-loop grounding check. Target metric: FACT C.Acc 0 -> competitive; E.Cit > 0.

**Verify each with the scoreboard:** after a change, run `research-engine bench --tasks 5 --judge ollama --reuse-engine` (re-score) or without `--reuse-engine` (fresh campaigns), and diff the scorecard. Authenticate `gemini` for a trustworthy multi-task number: `research-engine bench --tasks 20 --judge gemini`.

**Files added this session (branch `feat/deepresearch-bench`):** `bench/` (package + `data/{query,criteria,reference}.jsonl` + `LICENSE.md`), `src/research_engine/llm/gemini_cli_client.py`, `bench` command in `main.py`, gemini branch in `model_registry.py`, `tests/unit/bench/` (22 tests), `docs/architecture/benchmark.md`. Approved plan: `C:\Users\Isaac\.claude\plans\lexical-bubbling-starfish.md`.

## PUSHED — PR #17 open (2026-07-08)
Branch `feat/llm-fulltext-lanes` (29 commits) pushed to origin; **PR #17**: https://github.com/isaac233/Research-Engine/pull/17 (base `main`). Covers golden-eval + anti-poison + self-improvement loops + the full LLM-fulltext 7-lane upgrade (Phases 0-6) + audit TLS/gzip fixes. ~395 tests green, mypy+ruff clean, live campaign verified.

## Whole-Project Audit + "does it actually research?" — 2026-07-08

Audited cohesion/organization/consistency-with-both-prompts and — critically — ran a REAL end-to-end campaign. Found and fixed TWO blockers that made real research impossible; the engine now genuinely performs research.

- **Structure:** clean, domain-organized, no orphan files (only `_run_stub` remains as a safety default; its "future subsystems" comment is now stale — all stages implemented).
- **BLOCKER 1 (TLS) — fixed (`15a5929`):** every HTTPS source failed with CERTIFICATE_VERIFY_FAILED (corporate TLS-inspection root CA absent from certifi). `src/research_engine/__init__.py` now injects `truststore` at import → all httpx/urllib use the OS trust store. Added truststore dependency.
- **BLOCKER 2 (gzip) — fixed (`15a5929`):** crossref/openalex failed "incorrect header check" — `ssrf_guard.safe_request` rebuilt the response with decompressed body but kept `Content-Encoding: gzip` → double-decode. Now strips content-encoding/length on the reconstructed response.
- **PROOF IT WORKS:** live campaign `run "efficient routing in sparse mixture-of-experts models" --sources 3 --quality 0.5` completed end-to-end and delivered `Research/.../*_Insights.MD` with 3 REAL arXiv papers, real quantitative results (e.g. within/across routing similarity 0.8435±0.0879, Cohen's d 1.44), method + data + **replication steps** per source, a source's GitHub code repo, and cross-source synthesis. gemma4:12b (extract) + Mistral-Small (synth) ran on GPU. This is the vision realized (full-text, replication-grade, local-model-driven).
- Discovery now: arxiv + crossref + openalex return papers; semantic_scholar 429s without an API key (graceful, handled). Multi-source works.
- FOLLOW-UP (minor): semantic_scholar needs an API key or backoff for reliability; clean the stale `_run_stub` comment.

## LLM Full-Text Extraction + 7-Lane Plan — 2026-07-08

**Why this work:** user observed the research phase was seconds long and the GPU never spiked. Root cause: the local LLM was **never wired into a run** (`_make_orchestrator` built `SourceRanker()`/`StructuredExtractor()` with no provider), and extraction was regex on abstract-level text — the exact "reads only abstracts, can't replicate" failure the project exists to kill. New spec in `Research Engine Prompt 2.txt`: 7 model lanes, quality/speed + volume sliders, constraint triangle, sequential VRAM load/unload, replication-grade full-text insight.

**Approved plan:** `C:\Users\Isaac\.claude\plans\jolly-wobbling-steele.md` (6 phases). Branch `feat/llm-fulltext-lanes` (cut from `feat/self-research-golden-eval`).

**DONE this session (Phase 0 + Phase 1, live-verified):**
- Phase 0 (`cc1dff2`, `b4fa9a2`): `config/model_lanes.yaml` (7 lanes w/ fallbacks) + `scripts/pull_models.py` (normalize HF tags, pull, record `data/model_pull_report.json`, degrade missing→installed fallback). **All 7 requested tags 404 as written** (`gemma4:12b/26b/31b`, `batiai/qwen3.6-35b:iq3`, etc. are speculative) → every lane currently falls back to an installed model (`gemma4:latest`, `mistral-small3.2:latest`, `qwen2.5-coder:14b`). A real pull is running in the BACKGROUND; check `data/model_pull_report.json` + `data/pull_models.log` next session for any tag that actually resolved.
- Phase 1 (`0849c2c`, `3948e05`): `extraction/llm_extractor.py::LLMSectionExtractor` (chunked map-reduce, defensive JSON parse, ABSENT handling, **verbatim-evidence substring guard** dropping hallucinated claims) + `extraction/chunker.py` + `extraction/prompts.py`. `StructuredExtractor` gained `llm_extractor`; uses LLM path on real full text, regex fallback otherwise, flags `meta.degraded=abstract_only`, sets `extraction_tool=llm:<model>`; added `conclusions`+`replication_notes`. `main.py::_make_orchestrator` wires deep lane via `ModelRegistry` with ping-guarded regex fallback (CI/offline safe).
- **Key fix (`3948e05`):** `gemma4` is a *thinking* model — with a bounded token budget it spent it all on hidden reasoning and returned EMPTY content. Set `think=false` by default on `OllamaClient`. Now clean JSON in ~2.5x fewer tokens.
- **Live acceptance PASSED:** `gemma4:latest` read full text → methodology/data/results/conclusions + 5 evidence-verified claims (0 hallucinated) in ~8s; `ollama ps` showed the model resident with 3.3 GB on the GPU. The GPU-driven full-text extraction the user wanted now works.
- Verification: all tests pass, mypy clean (75 files), ruff clean. New tests: `tests/unit/extraction/test_llm_extractor.py` (8, incl. anti-hallucination + abstract-only skip).

**Phase 2 DONE (`71e162d`), live-verified:**
- `llm/lane_roster.py::LaneRoster.from_yaml` (resolves effective tag from pull report); `llm/lifecycle.py::ModelLifecycleManager` (load/unload keep_alive=0, switch evicts old before loading new, `with_model` ctx-mgr evicts on error, `active()` via `/api/ps`, event hook). `ollama_client.py`: complete() options+keep_alive, `ps/warm/unload`. `model_registry.build_ollama_client()`. `validate-models` now prints a lane table.
- Live: load→switch→unload keeps exactly ONE model resident (no VRAM stacking). Tests added (roster + lifecycle).
- **ALL 7 lanes resolved to REAL models** (`be808af`, `validate-models` all ok): fast `gemma4:12b` (in-VRAM), deep `gemma4:12b` (in-VRAM; the aspirational `gemma4:26b-a4b` MoE does NOT exist, so deep uses 12b — user confirmed fine), overnight `gemma4:31b`, online_a `batiai/qwen3.6-27b:q3` (user-corrected tag), online_b `hf.co/unsloth/Qwen3.6-27B-GGUF:IQ4_XS`, synth_a `hf.co/lmstudio-community/Mistral-Small-3.2-24B-Instruct-2506-GGUF:Q4_K_M`, synth_b `hf.co/KikoCis/gemma-4-31b-it-IQ3_XS-GGUF:IQ3_XS`. Extra installed: `batiai/qwen3.6-35b:iq3` (unused spare).
- **Pull script hardened:** captures raw bytes (no text-mode) to survive ollama's ANSI progress on Windows cp1252; strips control chars from stored errors; incremental report writes. `_resolve_deep_model` in main.py reads the report → deep extraction now runs on gemma4:12b.

**Phase 3 DONE (`23c5cbb`), live-verified:**
- `monitoring/gpu_probe.py::GpuProbe.snapshot()` (nvidia-smi VRAM + `/api/ps` per-model RAM-offload split; None on CI). `telemetry.py`: `model_event`/`gpu_snapshot` + `lifecycle_telemetry_hook`. `orchestrator.status_snapshot` includes live `gpu` + per-stage `models`; `_run_extract` emits model assignment + extractor agent-history action (the deferred P1 item). `status` CLI prints `model[extract]`, VRAM, per-model offload %. Live: probe read 1779/16303 MiB.

**Phase 4 DONE (`dc1ca08`), live-verified:**
- `planning/constraint_triangle.py::solve` (2-of-3 derive 3rd; time governs→no slider→auto-optimize quality; <2 & no time→needs_slider; maps quality tier→per-stage lane assignment). `planning/quality_floor.py::QualityFloor.check` (goal/omission/fabrication). `cli/slider.py` (arrow-key via optional prompt_toolkit, numbered fallback, never hangs/aborts a run — non-TTY/EOF→balanced defaults). `main.py run`: `--quality/--time-budget/--sources`, persists `ResolvedPlan` to campaign meta, volume caps max_sources. `prompt_toolkit` added as optional `[tui]` extra.
- Live: `--time-budget 600`→quality auto 0.63 no slider; `--quality 0.9 --sources 5`→time 409s; bare→balanced default, no hang.
- NOTE: ResolvedPlan.lane_assignment is persisted to meta but stages don't yet READ it to pick lanes — that wiring is Phase 5 (with lifecycle.with_model + handoff docs).

**Phase 5 DONE (`eda41f4`):**
- `synthesis/synthesizer.py::Synthesizer` (deep reads → replication-grade brief via synth lane) + `unique_insight_filter` (drop dup-insight sources, cap at volume). `planning/handoff.py::HandoffDoc` (written on model switch). `main.py`: one Ollama provider drives all lanes — fast-lane `build_llm_scorer` into screening, deep lane into extraction, synth lane into Synthesizer; lane tags via LaneRoster+pull report; heuristic fallback when Ollama absent. `orchestrator`: synthesizer builds the brief (unique-insight sources) w/ reporter fallback + writes extract→evaluate handoff.
- 389 tests pass; mypy+ruff clean (86 files).
- STILL PARTIAL: `ModelLifecycleManager` (Phase 2) is NOT yet wired into the run loop — stages don't call `with_model`/`switch` to sequentially load per-`resolved_plan` lanes; each lane call currently relies on Ollama's own load/keep_alive. Full sequential VRAM handoff per quality-slider lane assignment is the main remaining integration (fold into P6 or a P5.1). Also: LLM query_planner still heuristic (optional, low priority).

**Phase 6 DONE (`44b0bea`) — ALL 6 PHASES COMPLETE:**
- Wired the Phase 2 lifecycle into the run loop (the gap): `orchestrator._switch_lane(stage)` loads the stage's `resolved_plan` lane model via LaneRoster, evicting the previous (one model resident, no VRAM stacking); emits switch telemetry; frees the model at FINALIZE. `main.py` builds ModelLifecycleManager + LaneRoster when Ollama reachable.
- `docs/architecture/model-lanes.md` documents the whole LLM-driven system. Security confirmed (paper text = data, agent-history summaries-only + redaction).
- 392 tests pass; mypy+ruff clean (86 files).

**LOW-PRIORITY REMAINING (optional, next sessions):**
- LLM query planner still heuristic (works fine; low value).
- Overnight/synth_b IQ3 lanes are configured but only used if the quality slider/plan assigns them; not yet exercised live end-to-end.
- Not pushed / no PR — user has not asked to push. Branch `feat/llm-fulltext-lanes` has Phases 0-6.
- Consider a live full campaign on a real OA-paper query at `--quality 0.9` to exercise the full multi-lane handoff path end-to-end (unit-tested; not yet run live as a single campaign).
- **Correct model tags:** user should supply real Ollama tags (or confirm the background-pull resolved ones) to replace the speculative lane tags; IQ3 lanes = synthesis/overnight only, never deep extraction.
- Env: RTX 5080 16GB VRAM + 64GB RAM. Ollama auto-offloads to RAM (no custom bridge). MoE tolerates offload; dense does not.

## This Session
- Done:
  - Read and parsed `Research Engine Prompt1.MD`.
  - Loaded reference/skills/catalog/agents per CLAUDE.md v12.
  - Researched current open-source patterns for research agents, browser automation, and multi-agent orchestration.
  - Used the `planner` agent to produce `docs/plan/master_plan.md`.
  - Created full project directory tree and Phase 0 scaffold (README, HANDOFF, .gitignore, pyproject.toml, routers, eval harness skeleton, GitHub templates).
  - Fixed `router_sim.py` keyword matching and added a load table to `research-engine-router.md` so all `.claude/router_eval/` self-checks pass.
  - Initialized GitHub repo `isaac233/Research-Engine`, opened Pull Request #1, merged it to `main`, and deleted the feature branch.
  - Amended `docs/plan/master_plan.md` to require a consuming-project `Research/` folder with per-campaign sub-folders and differentiated `<campaign>_Insights.MD` files plus an aggregated `Research/Insights.MD`; merged via PR #3.
  - Implemented Phase 1: core orchestrator + model-agnostic LLM layer.
    - `src/research_engine/state.py`: immutable `ResearchRequest`/`Campaign` dataclasses + SQLite append-only store.
    - `src/research_engine/events.py`: append-only event bus.
    - `src/research_engine/llm/`: `LLMProvider` ABC, `OllamaClient`, `AnthropicClient`, `ModelRegistry`.
    - `src/research_engine/orchestrator.py`: campaign lifecycle state machine with pause/resume/kill.
    - `src/research_engine/monitoring/telemetry.py`: sanitized stage telemetry.
    - `src/research_engine/main.py`: `research-engine run/status/pause/resume/kill` CLI.
    - `src/research_engine/config.py`: project path resolution (including `Research/` layout).
    - Tests: 21 unit/integration tests, 80% coverage.
  - Implemented Phase 2: AI-only browser subsystem.
    - `src/research_engine/browser/ai_browser.py`: `AIBrowser` ABC, `BrowserAction`, `BrowserResult`, `BrowserActionType` enum.
    - `src/research_engine/browser/cdp_driver.py`: Playwright/Chromium driver with policy + robots.txt guards.
    - `src/research_engine/browser/raw_http.py`: pooled httpx client with retries, backoff, jitter, header rotation.
    - `src/research_engine/browser/policy.py`: SSRF/ethical URL policy (private IP, localhost, file:// block).
    - `src/research_engine/browser/robots.py`: per-host robots.txt fetcher/cache.
    - `src/research_engine/browser/fingerprint.py`: legitimate header/viewport rotation.
    - `src/research_engine/browser/graphql_client.py`: GraphQL-aware POST helper.
    - `src/research_engine/browser/unblock_probe.py`: browser-based unblocking research probe; never reports "no solution" without an evidence log.
    - `src/research_engine/orchestrator.py`: blocker detection + unblocking campaign dispatch during discovery.
    - `src/research_engine/main.py`: wires `UnblockProbe` as the default browser.
    - Tests: 38 new browser unit tests, total 59 tests, 80% coverage.
  - Implemented Phase 3: discovery + academic search.
    - `src/research_engine/discovery/schema.py`: normalized `Paper`, `SourceQuery`, `SearchResult`, `DuplicateGroup`, `ResolveResult`, `DiscoveryResult` dataclasses.
    - `src/research_engine/discovery/query_planner.py`: decomposes a request into source-specific `SourceQuery` objects.
    - `src/research_engine/discovery/sources/base.py`: `SourceAdapter` ABC.
    - `src/research_engine/discovery/sources/semantic_scholar.py`, `crossref.py`, `arxiv.py`, `openalex.py`, `serp.py`, `web_crawl.py`: academic + web source adapters.
    - `src/research_engine/discovery/dedup.py`: DOI/URL exact match + title fuzzy deduplication with different-DOI guard.
    - `src/research_engine/discovery/snowball.py`: forward/backward citation expansion via source adapters.
    - `src/research_engine/discovery/resolver.py`: full-text resolution through pdf_url, arXiv, Unpaywall, and DOI landing page; never paywalls.
    - `src/research_engine/discovery/source_registry.py`: builds and dispatches adapters by source name.
    - `src/research_engine/discovery/pipeline.py`: end-to-end `DiscoveryPipeline` (plan → search → dedup → snowball → resolve).
    - `src/research_engine/orchestrator.py`: `DISCOVER` stage runs `DiscoveryPipeline`; unblocking campaigns still dispatch browser probe.
    - `src/research_engine/main.py`: constructs `SourceRegistry` + `DiscoveryPipeline` and passes to `Orchestrator`.
    - `pyproject.toml`: added `feedparser>=6.0` dependency.
    - Tests: 56 new discovery unit tests, total 115 tests, 86% coverage.
  - Updated routers with Phase 3 keyword rows and R013–R019 learned-route deltas in `.claude/research-engine-routes.md`.
  - Updated `.claude/agents/discovery-router.md` keyword table for pipeline, schema, registry, orchestrator integration, and main.py.
  - Implemented Phase 4: screening + structured extraction.
    - `src/research_engine/screening/criteria.py`: `BooleanCriterion`, `NumericCriterion`, `LLMRubricCriterion`, `MatchMode`, `CriterionType`, plus factory + default academic criteria.
    - `src/research_engine/screening/ranker.py`: `SourceRanker` applies criteria with optional LLM scorer, returns sorted `SourceScorecard`s; supports must/should/optional weights and `build_llm_scorer` helper.
    - `src/research_engine/extraction/markdownify.py`: HTML → markdown conversion (headings, bold/italic, links, lists, tables) with nav/footer/script/style removal.
    - `src/research_engine/extraction/pdf_converter.py`: `PDFConverter` tries `pdfplumber` then `pypdf`, keeps original on failure.
    - `src/research_engine/extraction/structured.py`: `StructuredExtractor` extracts methodology, data summary, results summary, claims, citations, and conflict detection; abstract fallback when no full text.
    - `src/research_engine/extraction/citation.py`: `extract_citations()`, `normalize_doi()`, `citations_to_dict()`.
    - `src/research_engine/orchestrator.py`: added `SCREEN` and `EXTRACT` stage handlers; persists `scorecards`, `included_papers`, `extracted_sources` to campaign meta; fixed stage-to-stage campaign state freshness.
    - `src/research_engine/main.py`: wires `SourceRanker` and `StructuredExtractor` into `Orchestrator`.
    - `src/research_engine/discovery/schema.py`: added `Paper.to_dict()` / `Paper.from_dict()` for JSON-safe SQLite meta serialization.
    - `src/micro_tools/pdf_to_md/`: standalone PDF → markdown micro-tool with CLI entry point.
    - Tests: 19 new screening/extraction unit tests, total 134 tests, 87% coverage.
  - Updated `.claude/agents/extraction-router.md` keyword table for screening, extraction, orchestrator integration, main.py, and state.
  - Added R020–R027 learned-route deltas to `.claude/research_engine-routes.md` for Phase 4 subsystems.
  - Implemented Phase 5: adversarial verification + evaluation apparatus.
    - `src/research_engine/adversarial/challenge.py`: `Challenge`, `VerificationResult`, `ChallengeDispatcher`, plus dict helpers.
    - `src/research_engine/adversarial/devil.py`: `DevilAgent` rule-based challenger with optional frontier-model deep audit.
    - `src/research_engine/adversarial/verifier.py`: `Verifier` checks quoted evidence, DOI shape, source locators, and URL reachability.
    - `src/research_engine/evaluation/harness.py`: `EvaluationHarness` computes claim, challenge, verification, citation, coverage, and quality metrics.
    - `src/research_engine/evaluation/reporter.py`: `Reporter` produces a Markdown insight brief with claims, evidence, challenges, and caveats.
    - `src/research_engine/evaluation/improvement.py`: `ImprovementProposer` emits candidate R### deltas (never auto-applies).
    - `src/research_engine/evaluation/deep_audit.py`: `DeepAuditor` stub with frontier-model audit path.
    - `src/research_engine/orchestrator.py`: `ADVERSARIAL`, `EVALUATE`, and `DELIVER` stage handlers; persists challenges, verifications, evaluation report, and insight brief.
    - `src/research_engine/extraction/structured.py`: added `paper` to `extracted_source_to_dict()` and `extracted_source_from_dict()` so adversarial stages can reconstruct sources.
    - Tests: 14 new adversarial/evaluation unit tests, total 148 tests, 85% coverage.
  - Updated `.claude/agents/evaluation-router.md` keyword table for orchestrator integration, main.py, and state.
  - Added R028–R033 learned-route deltas to `.claude/research_engine-routes.md` for Phase 5 subsystems.
  - Implemented Phase 6 monitoring/telemetry/status + closed Phase 0–4 gaps.
    - `src/research_engine/llm/__init__.py`: lazy `__getattr__` imports for `AnthropicClient` / `OllamaClient`; no hard runtime dependency on optional clients.
    - `config/default.yaml`: conservative defaults for Unpaywall email, rate limits, browser timeout/retries, and enabled sources.
    - `.claude/agents/{discovery,browser,extraction,evaluation}-router.md`: added `FROZEN EVAL` read-only mode to all four router agents.
    - `src/research_engine/extraction/pdf_converter.py`: `convert_bytes()` for in-memory PDF conversion preserving original byte metadata.
    - `src/research_engine/extraction/structured.py`: URLPolicy-gated full-text fetch with PDF conversion, markdownify HTML extraction, and abstract fallback; wired through `orchestrator.py` via `resolved_map`.
    - `src/research_engine/monitoring/progress.py`: `StageProgressTracker` with uniform/custom weights.
    - `src/research_engine/monitoring/estimator.py`: `TimeEstimator` using per-campaign stage history.
    - `src/research_engine/monitoring/calibrator.py`: `Calibrator` normalizing stage weights from observed durations.
    - `src/research_engine/monitoring/telemetry.py`: `TelemetryAnalyzer` with stuck-stage, stage-failure, and thrashing alerts.
    - `src/research_engine/cleanup/janitor.py`: `CleanupJanitor` vacuums SQLite state DB without touching research artifacts.
    - `src/research_engine/orchestrator.py`: `INIT`, `PLAN`, `FINALIZE` handlers; telemetry/estimator/progress/analyzer integration; `status_snapshot()`; `_run_adversarial` uses `ChallengeDispatcher`; `_run_evaluate` wires `ImprovementProposer` and optional `DeepAuditor`.
    - `src/research_engine/main.py`: `_make_orchestrator` constructs `TimeEstimator`; `status` command prints progress, ETA, remaining stages, and alert count.
    - Tests: 191 tests collected, 88% coverage (`python -m pytest -q`).
  - Added R034–R041 learned-route deltas to `.claude/research-engine-routes.md` for Phase 6 / gap-closure subsystems.
  - Implemented Phase 7: campaign analytics dashboard, model-stack validation, production config loading, and storage cache.
    - `src/research_engine/dashboard.py`: `CampaignDashboard` aggregates campaign status/stage/duration metrics, per-campaign summaries with stage timings, and markdown report generation.
    - `src/research_engine/main.py`: added `report` and `validate-models` CLI commands.
    - `src/research_engine/llm/validator.py`: `ModelStackValidator` pings every configured provider, validates specific model availability, and checks for a small-capacity local model (Gemma/Qwen/Phi/Llama class).
    - `src/research_engine/config.py`: loads `config/default.yaml` with `EngineConfig.get()` dotted access and optional `config_overrides`; added `cache_db_path()`.
    - `src/research_engine/storage/cache.py`: `SourceCache` SQLite-backed cache for discovered `Paper` records keyed by query/source.
    - `src/research_engine/llm/model_registry.py`: moved provider client imports inside `build_provider()` so importing the registry no longer requires optional runtime dependencies.
    - Tests: 31 new unit tests for dashboard, config, validator, and cache; total 219 tests, 88% coverage.
- Open:
  - Continue adversarial review of browser policy and unblocking flow.
  - Wire `SourceCache` into `DiscoveryPipeline` for automatic cache hits/misses (module exists; integration pending).
  - Expand integration tests for `report` and `validate-models` CLI commands.
- Blocked: none.
- Risks:
  - Ethical/legal boundary for "advanced penetration techniques" must remain pinned to authorized/defensive/public-only scope as browser capabilities grow.
  - Local model capability assumption (Gemma/Qwen-class) must be validated during Phase 4 screening/extraction.
  - Unblocking campaigns must not drift into gray-area sources; the SSRF/robots.txt policy is the guardrail.

## v0.1.0 Finish Session — 2026-07-07
- Branch: `finish-v0.1.0` (cut from the `phase-5-adversarial` finish work).
- Bundles A–D audit:
  - ✅ SourceCache wired into `DiscoveryPipeline` (`src/research_engine/discovery/pipeline.py`).
  - ✅ MCP adapter exposes `research_engine_run` and `research_engine_status` with query length / source caps and project-root traversal guard (`src/research_engine/mcp_adapter.py`).
  - ✅ `scripts/github_pr.py` + `scripts/end_session.py` implemented with dry-run default, branch guards, and git-repo validation.
  - ✅ `src/research_engine/cleanup/dedup_files.py` hash-based dedup wired into `CleanupJanitor`.
  - ✅ Architecture docs populated under `docs/architecture/` and Main AI runbook at `docs/runbooks/main-ai-integration.md`.
  - ✅ `Dockerfile` + `docker-compose.yml` added (multi-stage Python 3.12).
  - ✅ E2E campaign test (`tests/e2e/test_campaign.py`) passes with mocked sources.
- Security hardening applied:
  - `URLPolicy._is_public_ip` now rejects multicast/reserved/private/loopback.
  - `URLPolicy._decode_host` percent-decodes hostnames until stable; non-ASCII/IDNA hostnames blocked unless allow-listed.
  - `ssrf_guard.safe_request` reconstructs the response with the original URL so the pinned-IP URL never leaks.
  - `cdp_driver.py`: context-level request routing intercepts every page/popup; popup closes immediately after routing.
  - `discovery/resolver.py`: Unpaywall OA URLs re-validated with `resolve_hosts=True`; RuntimeError from SSRF guard sanitized.
  - `scripts/end_session.py` and `scripts/github_pr.py` validate git repo presence and refuse `main` without `--allow-main`.
- Verification:
  - `pytest -q` → all tests passing, 87% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `.claude/router_eval/*.py` self-checks → all green.
  - `bandit -r src` → 0 HIGH/CRITICAL findings.
  - `scripts/end_session.py` dry-run → completes without touching remotes.
  - `tests/e2e/test_campaign.py` and `tests/integration/test_mcp_adapter.py` pass.
- Security/code review findings fixed in this session:
  - Removed non-existent `WebSocket.close()` handler; HTTP upgrade is already blocked by context-level routing.
  - Prevented internal-IP disclosure in policy / SSRF guard error messages.
  - Fixed `end_session.py` so `github_pr.py` stages/commits/pushes/opens PR instead of committing twice.
  - Added module-level mocked-DNS fixture to `tests/unit/discovery/test_resolver.py` so unit tests no longer hit real DNS.
  - `CDPDriver._fetch` now applies per-action `BrowserAction.headers` via `page.set_extra_http_headers`.

## State of the Build
- **Current work: LLM-driven full-text research engine — PR #17 OPEN** (branch `feat/llm-fulltext-lanes` → `main`, 30 commits).
  - https://github.com/isaac233/Research-Engine/pull/17
  - 7 model lanes + VRAM lifecycle, quality/speed + volume sliders + constraint triangle, replication-grade full-text extraction (methods/data/results), synthesizer + handoff docs, model/GPU telemetry.
  - Audit fixed two blockers that made real research impossible: TLS trust-store (truststore) + gzip double-decode.
  - **Verified:** ~395 tests green, mypy + ruff clean; live end-to-end campaign delivered replication-grade `Insights.MD` from full-text arXiv papers on GPU.
- `main` still at **v0.1.0** (`33c393d`, PR #12, tag `v0.1.0`) until #17 merges.
- To resume next session: `git checkout feat/llm-fulltext-lanes`; read the "PUSHED — PR #17" + audit sections above and `docs/architecture/model-lanes.md`.
- Optional follow-ups: Semantic Scholar API key (429s without it, handled); LLM query planner (still heuristic); a live `--quality 0.9` full multi-lane campaign.

## Next Priority Tasks
1. Gather real-world usage feedback and bug reports from v0.1.0.
2. Plan v0.2.0 scope (likely: DuckDB corpora store, async pipeline, richer browser unblocking, production telemetry sink).
3. Keep router eval baseline current as the codebase grows.

## Decisions / Assumptions
- ADR-001: Python 3.12+ primary; SQLite for state, DuckDB for corpora.
- ADR-002: Port router/eval pattern from Financial Model Training Data.
- Load-bearing assumption: local models can drive deterministic discovery/screening with adversarial oversight.

## v0.1.0+ Standards Document
- Added `Standards.MD` (PR #14) capturing all quality, organization, security, ethics, monitoring, source-management, and session-ritual requirements from `Research Engine Prompt1.MD`.
- It includes pre-change and post-change verification checklists. **Review `Standards.MD` before starting and after completing any future work.**

## v0.1.0+ Source Memory & Agent History Session — 2026-07-07
- Added two searchable SQLite databases to make the engine's prior work reusable and auditable:
  - `src/research_engine/storage/source_memory.py`: `SourceMemory` catalog of good sources with topic/information tags, access methods, reliability scores, search hints, and FTS5 full-text search.
  - `src/research_engine/storage/agent_history.py`: `AgentHistory` append-only audit log of agent actions with URL/API, request/response summaries, outcomes, reasons, evidence links, and redacted headers.
- Added `src/research_engine/storage/_redaction.py` for shared URL/secret/metadata sanitization and `src/research_engine/orchestrator_instrumentation.py` to keep `orchestrator.py` under 800 lines.
- `EngineConfig` gained `source_memory_db_path()` and `agent_history_db_path()`.
- `_make_orchestrator` in `src/research_engine/main.py` now constructs both stores and injects them into `Orchestrator`.
- `Orchestrator` records stage transitions, browser unblocking probes, and discovery search results into `AgentHistory`; discovery sources are remembered in `SourceMemory`.
- Added input-length and URL-policy validation before passing untrusted query/context/URLs to the browser, discovery pipeline, and extractor.
- Added unit tests:
  - `tests/unit/storage/test_source_memory.py`
  - `tests/unit/storage/test_agent_history.py`
  - `tests/unit/storage/test_redaction.py`
  - updated `tests/unit/test_orchestrator.py`
- Updated architecture docs in `docs/architecture/storage.md`.
- Merged via PR #16: https://github.com/isaac233/Research-Engine/pull/16 (commit `efc4e147a48ea3cf13db29427742d335ed4fb57e`).
- Verification:
  - `pytest -q` → all tests passing, 87% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `bandit -r src` → 0 HIGH/CRITICAL findings in changed modules (11 pre-existing LOW/MEDIUM issues elsewhere).

## Self-Research & Golden-Answer Eval Session — 2026-07-08
- Added a deterministic golden-answer evaluation harness and a self-research loop that runs the engine on its own codebase.
  - `src/research_engine/evaluation/harness.py`: `EvaluationReport` gained `precision`/`recall`/`f1_score`; `EvaluationHarness.evaluate()` accepts `expected_claims` and computes precision/recall/F1 via maximum bipartite (Kuhn) claim matching. Paraphrase matching guards against negation, directional opposites, morphological antonyms, qualifier/scope mismatch, numeric mismatch, causal-vs-correlational mismatch, and tautologies.
  - `src/research_engine/main.py`: new `self-eval` CLI command runs a fixture of synthetic sources with known expected claims and reports mean F1, utility mean F1, and a trap robustness score; `--output`/`--force`/`--threshold` options; shared `_validate_output_path` (extracted from `report`).
  - `src/research_engine/extraction/structured.py`: richer claim markers, adjacent-claim merging for multi-sentence findings, confidence scoring (quantitative claims → high), and confidence-based filtering to raise precision.
  - `src/research_engine/evaluation/improvement.py`: R050/R051/R052 delta candidates driven by F1, missing expected claims, and a saturated benchmark.
  - `src/research_engine/evaluation/reporter.py` + `orchestrator.py`: surface precision/recall/F1 in the brief and persisted evaluation report.
  - `scripts/self_research.py`: builds a local doc/source corpus, monkey-patches discovery to return it, drives a full campaign through the orchestrator, then runs the golden-answer benchmark and captures metrics/proposals to JSON. Runtime + F1 thresholds gate exit code.
  - `tests/fixtures/eval_qa.json`: 14 fixtures — 7 utility (all score F1 1.0) + 7 adversarial traps (all correctly score F1 0.0, robustness 1.0).
  - Tests: `tests/unit/evaluation/test_harness.py` (+215), `test_improvement.py`, `test_reporter.py`, `tests/unit/extraction/test_structured.py`, `tests/integration/test_self_eval.py`, `tests/integration/test_self_research.py`.
  - `pyproject.toml`: `pytest.pythonpath` now includes `.` so `scripts.self_research` is importable in tests.
  - `.gitignore`: ignore `data/self_research/` and `coverage.json` generated artifacts.
- Verification:
  - `pytest --no-cov -q` → all tests passing; full run 88% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `bandit -r src scripts` → 0 HIGH/CRITICAL (18 pre-existing LOW, 1 MEDIUM).
  - `research-engine self-eval --fixture tests/fixtures/eval_qa.json` → utility F1 1.0, robustness 1.0.
  - `python scripts/self_research.py` → completes in ~0.25s, 20-doc corpus, campaign `completed`.

## Anti-Poison Hardening + 3× Self-Improvement Loop — 2026-07-08

### Anti-poison audit (pre-loop)
- Verified every learning surface can improve without self-poisoning; fixed two gaps (commit `08b148e`):
  - `SourceMemory.remember`: `reliability_score` now defaults to `None` — an incidental re-remember keeps the learned score (new source → 0.5); explicit score still updates. Kills the destructive `INSERT OR REPLACE` regression.
  - `research-engine-router.md`: added FROZEN EVAL read-only mode (the only router lacking it) so eval runs can't mutate the shared learned-routes memory.
- Safe already: `ImprovementProposer` (all `auto_apply:False`, never applied), router routes log (PROVISIONAL-until-verified, one-delta/miss, `.claude/router_eval/replay` contradiction check), `Calibrator` (0.1 floor, normalized, ETA-only).

### Self-improvement loop (ran the engine on itself 3×, verified each insight, implemented sound ones)
- **Loop 1** (`b729b19`): engine flagged R052 "benchmark saturated at F1 1.0". Probed matcher → found `12 mg` matched `12 kg`. Added unit-aware numeric conflict (compares (number, unit) against a fixed unit set) + `unit-mismatch` trap fixture.
- **Loop 2** (`704e0bd`): R052 again. Found `A outperforms B` matched `B outperforms A`. Added comparative operand-swap guard (same word multiset reordered around a comparative marker → conflict) + `comparative-swap` trap fixture. Benign non-comparative reorders still match.
- **Loop 3** (`a7755ca`): self-research's own metrics came back null. Root cause: corpus screened to 0 included papers (20 scored, 0 kept) → EXTRACT/ADVERSARIAL/EVALUATE/DELIVER silently no-op'd via `_run_stub` reporting "not yet implemented", campaign completed with empty brief and no signal. Added `_run_skipped(reason)` for honest skip reporting + `screening_yielded_zero` meta flag so an empty deliverable is visible, not silent.
- Golden-answer benchmark now 17 fixtures (7 utility + 10 traps); self-eval utility F1 1.0, robustness 1.0. All tests/mypy/ruff clean each loop.

### Known / open for next session
- **Root observation still open:** the default screening criteria exclude the self-research doc corpus entirely (0/20). The loop-3 fix makes this *visible* but does not tune criteria — a docs corpus is genuinely not "academic papers". Next: either (a) add a doc-oriented criteria set for self-research, or (b) have `scripts/self_research.py` assert `screening_yielded_zero` is False so the benchmark exercises the full evaluate path. Until then self-research exercises only the golden-answer benchmark path, not the live-campaign evaluate path.
- Benchmark keeps reporting "saturated" each loop because fixed traps pass; that is expected (bar rises each loop). Real signal is the matcher weaknesses found by probing, not the generic R052 text.
- Branch `feat/self-research-golden-eval`; commits `08b148e`, `b729b19`, `704e0bd`, `a7755ca` on top of `67a21cb`. NOT pushed, no PR.

## Notes for Next Agent
- All routers live under `.claude/agents/` and learned routes under `.claude/research-engine-routes.md`.
- The eval harness under `.claude/router_eval/` must remain isolated from `src/`.
- `scripts/end_session.py` is a stub; do not run it for real until Phase 9.
- The `Research/` folder layout is documented in `docs/plan/master_plan.md` section 4.13 and implemented in `src/research_engine/config.py`.
- Discovery subsystem is fully wired into the orchestrator; start Phase 4 with `screening/criteria.py` and `screening/ranker.py`.
- New Phase 7 modules: `dashboard.py`, `llm/validator.py`, `storage/cache.py`; CLI commands: `report`, `validate-models`.
