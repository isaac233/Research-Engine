# Hybrid Plan: Tongyi-DR as the ReAct planner's reasoning brain (adapt, don't supplant)

## ⏱️ STATUS (2026-07-20)
- **Phase 0.1 wiring:** BUILT + green (`RESEARCH_ENGINE_REACT_REASONING_MODEL` override,
  flag-gated, 2 tests).
- **Phase 0.2 spike:** RAN (isolated single-model probes, task 51, live SearXNG); findings
  below. Hypothesis **weakened** at fixed page budget.
- **Phase 1 lane integration:** BUILT — `tongyi_dr` / `tongyi_dr_q3` lanes added to
  `config/model_lanes.yaml`, `_react_reasoning_lane()` resolves a managed lane, and
  `_react_plan` loads/evicts the lane via `ModelLifecycleManager` so only one model is
  resident. Env: `RESEARCH_ENGINE_REACT_REASONING_LANE`. Not yet live measured.

| reasoning model | pages | spans | iters | outline | time |
|---|---|---|---|---|---|
| mistral (baseline) | 16 | **174** | 8 | 6 | 384s |
| Tongyi-DR Q4 | 16 | 146 | 7 | 7 | 186s |

**Finding:** retrieval **volume is budget-bound, NOT model-bound** — both hit the 16-page
cap; Tongyi banked *fewer* spans (146 vs 174) but a slightly richer outline (7 vs 6) in
fewer iters. The naive thesis "Tongyi reasoning → more retrieval → RACE up" is **not
supported at fixed budget.** Tongyi's only remaining edge is *quality at equal volume*
(unproven) + the modest writer-role FACT bump (+5.5, [[trained-deepresearch-models]]).

**The spike surfaced a BIGGER, model-agnostic lever:** the react loop banks **174
verbatim spans / 16 pages LIVE** (vs the fixed cache's ~20). That ~8× evidence is the
real RACE-volume opportunity — and mistral drives it, stable, no 30B-offload fragility.

**PIVOT (recommended next):** deprioritize the Tongyi swap; instead (a) FIX the
full-campaign react-banking bug (react banks 174 standalone but ~0 inside
`research-engine bench` — see HANDOFF), then (b) measure full RACE/FACT with the react
loop at volume on **mistral**, and (c) raise `max_pages`. Revisit Tongyi only if a
write+FACT/RACE-score of the two banks proves its bank yields a materially better report.
The new lane integration is the safe, low-cost way to run that comparison when the time
comes.

---

## Thesis
Our RACE ceiling is **evidence volume** (cache/linear runs bank ~4 sources / ~20 spans;
reference reports draw on 100+). Writer-side tuning has plateaued (~27-29 RACE). The
lever we haven't pulled is a **capable model driving gap-driven retrieval**. The #8
`ReactPlanner` is already a WebWeaver-shaped loop — pure DI over injected
`objectives`/`search`/`read`/`summarise`/`refine`/`outline` fns. The missing piece was
a model good enough to drive it; mistral/gemma can't. **Tongyi-DeepResearch-30B-A3B is
that model** (trained for exactly this; measured to already out-ground mistral even as a
passive writer: FACT 44.3→49.8, E.Cit 14.25→17.75 at Q4). This plan routes Tongyi into
the planner's **reasoning** seams while keeping our adapters, EvidenceBank, champion
writer, and honesty gates — additive, flag-gated, fallback-safe.

## Key architectural insight (why this is cheap + safe)
Because Tongyi runs **inside our loop** (not its own agent harness), it is used as a
strong reasoning **LLM** answering our refine/outline/objective prompts — it never emits
tool calls. Our `ReactPlanner` does the tool-calling deterministically through our
policy-guarded adapters. Consequences:
- **No tool-protocol shim** (the usual agent-integration cost is avoided).
- **Honesty/policy scaffold stays in control** — `EvidenceBank.from_pages` still
  substring-guards every span (verbatim from the fetched page); Devil/Verifier +
  drop-unsupported still run; robots/SSRF/URL policy still gates every fetch.
- The delta is **routing 3 lambdas to a second model handle** in `_react_plan`
  (`orchestrator.py:974-979`). The DI already isolates it.

Tradeoff accepted: this captures Tongyi's trained research *reasoning* (gap analysis,
query refinement, outline synthesis) but NOT its autonomous-navigation policy. That is
the right trade — our scaffold enforces safety/reproducibility its autonomous nav would
not. (Full autonomous mode = Alternative B below, only if A's lift is real but capped.)

## Baseline / target (kimi judge, cache A/B + live)
- Writer plateau: `section_synth` RACE ~27-29 / FACT ~44-50% / E.Cit ~14-18.
- Hybrid target (directional): **RACE ↑ via banked-source count** (Comp/Depth/E.Cit),
  FACT held (bank is still verbatim-guarded). DoD gate specified per phase.

## Budget-sharing (the "both see part of the budget" requirement)
Two granularities, built in order:
- **Coarse (Phase 1 spike):** Tongyi = whole PLAN phase (one model resident, no in-loop
  swaps); champion writer + cheap lane = WRITE phase. Sequential residency via the
  existing `ModelLifecycleManager` (load Tongyi → plan → evict → load writer → write).
- **Fine (Phase 3, only if spike passes):** within the plan phase, Tongyi does the
  reasoning steps (objectives/refine/outline); the **cheap lane does high-volume
  summarise** — phase-batched so Tongyi and the summariser don't thrash VRAM. This is
  the genuine per-step split; deferred until the lift is proven (don't build the swap
  scheduler before the hypothesis holds).

---

## Phase 0 — Falsification spike (cheapest experiment — DO THIS FIRST)
**Goal:** prove Tongyi's reasoning lifts retrieval in our loop before any build-out.
Simplest viable wiring: Tongyi Q4 as the reasoning model for `objectives_fn` /
`refine_fn` / `outline_fn`; keep `summarize_fn` on Tongyi too **for the spike** (avoids
in-loop model swaps — one resident model for the whole plan phase); `search_fn`/`read_fn`
unchanged (our adapters). `think=false` + the `_strip_reasoning` already added (the
passive-writer test confirmed Tongyi produces clean structured output this way).

| # | Task | Files | Acceptance / GATE |
|---|---|---|---|
| 0.1 | Add a `reasoning_model` param to `_react_plan`; route `objectives_fn`/`refine_fn`/`outline_fn` (and spike-summarise) to it, default `None` = current single-model behavior. Env `RESEARCH_ENGINE_REACT_REASONING_MODEL`. | `orchestrator.py` | Existing react tests green; None ⇒ byte-identical to today. |
| 0.2 | Live A/B on 1-2 DeepResearch-Bench tasks (SearXNG stack up): reasoning model = mistral vs Tongyi Q4. Record **sources banked, RACE (Comp/Depth), E.Cit, FACT, wall-clock**. | `bench/`, scratch | — |
| 0.3 | **GATE:** Tongyi banks **more relevant evidence** AND lifts **RACE-Comp or E.Cit meaningfully** (target E.Cit well above the ~14-18 writer-role band, toward WebWeaver's breadth) AND finishes within the react deadline (`_MAX_SECONDS`). | HANDOFF | If flat / too slow ⇒ **assumption falsified, STOP** — Tongyi-in-scaffold ≈ mistral or the offloaded 30B is too slow for the loop. |

**Load-bearing assumption (≈70%):** Tongyi's research-trained reasoning, used only as the
planner's refine/outline/objectives brain, produces materially better retrieval than
mistral/gemma — enough to move RACE-Comp/E.Cit — and live wall-clock on the offloaded
30B stays tolerable. Phase 0 falsifies this for the price of one live A/B.

---

## Phase 1 — Lifecycle + lane integration (BUILT 2026-07-20)
| # | Task | Files | Acceptance |
|---|---|---|---|
| 1.1 | Wire Tongyi as a proper lane (`config/model_lanes.yaml` + pull report) so `LaneRoster` resolves it; sequential residency: load Tongyi for PLAN, evict, load writer for WRITE. | `config/model_lanes.yaml`, `orchestrator.py` | BUILT: `tongyi_dr` (Q4_K_M, enabled) and `tongyi_dr_q3` (Q3_K_M, disabled) lanes added; `_react_reasoning_lane()` resolves `RESEARCH_ENGINE_REACT_REASONING_LANE` and `_react_plan` calls `lifecycle.switch`/`unload` around the plan phase. Tests green. |
| 1.2 | Quant pin: Q4_K_M (Q3 measured to erase the edge; a 100-step loop is more quant-sensitive than one-shot writing). | docs | `tongyi_dr` tag pinned to `tongyi-deepresearch-30b-a3b:Q4_K_M`; `tongyi_dr_q3` is `enabled: false`. |

**Usage:** set `RESEARCH_ENGINE_REACT_REASONING_LANE=tongyi_dr` to route the ReAct planner's
reasoning seams (objectives / refine / outline / summarise) through the managed lane while
keeping `search_fn`/`read_fn` on the deterministic adapters. Unset ⇒ the existing
`RESEARCH_ENGINE_REACT_REASONING_MODEL` per-call override (or the synth model) is used.

---

## Phase 2 — Honesty + fallback hardening
| # | Task | Files | Acceptance |
|---|---|---|---|
| 2.1 | Confirm the honesty chain is intact through the Tongyi path: spans substring-guarded at bank insert; Devil/Verifier + drop-unsupported run on the writer output; `planner_found_no_evidence` flag fires when the loop banks nothing. | `orchestrator.py`, `adversarial/*` | Tests: fabricated Tongyi span rejected at insert; empty loop flagged not faked. |
| 2.2 | Fallback: Tongyi loop stall / tool-call malformation / deadline ⇒ fall back to the linear discovery→synth path (already the react None-return contract). | `orchestrator._react_plan` | Live: forced Tongyi failure degrades cleanly to legacy path. |

---

## Phase 3 — Fine budget split (the per-step cheap/Tongyi division) — only if Phase 0-2 hold
**Goal:** stop paying Tongyi for high-volume summarisation; hand summarise to the cheap
lane without VRAM thrash.
| # | Task | Files | Acceptance |
|---|---|---|---|
| 3.1 | Phase-batch the loop: read a round's pages WITHOUT summarising (split summarise out of `_collect`); after Tongyi's reasoning batch, evict Tongyi → load cheap lane → summarise the batch → reload Tongyi for the next round. Bound swaps to ≤2/round. | `planning/react_planner.py`, `orchestrator.py`, `llm/lifecycle.py` | Loop still unit-testable with fakes; live swap count bounded; measure wall-clock vs Phase-0 (Tongyi-does-all). |
| 3.2 | Measure: does the split reduce wall-clock without hurting RACE/FACT? Keep only if net positive. | `bench/` | Split kept only if it pays. |

---

## Phase 4 — Certification
| # | Task | Acceptance (DoD) |
|---|---|---|
| 4.1 | 10-task kimi sweep, hybrid vs current default. | **RACE meaningfully > writer plateau (toward 40+), FACT held ≥ ~48%, E.Cit up substantially**, honesty flags intact, wall-clock acceptable. Archive `bench/out/*.jsonl` first (resume-cache gotcha). |

---

## Alternatives considered (§7)
- **A — Scaffold-hosted Tongyi (CHOSEN for the spike).** Our loop, Tongyi as reasoning
  LLM. Pros: no tool-shim, honesty scaffold intact, minimal delta. Cons: doesn't use
  Tongyi's autonomous-nav training.
- **B — Tongyi-driven autonomous agent.** Tongyi runs its own loop; our search/browser
  exposed as its tools via a protocol shim. Pros: full use of training. Cons: shim build,
  surrenders honesty/policy scaffold, think/grammar-format complexity, bigger blast
  radius. **Escalation path only if A's lift is real but capped** by our scaffold.
- **C — Null: bigger cheap-model retrieval.** Just raise linear source volume with gemma.
  Rejected: gemma can't drive gap-reasoning (the reason #8 exists); adds shallow volume.

## Risks / mitigations
- **Offloaded-30B latency** → Phase-0 measures wall-clock against the react deadline;
  Loop Safety caps (`max_iters`/`max_pages`/`max_seconds`) already bound it.
- **VRAM thrash from cheap↔Tongyi swaps** → Phase 0 avoids it entirely (Tongyi-does-all);
  Phase 3 phase-batches only after the lift is proven.
- **think/grammar-format interaction** → default `think=false`+strip (already works);
  think=true is a measured upside, not a dependency.
- **Quant cliff in the loop** → pin Q4 (Q3 measured to erase the edge).
- **FACT dilution from over-retrieval** → bank stays verbatim-guarded; drop-unsupported +
  Verifier prune; measure FACT alongside E.Cit at every gate.

## First move
Phase 0.1 + 0.2 — one live A/B (Tongyi vs mistral as the react reasoning brain) on 1-2
tasks. Falsifies or confirms the whole direction for the cost of a single run. Needs the
SearXNG/podman stack (HANDOFF session ops) + `RESEARCH_ENGINE_PLANNER=react`.
