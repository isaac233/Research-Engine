# Finish-Line Execution v9 — Evidence-Grounded Scope (task-53 vague-query fix)

> **STATUS 2026-07-20 (build session):** ✅ **R1 (evidence-grounded scope) + R2 (verified checklist critic) BUILT, unit-tested, UNCOMMITTED.** 680 unit tests green (665 base + 15 new), mypy + ruff clean, all env-gated default-off (default path byte-identical). ⏸ R4 WARP deferred (token budget). ▶ **NEXT = R0 live falsifier** (task 53, config B vs A, `RETRIEVAL_CACHE=1`, kimi judge) — see Progress log + Deferred section. New flags: `RESEARCH_ENGINE_SCOPING_PASS`, `RESEARCH_ENGINE_SCOPING_PAGES` (def 4), `RESEARCH_ENGINE_RUBRIC_CRITIC`.

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
- [ ] **Stop rule:** if context budget is tight, stop after R1 is green + lint/type clean + handoff updated. R1 alone justifies the session. R2/R4 are additive.
- [ ] **Never this session:** R3 (ephemeral gap-loop), R5 (backbone pull), any live/bench/Ollama run (MITM + wedge make it slow/fragile — see constraints).

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

## Deferred / next session (checklist stubs — do NOT build now)

### R3 — Bounded ephemeral gap-loop (DuMate ρ_e, the principled W2/W4 retune)
- [ ] Regenerate a small gap-rubric each react round from `(outline, evidence digest)`; cap ≤2 gap queries; only fire AFTER core objectives are banked; stop when no gap remains (adaptive termination wired into `react_planner.run` `max_iters` loop). Reuse `coverage_ledger.py` scaffolding but evidence-conditioned + bounded (NOT the blind 80-cell grid that went −8).

### R5 — Backbone bet (pull a released DR agent, front with our stack)
- [ ] `ollama pull` / obtain `openbmb/AgentCPM-Report-GGUF` (8B, Insight 52.64, fits 16 GB) — NOT yet pulled.
- [ ] A/B WebWeaver-on-Qwen3-30B-A3B and already-pulled Tongyi-DR-30B-A3B as the AGENT (not passive writer), fronted by SearXNG + CDP fetch + v8 parity FACT scorer.

### Live measurement (all deferred — MITM + Ollama wedge make it session-fragile)
- [ ] Run R0 falsifier: task 53 only, config B vs config A, under `RESEARCH_ENGINE_RETRIEVAL_CACHE=1`, kimi judge. Target: IF .339 → .40+, no per-capita-PPP opening.
- [ ] Pre-run hygiene: archive `engine.jsonl` + `scores.jsonl`, purge serp rows in `data/cache.db` before each recorded run (they are resume caches; skip this and you re-score stale evidence).
- [ ] Attach `bench/watchdog.py` via Monitor (heartbeat/STALL; completion notif ≠ liveness).
- [ ] Escalate to N=3 (tasks 51/52/53) only once a lever passes N=1 on 53.
- [ ] Prove generality: add a 2nd underspecified-cohort English bench task; show R1/R2 fix the CLASS, not just task 53.
- [ ] Judge note: kimi judge for comparable absolutes must run OUTSIDE a Claude session (MITM); mistral judge is directionally fine for same-run A/B.

---

## Session-end / handoff checklist (MUST — do not skip)

- [ ] Tick every completed `- [ ]` above; leave unstarted items unticked (accurate handoff > optimistic).
- [ ] Fill the Progress log table (below) with today's rows.
- [ ] Run final gate once more: `pytest -q` (record pass count), `mypy src`, `ruff check src` + `ruff format --check src` — paste results into the Progress log notes.
- [ ] Update `HANDOFF.md` top: what landed (R1 [+R2] built, env flags `RESEARCH_ENGINE_SCOPING_PASS` / `RESEARCH_ENGINE_SCOPING_PAGES` / `RESEARCH_ENGINE_RUBRIC_CRITIC`), the A/B matrix, and the exact next action (R0 live falsifier task-53 B-vs-A under RETRIEVAL_CACHE).
- [ ] Update scoreboard memory `deepresearch-bench-scoreboard.md`: note R1/R2 built + UNCOMMITTED/committed state; winning env string; that no live number moved yet (build-only session).
- [ ] Append ≤1 SAVE-WORTHY heuristic to `memory/heuristics.md` only if a non-obvious lesson emerged (e.g. "single-variable A/B: keep the master rubric switch, gate only the evidence").
- [ ] Change log: list every file touched with a one-line reason (rubric.py, orchestrator.py, test files [, warp.py stub]).
- [ ] Commit discipline: env-gated + default-off means the diff is safe, but per project rules COMMIT ONLY WHEN THE USER ASKS. Stage + propose a `feat:` message (`feat(scope): evidence-grounded rubric scope (R1) + verified checklist (R2), env-gated default-off`); do not push. Do not `--no-verify`.
- [ ] Communicate progress to the user: levers landed, tests green count, mypy/ruff status, what is deferred, the single next action.
- [ ] Run the End-of-Session Ritual (memory/INDEX.md §5.5); delete/curate any now-stale memory notes.

---

## Progress log (fill as you go — handoff accuracy)

| Date | Lever | Status | Tests (pass/total) | Notes |
|---|---|---|---|---|
| 2026-07-20 | R1 evidence-grounded scope | ✅ GREEN (built, unit-tested, UNCOMMITTED) | 680 total (665 base + 10 R1) | `rubric.py` `build_rubric(evidence=)` + `_USER_GROUNDED`; `orchestrator._collect_scope_evidence` + `_scoping_pass_enabled`/`_scoping_pages`; flags `RESEARCH_ENGINE_SCOPING_PASS` / `_SCOPING_PAGES`(def 4). Live A/B (R0) NOT run. |
| 2026-07-20 | R2 verified checklist critic | ✅ GREEN (built, unit-tested, UNCOMMITTED) | 680 total (+5 R2) | `rubric.critique_rubric()` + `orchestrator._rubric_critic_enabled`; flag `RESEARCH_ENGINE_RUBRIC_CRITIC`. Composes on R1 = config C. |
| 2026-07-20 | R4 WARP skeleton | ⏸ DEFERRED (token budget → reserved for session-end) | — | Not started; larger writer blast radius. Full R4 = next session. |
| 2026-07-20 | mypy + ruff gate | ✅ clean | — | `mypy` 2 files clean; `ruff check` clean. NB `ruff format` shows PRE-EXISTING nits in untouched code (lines 100/120/626/672) — not mine; project has no `ruff format`/black enforced. |
| 2026-07-20 | HANDOFF + scoreboard updated | ✅ done | — | HANDOFF.md top + `deepresearch-bench-scoreboard.md` updated; this doc's progress log = source of truth. |
| — | **NEXT SESSION** | ▶ R0 live falsifier | — | task 53, config B vs A, `RETRIEVAL_CACHE=1`, kimi judge (outside Claude session per MITM). Target IF .339→.40+, no per-capita-PPP opening. Then C (A+R1+R2). Then R4. |
