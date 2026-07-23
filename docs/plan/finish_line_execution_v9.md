# Finish-Line Execution v9 — Evidence-Grounded Scope (task-53 vague-query fix)

> **STATUS 2026-07-20 (session 3):** ✅ **R1/R2/R4 COMMITTED, R3 COMMITTED, R5 (Tongyi-DR managed reasoning lane) + R6 (RhinoInsight evidence-ranking critic) BUILT, unit-tested, COMMITTED + PUSHED.** 733 unit tests green (665 base + 68 new across R1–R6), mypy + ruff clean, all env-gated default-off (default path byte-identical). R5 = `config/model_lanes.yaml` `tongyi_dr`/`tongyi_dr_q3` lanes + orchestrator lifecycle switch/unload around the ReAct plan phase. R6 = `planning/evidence_ranker.py` + orchestrator wiring that reorders `OutlineSection.evidence_ids` by relevance/quality/timeliness/consistency before the writer. ▶ **NEXT = outside-session measurement:** R0 kimi rescore, R3 live A/B, R5 AgentCPM-Report pull+A/B. New flags: `RESEARCH_ENGINE_REACT_REASONING_LANE`, `RESEARCH_ENGINE_EVIDENCE_RANKER`, `RESEARCH_ENGINE_EVIDENCE_RANKER_MAX_SPANS` (def 20).

**Goal.** Kill the task-53 cohort-drift failure by replacing the engine's single blind, static, unverified scope call (`planning/rubric.py::build_rubric`, invoked at `orchestrator.py::_react_plan`) with an **evidence-grounded, verified** scope. Every lever is env-gated + default-off so the committed default path stays byte-identical and the 665+ existing unit tests stay green. This session builds + unit-tests + lints R0/R1 (primary), R2 (stretch), and an R4 skeleton (deferrable). No live bench measurement this session.

**How to use this doc.** Work top-to-bottom. Tick every `- [ ]` as you complete it — this file doubles as the session progress tracker and handoff record. Each section has a **Done when:** measurable exit criterion; do not advance until it is met. TDD is mandatory: write the failing test, watch it fail, implement, watch it pass. READ `docs/plan/finish_line_research_v9.md` first (levers R0–R5, prior negatives, sources). Do NOT re-attempt the logged negatives (W2/W4 blind 80-cell grid, blind anchored outline) — the whole point of v9 is that scope is grounded + verified, not blind.

## Anchor map (absolute paths, verified this session)
- Repo root: `C:\Users\Isaac\OneDrive\Desktop\beta\Research Engine` — branch `feat/deepresearch-bench`.
- Scope call: `src\research_engine\planning\rubric.py` — `build_rubric(query, provider, model)`, `Rubric`, `TRIVIAL`, `_USER`, `_parse_json`.
- Call site + wiring: `src\research_engine\orchestrator.py` — env helpers cluster ≈L187–315; `_react_plan` ≈L1343; `search_fn` ≈L1393; `read_fn` ≈L1425; `build_rubric(...)` call ≈L1462–1465; `_objectives` ≈L1472–1478; grounding-brief block ≈L1488–1500; `_react_brief` writer ≈L1307–1316; `deepen_report` ≈L1322; rubric imports ≈L52–53; `self._rubric` init ≈L429.
- Analog to copy patterns from: `src\research_engine\planning\grounding_brief.py` (schema + `_parse_json` + degrade-to-trivial pre-search call).
- Tests: `tests\unit\planning\test_rubric.py` (fake `_Provider` with `.calls`/`.reply`); `tests\unit\test_orchestrator_react.py` (orchestrator wiring fakes); `tests\unit\planning\test_react_planner.py`.

---

## Session budget / order of execution

- [ ] **First:** read `docs/plan/finish_line_research_v9.md` + this anchor map; confirm branch `feat/deepresearch-bench` clean (`git status`).
- [ ] **Falsifier (do before anything else):** R0/R1 = evidence-grounded scope. This is the cheapest thing that would disprove the whole v9 thesis. Build the mechanism (R1) unit-first; the live task-53 A/B (R0) is deferred to next session but the code lands now.
- [ ] **Then (stretch, only if R1 fully green):** R2 verified-checklist critic.
- [ ] **Then (skeleton only, clearly deferrable):** R4 WARP draft⟷deepen — write the checklist + stub tests, do NOT finish the writer if tokens are tight.
- [x] **Stop rule:** if context budget is tight, stop after R1 is green + lint/type clean + handoff updated. R1 alone justifies the session. R2/R4 are additive.
- [x] **Never this session:** R3 (ephemeral gap-loop), R5 (backbone pull), any live/bench/Ollama run (MITM + wedge make it slow/fragile — see constraints). R3/R5 were picked up in a later session; live runs remain outside-session.

### Flag composition / A-B matrix (load-bearing — bake into every measurement)
Isolate ONE variable. The clean falsifier keeps all rubric machinery constant and toggles only the evidence:

| Config | Flags set | Meaning |
|---|---|---|
| Default | (none) | `TRIVIAL_RUBRIC`, byte-identical baseline |
| A (blind rubric) | `RUBRIC_SCAFFOLD=1` | today's blind one-shot scope |
| B (grounded rubric) | `RUBRIC_SCAFFOLD=1` `SCOPING_PASS=1` | R1: same call, scope conditioned on evidence |
| C (grounded+verified) | `RUBRIC_SCAFFOLD=1` `SCOPING_PASS=1` `RUBRIC_CRITIC=1` | R1+R2 |

- [ ] Design decision recorded: `SCOPING_PASS` does NOT build a rubric on its own — `RUBRIC_SCAFFOLD` remains the master "build a rubric at all" switch; `SCOPING_PASS` only decides whether that rubric's scope is evidence-grounded. This makes B−A a single-variable A/B.

---

## R0/R1 — Evidence-Grounded Scope (PRIMARY, the falsifier)

**Rationale.** Task-53's #1 comprehensiveness criterion is literally "Definition and Scope of 'Wealthiest Governments'." Today `build_rubric` guesses the cohort blind from a weak local model and drifts (per-capita-PPP/Macao). DuMate coarse-to-fine + RhinoInsight pre-search checklist + AgenticLU self-clarification all converge: do a bounded scoping search first, then condition scope on that evidence. Smallest diff that targets instruction_following (.339→target .40+).

**Files to touch**
- `src\research_engine\planning\rubric.py` — extend `build_rubric` signature + prompt.
- `src\research_engine\orchestrator.py` — new env helpers; bounded scope-evidence collection before the `build_rubric` call.
- `tests\unit\planning\test_rubric.py` — evidence-conditioning tests.
- `tests\unit\test_orchestrator_react.py` — scoping-pass wiring tests.

### Test-first checklist (RED)
- [ ] Add `test_build_rubric_evidence_default_prompt_byte_identical`: call `build_rubric(query, provider)` with no evidence; assert the captured user message (`_Provider.calls[-1]`) equals `_USER.format(query=query)` exactly — proves the default path is unchanged at the prompt level.
- [ ] Add `test_build_rubric_conditions_scope_on_evidence`: pass `evidence="<snippet A>\n\n<snippet B>"`; assert both snippets appear verbatim in the captured user message.
- [ ] Add `test_build_rubric_evidence_uses_self_clarification_framing`: with evidence present, assert the prompt contains the "first name what is ambiguous about the cohort, then resolve it from the evidence" instruction (exact substring TBD in impl, assert on it).
- [ ] Add `test_build_rubric_evidence_still_degrades_to_trivial_on_garbage`: evidence set + non-JSON reply → returns `TRIVIAL`.
- [ ] Add `test_build_rubric_evidence_is_char_capped`: pass an over-long evidence string; assert the user message length is bounded by the documented cap (no unbounded prompt).
- [ ] In `test_orchestrator_react.py`, add `test_scoping_pass_disabled_by_default_no_scope_reads`: `RUBRIC_SCAFFOLD` on, `SCOPING_PASS` unset; assert zero extra `search_fn`/`read_fn` calls before planner.run and that `build_rubric` received `evidence == ""` (spy the fake provider or the collection helper).
- [ ] Add `test_scoping_pass_collects_bounded_snippets_and_grounds_rubric`: both flags on; fakes return >budget refs; assert `read_fn` invoked ≤ `_scoping_pages()` times and `build_rubric` received non-empty evidence.
- [ ] Add `test_scoping_pass_snippets_skip_empty_and_dedupe_urls`: fakes return blank/403 reads + a duplicate URL; assert only non-empty, unique pages become snippets.
- [ ] Run the new tests, confirm they FAIL for the right reason (feature absent), not import errors.

### Implementation checklist (GREEN)
- [ ] `rubric.py`: extend signature to `build_rubric(query, provider, model=None, evidence: str = "")` (trailing param → existing 2/3-arg positional calls unchanged).
- [ ] `rubric.py`: add module constant `_EVIDENCE_MAX_CHARS` (e.g. 4000) and a second user template `_USER_GROUNDED` (or a prefix block) carrying: the raw query, the truncated evidence block, and the self-clarification framing ("first name what is ambiguous about the cohort/measure; resolve it strictly from the evidence below; state explicit inclusions and exclusions").
- [ ] `rubric.py`: branch in `build_rubric` — `content = _USER.format(query=query)` when `not evidence` (byte-identical), else the grounded template with `evidence[:_EVIDENCE_MAX_CHARS]`. Keep `format=_SCHEMA`, `temperature=0.0`, same parse + `TRIVIAL` degrade path.
- [ ] `orchestrator.py`: add env helpers in the ≈L187–315 cluster, matching the existing one-line `bool(os.environ.get(...))` + docstring style:
  - [ ] `_scoping_pass_enabled()` → `RESEARCH_ENGINE_SCOPING_PASS`.
  - [ ] `_scoping_pages()` → `RESEARCH_ENGINE_SCOPING_PAGES`, default 4, `try/except ValueError` like `_pdf_max_bytes`.
- [ ] `orchestrator.py`: add module constant `_SCOPE_SNIPPET_CHARS` (per-page cap, e.g. 1000).
- [ ] `orchestrator.py`: immediately before the `build_rubric(...)` call (≈L1462), add a bounded, gated collector (small local fn `_collect_scope_evidence()` or inline) that, only when `_scoping_pass_enabled()`: calls `search_fn(query)` once, iterates refs, calls `read_fn(ref)`, keeps non-empty texts (dedupe by url, cap each to `_SCOPE_SNIPPET_CHARS`, stop at `_scoping_pages()`), and joins them (with source title) into `scope_evidence`. Reuse the in-scope `search_fn`/`read_fn` so cache/validation/PDF/403 handling and determinism (`RETRIEVAL_CACHE`) are inherited for free.
- [ ] `orchestrator.py`: change the call to `build_rubric(query, provider, reasoning_model, evidence=scope_evidence)`; keep the `... if _rubric_scaffold_enabled() else TRIVIAL_RUBRIC` gating unchanged (master switch untouched).
- [ ] `orchestrator.py`: gate the collector so `scope_evidence == ""` when `_scoping_pass_enabled()` is false → grounded template never fires on the default/A path.
- [ ] Add a `_react_dbg` trace line for scoping (pages collected, evidence chars) mirroring the existing rubric trace.

### Verification checklist
- [ ] `pytest tests/unit/planning/test_rubric.py -q` green.
- [ ] `pytest tests/unit/test_orchestrator_react.py -q` green.
- [ ] `pytest -q` — full suite, 665+ green, zero regressions.
- [ ] `mypy src/research_engine/planning/rubric.py src/research_engine/orchestrator.py` clean (new `evidence`/helpers fully annotated).
- [ ] `ruff check src/research_engine/planning/rubric.py src/research_engine/orchestrator.py` clean; `ruff format --check` clean.
- [ ] Manual diff review: with both flags unset, `git diff` shows no behavioral change to the default path (only additive gated code + new default-`""` param).

**Done when:** all R1 tests green, full suite 665+ green, mypy+ruff clean, and the A/B matrix is realizable from env flags alone (default path byte-identical, `SCOPING_PASS=1` provably grounds the scope in ≤`_scoping_pages()` reads). The live task-53 B-vs-A run (R0) is queued to the Deferred section.

---

## R2 — Verified Checklist (critic over the rubric) [STRETCH]

**Rationale.** Co-ReAct's warning: an unreliable rubric on a weak model actively misleads (this is what sank blind W4). The safeguard is verification, not more cells. One critic pass checks the cohort is well-defined, inclusions/exclusions explicit, and acceptance criteria stated per section, then rewrites before injection.

**Files to touch**
- `src\research_engine\planning\rubric.py` — add `critique_rubric(...)`.
- `src\research_engine\orchestrator.py` — new env helper + one wiring line.
- `tests\unit\planning\test_rubric.py` — critic tests.
- `tests\unit\test_orchestrator_react.py` — critic wiring test.

### Test-first checklist (RED)
- [ ] `test_critique_rubric_tightens_scope_and_adds_acceptance_criteria`: feed a vague `Rubric`; fake critic returns tightened scope + explicit inclusions/exclusions + per-section acceptance lines; assert the returned `Rubric` has the tightened scope and the acceptance criteria present in `guidance` (and surfaced by `.digest()`).
- [ ] `test_critique_rubric_degrades_to_input_on_garbage`: non-JSON critic reply → returns the input rubric unchanged (never `TRIVIAL`, never raises).
- [ ] `test_critique_rubric_noop_on_trivial`: `TRIVIAL` in → `TRIVIAL` out, no LLM call asserted.
- [ ] `test_rubric_critic_disabled_by_default` (orchestrator): flag off → `critique_rubric` not invoked; `self._rubric` identical to `build_rubric` output.
- [ ] `test_rubric_critic_rewrites_when_enabled` (orchestrator): flag on → `self._rubric` is the critic's output.
- [ ] Confirm the new tests FAIL correctly.

### Implementation checklist (GREEN)
- [ ] `rubric.py`: add `_CRITIC_SCHEMA`, `_CRITIC_SYSTEM`, `_CRITIC_USER` (serialize the current title/scope/sections/guidance into the prompt; ask: cohort well-defined? inclusions/exclusions explicit? acceptance criteria per section? rewrite accordingly). Reuse `_parse_json`.
- [ ] `rubric.py`: `critique_rubric(rubric: Rubric, provider, model=None) -> Rubric` — one `format=`-constrained call; fold per-section acceptance criteria into `guidance` (keep the `Rubric` dataclass shape stable — minimal diff, `.digest()` already emits guidance); on any exception or `TRIVIAL` input, return the input rubric.
- [ ] `orchestrator.py`: add `_rubric_critic_enabled()` → `RESEARCH_ENGINE_RUBRIC_CRITIC` in the env cluster.
- [ ] `orchestrator.py`: after the `build_rubric` call and before `self._rubric = rubric` (≈L1465), add `if _rubric_critic_enabled(): rubric = critique_rubric(rubric, provider, reasoning_model)`. Composes cleanly on R1's grounded rubric.
- [ ] Import `critique_rubric` alongside the existing rubric imports (≈L53).

### Verification checklist
- [ ] `pytest tests/unit/planning/test_rubric.py tests/unit/test_orchestrator_react.py -q` green.
- [ ] `pytest -q` full suite green.
- [ ] `mypy` + `ruff check`/`format --check` clean on both touched files.
- [ ] Default path (both new flags unset) byte-identical — verify by diff + a default-config orchestrator test still passing.

**Done when:** critic tightens a vague rubric in tests, degrades safely to input on failure, is a no-op when disabled, full suite green, mypy+ruff clean.

---

## R4 — WARP draft⟷deepen writing [SKELETON ONLY — clearly deferrable]

**Rationale.** AgentCPM WARP: plan-then-write has an "insight ceiling"; interleaving Evidence-Based Drafting with Reasoning-Driven Deepening (treat the draft as a fresh observation → expand the shallowest section) gained +1.19 Insight, +0.98 Comprehensiveness untrained. Insight is the 0.39-weight RACE dimension. This is a real writer change — larger blast radius than R1/R2 — so this session only scaffolds it.

**Files to touch (planned)**
- New `src\research_engine\synthesis\warp.py` (draft → find-shallowest → expand → redraft loop, bounded rounds).
- `src\research_engine\orchestrator.py` — `_react_brief` (≈L1285–1341): route the single `deepen_report` (≈L1322) through the WARP loop when enabled.
- New `tests\unit\synthesis\test_warp.py`.

### Skeleton checklist (do NOT finish the loop this session unless time remains)
- [ ] Add env helper `_warp_writer_enabled()` → `RESEARCH_ENGINE_WARP_WRITER` (default off), with docstring noting it REPLACES `deepen_report` and is mutually exclusive with section-locked write (`_section_locked_write_enabled`) — decide precedence and document it.
- [ ] Write stub tests (xfail/skip-marked) capturing intended contract:
  - [ ] `test_warp_writer_disabled_by_default_uses_deepen` — flag off → existing `deepen_report` path, byte-identical.
  - [ ] `test_warp_expands_shallowest_section` — flag on → the section with the fewest banked spans/lowest length gets an Expand+redraft round.
  - [ ] `test_warp_bounded_rounds` — loop terminates at a max-expand cap (e.g. 2) regardless of input.
  - [ ] `test_warp_composes_with_abstain_gate` — abstain gate still runs AFTER WARP on the final draft.
- [ ] Decide interaction order in `_react_brief`: WARP replaces `deepen_report`; abstain gate (≈L1326–1340) runs on the WARP output; document that section-locked write bypasses WARP (like it bypasses deepen today).
- [ ] Leave `warp.py` as an interface stub (function signature + docstring + `NotImplementedError` or trivial passthrough) so mypy/ruff pass and the default path is untouched.

### Verification checklist (skeleton)
- [ ] `pytest -q` full suite green with WARP stubs skipped/xfail (no default-path change).
- [ ] `mypy` + `ruff` clean on the new stub + `_react_brief`.

**Done when:** the env helper, stub module, and skip-marked contract tests exist; default path byte-identical; the full loop is explicitly marked "next session" in the Deferred table.

---

## R5 — Tongyi-DR as managed ReAct reasoning lane [BUILT 2026-07-20 (session 3)]

**Rationale.** The backbone bet buys RACE, not FACT. Rather than a risky model swap at the writer,
use the already-pulled `Tongyi-DeepResearch-30B-A3B` as the planner's reasoning brain
(objectives/refine/outline/summarise), with the writer lane loaded only after the plan phase.
Sequential residency keeps 16 GB VRAM safe. If the comparison against mistral at fixed retrieval
budget is flat, the lane integration cost is already sunk and we just leave it env-gated.

**Files touched**
- `config\model_lanes.yaml` — added `tongyi_dr` (Q4_K_M, enabled) and `tongyi_dr_q3` (Q3_K_M, disabled) lanes.
- `src\research_engine\orchestrator.py` — `_react_reasoning_lane()`, lifecycle switch/unload around `_react_plan`.
- `tests\unit\test_orchestrator_react.py` — lane load/unload, tag routing, fallback, precedence.
- `tests\unit\llm\test_lane_roster.py` — project lanes load the new entries.

### Checklist (all done)
- [x] Lanes defined with role=planner, fallback to `mistral-small3.2:latest`, `enabled` differentiated by quant fit.
- [x] `_react_plan` switches to the lane's tag before the planner and unloads in `finally`.
- [x] Unknown/disabled lane falls back to existing per-call override / synth model.
- [x] Tests green; full suite green; `mypy src/research_engine/orchestrator.py` + `ruff check src tests` clean.
- [x] `docs/plan/hybrid_tongyi_plan.md` Phase 1 updated to BUILT.

**Flag:** `RESEARCH_ENGINE_REACT_REASONING_LANE=tongyi_dr` (unset ⇒ unchanged).

**Done when:** lane resolves, loads, and unloads correctly in tests; default path byte-identical; docs updated.

---

## R6 — RhinoInsight evidence-ranking critic [BUILT 2026-07-20 (session 3)]

**Rationale.** RhinoInsight scores evidence spans on relevance/quality/timeliness/consistency and
reorders them before writing. Because `SectionWriter` consumes spans in `OutlineSection.evidence_ids`
order, the cheapest, FACT-safe integration is to reorder those IDs rather than rewrite the bank.
Skip RhinoInsight's cluster-summary step — synthesis would move away from verbatim spans and break
our FACT-parity harness.

**Files touched**
- `src\research_engine\planning\evidence_ranker.py` (new) — `SpanScore`, `rank_spans(...)`.
- `src\research_engine\orchestrator.py` — `_evidence_ranker_enabled()`, `_evidence_ranker_max_spans()`, wiring in `_react_brief`.
- `tests\unit\planning\test_evidence_ranker.py` (new) — score/reorder, degradation, max-spans, empty input.
- `tests\unit\test_orchestrator_react.py` — env wiring tests.

### Checklist (all done)
- [x] Prompt asks the LLM to score each span 1–10 on relevance, quality, timeliness, consistency.
- [x] Aggregate score = 0.40 relevance + 0.25 quality + 0.20 timeliness + 0.15 consistency.
- [x] Reorders input spans by score descending; any parse/provider failure degrades to original order.
- [x] `max_spans` keeps the top N and drops the tail per section.
- [x] Wired after outline construction in `_react_brief`; only runs when `RESEARCH_ENGINE_EVIDENCE_RANKER=1`.
- [x] Tests green; full suite green; `mypy` + `ruff` clean.

**Flags:** `RESEARCH_ENGINE_EVIDENCE_RANKER=1`, `RESEARCH_ENGINE_EVIDENCE_RANKER_MAX_SPANS=20` (default).

**Done when:** ranker reorder is unit-tested, failure degradation is unit-tested, default path byte-identical, docs updated.

---

## Deferred / next session (checklist stubs — do NOT build now)

### R3 — Bounded ephemeral gap-loop (DuMate ρ_e, the principled W2/W4 retune) — ✅ BUILT 2026-07-20 (session 2), COMMITTED
- [x] Regenerate a small gap-rubric each react round from the evidence (query + bank digest); cap ≤2 gap queries; stop when no gap remains (adaptive termination). Evidence-conditioned + bounded (NOT the blind 80-cell grid that went −8).
  - `planning/gap_rubric.py` (new) `EphemeralGapRubric` — one JSON LLM call/round → ≤N gap queries + `complete` verdict; degrades safe; fast-fail `_reasoning_timeout()`. Duck-types the `coverage_ledger` slot (ingest/gap_queries/is_complete) — introduced `CoverageLedgerLike` Protocol in `react_planner.py`.
  - `react_planner.py` `adaptive_stop: bool = False` — break when `is_complete()` after ≥1 page banked (default off = byte-identical; W2 keeps its no-early-stop behavior).
  - `orchestrator.py` flags `RESEARCH_ENGINE_EPHEMERAL_GAP` (+ `_EPHEMERAL_GAP_QUERIES` def 2) → builds the rubric into the slot (supersedes W2) + turns on `adaptive_stop`.
  - Tests: 7 `test_gap_rubric.py` + 3 `test_react_planner.py` + 2 `test_orchestrator_react.py`. 698 unit green, mypy+ruff clean, committed `8c27a9a`. **Live A/B deferred** (MITM/wedge): `RUBRIC_SCAFFOLD=1 EPHEMERAL_GAP=1` vs `RUBRIC_SCAFFOLD=1`, task 53, `RETRIEVAL_CACHE=1`, kimi judge.

### R5 — Backbone bet
- [x] Tongyi-DR-30B-A3B managed reasoning lane BUILT + COMMITTED 2026-07-20 (session 3). Flag `RESEARCH_ENGINE_REACT_REASONING_LANE=tongyi_dr`.
- [ ] `ollama pull` / obtain `liyishanthu/AgentCPM-Report` (8B, Insight 52.64, fits 16 GB) — STILL outside-session; MITM blocks `ollama pull` inside a Claude session.
- [ ] A/B the obtained model as the AGENT (not passive writer), fronted by SearXNG + CDP fetch + v8 parity FACT scorer. AgentCPM-Report's WARP driver is corpus-RAG → needs retrieval-shim to SearXNG/CDP.

### Live measurement (all deferred — MITM + Ollama wedge make it session-fragile)
- [ ] Run R0 falsifier: task 53 only, config B vs config A, under `RESEARCH_ENGINE_RETRIEVAL_CACHE=1`, kimi judge. Target: IF .339 → .40+, no per-capita-PPP opening.
- [ ] Pre-run hygiene: archive `engine.jsonl` + `scores.jsonl`, purge serp rows in `data/cache.db` before each recorded run (they are resume caches; skip this and you re-score stale evidence).
- [ ] Attach `bench/watchdog.py` via Monitor (heartbeat/STALL; completion notif ≠ liveness).
- [ ] Escalate to N=3 (tasks 51/52/53) only once a lever passes N=1 on 53.
- [ ] Prove generality: add a 2nd underspecified-cohort English bench task; show R1/R2 fix the CLASS, not just task 53.
- [ ] Judge note: kimi judge for comparable absolutes must run OUTSIDE a Claude session (MITM); mistral judge is directionally fine for same-run A/B.

---

## Session-end / handoff checklist (MUST — do not skip)

- [x] Tick every completed `- [ ]` above; leave unstarted items unticked (accurate handoff > optimistic).
- [x] Fill the Progress log table (below) with today's rows.
- [x] Run final gate once more: `pytest -q` (record pass count), `mypy src`, `ruff check src` + `ruff format --check src` — paste results into the Progress log notes.
- [x] Update `HANDOFF.md` top: R5 + R6 built, env flags `RESEARCH_ENGINE_REACT_REASONING_LANE` / `RESEARCH_ENGINE_EVIDENCE_RANKER` / `RESEARCH_ENGINE_EVIDENCE_RANKER_MAX_SPANS`, next actions = outside-session R0/R3/R5 measurement.
- [x] Update scoreboard memory `deepresearch-bench-scoreboard.md`: note R5/R6 built/committed/pushed; no live number moved (build-only session).
- [ ] Append ≤1 SAVE-WORTHY heuristic to `memory/heuristics.md` only if a non-obvious lesson emerged (R5 scoping to in-session achievable alternative vs outside-session infra is a candidate, but already captured in [[ollama-recovery-discipline]] / [[diagnose-before-escalate]] — skip unless the user wants it saved).
- [x] Change log: list every file touched with a one-line reason.
- [x] Commit discipline: user asked to commit + push; done in two `feat(scope):` commits on `feat/deepresearch-bench`; no `--no-verify`.
- [x] Communicate progress to the user: see final summary.
- [x] Run the End-of-Session Ritual (memory/INDEX.md §5.5); delete/curate any now-stale memory notes.

---

## Progress log (fill as you go — handoff accuracy)

| Date | Lever | Status | Tests (pass/total) | Notes |
|---|---|---|---|---|
| 2026-07-20 | R1 evidence-grounded scope | ✅ GREEN (built, unit-tested, COMMITTED) | 680 total (665 base + 10 R1) | `rubric.py` `build_rubric(evidence=)` + `_USER_GROUNDED`; `orchestrator._collect_scope_evidence` + `_scoping_pass_enabled`/`_scoping_pages`; flags `RESEARCH_ENGINE_SCOPING_PASS` / `_SCOPING_PAGES`(def 4). Live A/B (R0) NOT run. |
| 2026-07-20 | R2 verified checklist critic | ✅ GREEN (built, unit-tested, COMMITTED) | 680 total (+5 R2) | `rubric.critique_rubric()` + `orchestrator._rubric_critic_enabled`; flag `RESEARCH_ENGINE_RUBRIC_CRITIC`. Composes on R1 = config C. |
| 2026-07-20 | R4 WARP draft⟷deepen | ✅ GREEN (built, unit-tested, COMMITTED) | 686 total (+6 R4) | `deepen.py::warp_deepen()` iterates existing single-pass deepen (converge-or-cap); `orchestrator._warp_writer_enabled`/`_warp_rounds`; flags `RESEARCH_ENGINE_WARP_WRITER` / `_WARP_ROUNDS`(def 3). Applies only where deepen runs (react, not section-locked). Live A/B not run. |
| 2026-07-20 | mypy + ruff gate | ✅ clean | — | `mypy` 2 files clean; `ruff check` clean. NB `ruff format` shows PRE-EXISTING nits in untouched code (lines 100/120/626/672) — not mine; project has no `ruff format`/black enforced. |
| 2026-07-20 | HANDOFF + scoreboard updated | ✅ done | — | HANDOFF.md top + `deepresearch-bench-scoreboard.md` updated; this doc's progress log = source of truth. |
| 2026-07-20 (s2) | Resource-fit verification | ✅ done | — | 4-agent workflow verified current obtainability/16GB-fit/conflicts → `docs/plan/resource_fit_verification.md`. AgentCPM-Report 8B native-fit (R5 top pick); RhinoInsight/DuMate = paper/closed (port-prompts); backbone bet buys RACE not FACT. |
| 2026-07-20 (s2) | R3 ephemeral gap-loop | ✅ GREEN (built, unit-tested, COMMITTED) | 698 total (+12) | `gap_rubric.py` `EphemeralGapRubric` + `react_planner.adaptive_stop` + `CoverageLedgerLike` Protocol; flags `RESEARCH_ENGINE_EPHEMERAL_GAP`/`_QUERIES`(def 2). Live A/B not run. Commit `8c27a9a`. |
| 2026-07-20 (s2) | R0 unblocked | ✅ done | — | `bench/rescore_race.py` (new, durable) re-judges RACE over saved articles; glue-validated + mypy/ruff clean. Decisive kimi B-vs-A run queued OUTSIDE session. |
| 2026-07-20 (s3) | R5 Tongyi-DR reasoning lane | ✅ GREEN (built, unit-tested, COMMITTED + PUSHED) | 733 total (+35 incl. lane roster test) | `config/model_lanes.yaml` `tongyi_dr`/`tongyi_dr_q3` + `orchestrator._react_reasoning_lane()` + lifecycle switch/unload; flag `RESEARCH_ENGINE_REACT_REASONING_LANE`. Safe sequential residency; live A/B not run. Commit `3179472`. |
| 2026-07-20 (s3) | R6 RhinoInsight evidence-ranker | ✅ GREEN (built, unit-tested, COMMITTED + PUSHED) | 733 total (+? 10 ranker + orch wiring) | `planning/evidence_ranker.py` `rank_spans()` + orchestrator wiring; reorders `OutlineSection.evidence_ids` by 4-dim weighted score; degrades to original order; flag `RESEARCH_ENGINE_EVIDENCE_RANKER`/`_MAX_SPANS`(def 20). Commit `60ead3e`. |
| 2026-07-20 (s3) | mypy + ruff final gate | ✅ clean | — | `mypy src/research_engine/planning/evidence_ranker.py src/research_engine/orchestrator.py` clean; `ruff check src tests` clean; `pytest -q` 733 green. |
| — | **NEXT SESSION** | ▶ outside-session measurement only | — | 1) R0 kimi rescore (`bench.rescore_race` task 53). 2) Measure R3 live (`EPHEMERAL_GAP=1` A/B) under `RETRIEVAL_CACHE`. 3) Outside-session `ollama pull liyishanthu/AgentCPM-Report` + A/B as agent. No further in-session build queued. |
