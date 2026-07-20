# Finish-Line Research v9 — The Vague-Query Weakness (task 53): Online-Research-Backed Fix Plan (2026-07-20)

> **One-line thesis:** Task 53 exposed that the engine resolves an *underspecified* query's scope in a
> single **blind, static, unverified** LLM call (`planning/rubric.py` → `orchestrator.py:1463`). Every
> SOTA deep-research system that leads DeepResearch Bench fixes exactly this by making scope resolution
> **evidence-grounded, verified, and iterative** — and the two strongest inference-time recipes need **no
> training**, so they fit our hardware. An available open **8B local model already beats Claude/OpenAI
> DeepResearch on this benchmark**, so the north-star (beat Opus-class on research) is proven reachable on
> our rig; our gap to it is scaffold + backbone, not raw model power.

---

## 1. The problem, precisely

| | Task 52 (we do well) | Task 53 (exposed the weakness) |
|---|---|---|
| Prompt | "Investment philosophies of Duan Yongping, Warren Buffett, Charlie Munger?" | "Researching how the world's wealthiest governments invest." |
| Cohort | **Given** — 3 named entities | **Must be constructed** — which governments? by GDP? by SWF size? which vehicles (SWFs / pension funds / central-bank reserves)? |
| Evidence | Abundant, fetchable (letters, essays, quotes) | Bot-hostile + PDF (SWF annual reports, IMF/SWFI) |
| Best run | RACE 38.6 / FACT ~72% | RACE 32.7 / FACT 32.5% (crater = mostly instrument, see v8) |

Per-dim gap 53 vs 52 (CDP-era N=3): **instruction_following .339 vs .432 = −.093, the worst gap.**
The best task-53 article opened with a "richest countries by per-capita PPP" essay (Macao casinos) — the
**cohort was misdefined**, and IF/comprehensiveness bled from there. The judge's **#1 comprehensiveness
criterion for task 53 is literally "Definition and Scope of 'Wealthiest Governments' and Investment
Entities."** We are being scored, first and hardest, on the exact thing our pipeline does blind.

**Root cause (crystallized).** `rubric.py::build_rubric` produces a `scope` sentence + sections in **one
LLM call from the raw query, before any evidence is seen, from a weak local model, and never revised.**
For task 52 that is fine (the cohort is in the prompt). For task 53 the local model's first guess at
"wealthiest governments" is wrong and nothing corrects it. This is the same failure mode behind every
prior negative result we logged (see §4).

---

## 2. What the leaderboard actually looks like now (why this is winnable)

Current DeepResearch Bench RACE (from the AgentCPM-Report model card + WebWeaver/RhinoInsight/MindDR papers):

| System | Backbone | RACE | Insight | Note |
|---|---|---|---|---|
| MindDR 1.5 | ~30B-A3B (trained) | **52.5** | — | Li Auto, on HF leaderboard |
| RhinoInsight | Gemini-2.5-Pro | 50.92 | 51.45 | **inference-time, no param updates** |
| WebWeaver | Claude-Sonnet-4 | 50.58 | 50.02 | dual-agent |
| **AgentCPM-Report** | **MiniCPM4.1-8B (local)** | **50.11** | **52.64** | **GGUF released; highest Insight of all** |
| Gemini-2.5-Pro DR | Gemini-2.5-Pro | 49.71 | 49.45 | |
| OpenAI DeepResearch | o3-class | 46.45 | 43.73 | |
| **WebWeaver** | **Qwen3-30B-A3B (local)** | **46.77** | 45.78 | **the MoE class we already run** |
| Claude-research | Claude | 45.00 | 42.79 | |
| Claude-3.7-Sonnet w/Search | Claude-3.7 | 40.67 | — | **our internal "bar"** |
| **our engine (live, best)** | mistral-small3.2 etc. | **~29–33** | ~.32 | task-53 ~19–33 (N=1 variance ±11) |

Two facts reframe the whole effort:
1. **An 8B local model (AgentCPM-Report, 50.11) beats Claude-research (45.00) and OpenAI-DR (46.45).** The
   north-star is not blocked by our hardware — it is blocked by our scaffold and backbone.
2. **WebWeaver on Qwen3-30B-A3B scores 46.77** — on exactly the MoE class our notes say fits 16 GB with
   offload. Our own memory ([[finish-line-webweaver]]) already flagged this as proven-achievable.

The 40.67 "bar" is a waypoint (Claude-3.7, Gemini-era judge). The real ceiling is ~50–52, and it is open.

---

## 3. The convergent SOTA answer (five primary sources, read this session)

Every leading system fixes the vague-scope problem the same way: **ground the scope in evidence, verify it,
and keep it live in the loop.** Ranked by portability to our (untrained, local) stack.

### 3.1 RhinoInsight — arXiv:2511.18743 — RACE 50.92, **inference-time, no training** (most portable)
- **Verifiable Checklist module (t=0, before any search):** from the raw query, build an initial checklist
  `C0` + editable outline `O0` with **no evidence**. A critic (LLM) interprets the query; **"Ambiguous or
  underspecified checks trigger plan intents to refine scope, definitions, and acceptance criteria."** The
  critic then **splits/merges outline nodes, clarifies inclusions and exclusions, and orders by
  importance/dependency** → `C1 = critic(C0, Z0)` → outline `O1 = plan(C1)`.
  *"By clarifying scope, definitions, and acceptance criteria upfront — before search — we reduce drift,
  omissions, and inconsistencies."* This is the exact cure for task-53's cohort drift, and it is a prompt
  loop, not a trained model.
- **Evidence Audit module:** structures every search result into outline nodes, summarizes each cluster
  into source-cited abstracts, iteratively updates the outline, prunes noisy context, and a critic **binds
  high-quality evidence to each claim.** Fights context rot; improves FACT + readability.
- Prompt templates are in the paper appendix (portable).

### 3.2 DuMate-DeepResearch — arXiv:2606.07299 — leaderboard #1, RACE 58.03
- **Coarse-to-fine expansion for dynamic scope:** *"Complex tasks often begin with vague intent… The system
  starts with a **macro-level exploratory retrieval phase that maps the research space and establishes a
  preliminary cognitive framework**"* — i.e. it does a **scoping search first**, then commits the plan.
  This is what our blind `build_rubric` skips.
- **Persistent rubric** `ρ_p = G_p(topic, outline)` injected into planner **and** writer (we do this).
- **Ephemeral rubric** `ρ_e_t = G_e(outline, accumulated_evidence)` refreshed **every cycle**, conditioned
  on evidence already banked → targets the most decision-relevant gaps **and is the stopping signal** ("no
  outstanding gap → stop"). We do **not** do this — it's the principled version of our net-negative W2/W4.
- **Reflection gate** before any tool call: a candidate action passes a lightweight critic; rejected actions
  are revised for a bounded number of rounds → curbs error propagation.
- Rubric guidance is phrased as an **actionable instruction, not a numeric score**.

### 3.3 AgentCPM-Report — arXiv:2602.06540 — **8B local**, RACE 50.11, **Insight 52.64** (highest anywhere)
- **WARP (Writing As Reasoning Policy):** plan-then-write has an **"insight ceiling"** — freezing a static
  outline reduces the writer to an executor and kills emergent insight. Insight is **weight 0.39** in our
  tasks — the single biggest RACE dimension. WARP starts from an **intentionally sparse** outline (titles +
  brief intents), then interleaves **Evidence-Based Drafting** (write a section grounded in retrieval
  conditioned on the narrative so far) ⟷ **Reasoning-Driven Deepening** (treat the *draft itself* as a fresh
  observation, detect the weakest/shallowest section, **Expand** it into sub-sections + targeted retrieval,
  redraft). Terminate when the logical chain is complete.
- **WARP works WITHOUT training (§3.3.1):** prompt-only, on Qwen3-235B, WARP 50.72 vs plan-then-write 49.90,
  **+1.19 Insight, +0.98 Comprehensiveness.** So the loop is portable to our stack as a writer change.
- **Released:** `openbmb/AgentCPM-Report` + `openbmb/AgentCPM-Report-GGUF` (built on MiniCPM4.1-8B),
  code `github.com/OpenBMB/AgentCPM`. **A ~5–6 GB Q4 GGUF fits our 16 GB rig natively with headroom.**

### 3.4 Co-ReAct — arXiv:2605.23590 — rubrics as step-level collaborators in a **ReAct** agent (we run ReAct)
- **Inject–verify–retry per step:** before each tool call, inject a trajectory-conditioned rubric ("what
  should this next action target"); after the action is proposed **but before it executes**, an independent
  verifier checks it against the rubric; on fail, return which criteria are unmet → regenerate the action
  (τ=0.5, **max 1 retry** — cheap). Their search agent + verifier both run on **Qwen3-14B** (small).
- **Critical warning that explains our W2/W4 failure:** *"an unreliable rubric may not merely fail to help:
  when injected into the agent's context, untrained rubrics can actively **mislead** the search process and
  degrade performance."* → the fix for a weak-model rubric is **verification**, not more rubric cells.

### 3.5 AgenticLU / Chain-of-Clarifications — arXiv:2502.15920 — autonomous self-clarification (cheapest lever)
- A **prompt-level** loop (no user, no training; training only amortizes it): (1) *"ask one question about
  what you want to know to better answer this"* → (2) *"find relevant context to answer that clarifying
  question"* (ground) → (3) *"answer the clarifying question"* → (4) answer the original.
- Removing self-clarification costs **−10 to −13 points**; overhead with prefix caching **~2%**.
- For us, autonomously: before planning task 53, the agent asks itself *"which governments count as
  wealthiest, and by what measure?"*, grounds the answer in a 3–5 page scoping search, and only then fixes
  the cohort. Literally a prompt prepended to `_react_plan`.

---

## 4. Why our prior scaffolds went negative — and why these won't (reconciliation)

| Prior attempt | Result | Why it failed | The SOTA correction |
|---|---|---|---|
| W4 grounding brief + W2 coverage ledger | net −8 RACE | 80-cell blind grid **diluted** retrieval; unverified rubric on weak model **misled** (Co-ReAct) | evidence-**conditioned** ephemeral rubric, bounded to ≤2 gap queries/round, **after** core banked |
| task-anchored outline (blind) | FACT crashed | forced sections onto thin evidence; cohort still drift-skewed | scope grounded in a **scoping search first**, then anchor |
| verify-regen / span-entailment | negative | span ≠ page-level judge | (orthogonal; FACT already fixed by v8 parity harness) |
| CiteFix / P-Cite | flat | writer already cites the restated span | — |
| quality slider | no effect | not a real lever | — |

**The through-line:** blind + static + unverified scaffolds on a weak local model are neutral-to-harmful.
Evidence-grounded + verified + iterative scaffolds are what move the leaderboard. v9 is the second kind.

---

## 5. Ranked, hardware-aware plan (all env-gated, default-off, measure-one-at-a-time)

Confidence: **direction = high** (converged across 5 SOTA systems + primary sources); **magnitude on our
stack = medium** (N=1 variance is ±11 RACE — measure under `RETRIEVAL_CACHE`, never trust a single live run).

### R0 — cheapest validation experiment first (do this before anything else)
**Self-clarification + evidence-grounded scope, on task 53 only, under `RETRIEVAL_CACHE`.** Prepend the
Chain-of-Clarifications loop (§3.5) to `_react_plan`: one self-asked scope question → a small scoping search
(3–5 pages) → `build_rubric` is called **conditioned on those snippets** instead of the raw query alone.
Target: **IF .339 → .40+** and the cohort-definition drift disappears (no more per-capita-PPP opening). If IF
moves, the whole thesis holds and R1–R4 are justified. ~1 engine run. *This is the §7 methodology falsifier.*

### R1 — Evidence-grounded scope (DuMate coarse-to-fine + RhinoInsight pre-search checklist) — biggest, cheapest
Replace the blind scope in `rubric.py`. New flow in `orchestrator._react_plan` **before** line 1463:
1. one macro scoping search on the raw query (reuse react `search_fn`, cap ~5 pages);
2. `build_rubric(query, scoping_snippets, …)` — scope/cohort/inclusions-exclusions now **conditioned on real
   evidence**;
3. sections → objectives (as today, line 1475).
Directly targets task-53's #1 criterion (scope definition) and IF. Small, self-contained, env-gated.

### R2 — Verified checklist (RhinoInsight critic + Co-ReAct verify) — guards against "unreliable rubric misleads"
After building the rubric, run **one critic pass**: for each section/scope item, check *"is the cohort
well-defined? inclusions/exclusions explicit? acceptance criteria stated?"* and rewrite. Add per-section
**acceptance criteria** to `Rubric.guidance`. One extra LLM call; this is the safeguard that made our blind
W4 net-negative into a net-positive elsewhere.

### R3 — Bounded ephemeral gap-loop (DuMate ρ_e) — the principled retune of W2/W4
Each react round, regenerate a small gap-rubric from `(outline, evidence digest)` → **≤2** gap queries,
**only after core objectives are banked**; **stop when no gap remains** (adaptive termination). Replaces the
net-negative coverage-ledger default. Reuses `coverage_ledger.py` scaffolding but evidence-conditioned +
bounded. Wire the stop signal into `react_planner`'s `max_iters` loop.

### R4 — WARP draft⟷deepen writing (AgentCPM WARP) — the Insight lever (0.39 weight)
Reframe `_react_brief`'s single whole-bank deepen into the WARP loop: draft each section grounded in
retrieval → read the **draft** → find the shallowest section → **Expand** it (sub-sections + targeted
retrieval) → redraft; terminate on logical completeness. Untrained WARP gains **+1.19 Insight, +0.98 Comp**.
Also raises length toward the 70k-char reference (we were at 19.5k) — the P3 length lever, done structurally.

### R5 — Backbone bet (bigger lift, bigger payoff): run a released DR agent, not a passive-writer swap
Our memory ([[trained-deep-research-models]]) correctly warns: don't waste a trained DR model as a passive
writer. So use one **as the agent**:
- **AgentCPM-Report-GGUF (8B, MiniCPM4.1):** purpose-built WARP, **highest Insight on the board (52.64)**,
  fits 16 GB natively. `ollama pull` a GGUF or run via their `github.com/OpenBMB/AgentCPM` harness; front it
  with our SearXNG + CDP fetch + v8 parity FACT scorer.
- **WebWeaver (`github.com/Alibaba-NLP/DeepResearch`) on Qwen3-30B-A3B:** validated 46.77 on the MoE class we
  run; dynamic-outline dual-agent — the architecture our [[finish-line-webweaver]] plan already targets.
- **Tongyi-DeepResearch-30B-A3B** — already pulled (Q3 14 GB / Q4 18 GB); a trained DR agent to A/B as the
  reasoning/agent backbone rather than the writer.
Evaluate R5 **in parallel** with R1–R4: R1–R4 improve our pipeline; R5 tests whether a purpose-built agent
leapfrogs it. Whichever wins, keep the v8 parity FACT harness + CDP/wayback fetch in front.

### Available local models (for routing R1–R5) — from `ollama list` this session
Tongyi-DeepResearch-30B-A3B (Q3 14 GB / Q4 18 GB) · Mistral-Small-3.2-24B (15 GB) · Qwen3.6-27B (16 GB) ·
gemma4:31b (19 GB) · gemma4:12b (7.6 GB) · qwen2.5-coder:14b · mistral:7b · qwen3.5:4b · nomic-embed-text
(274 MB, for pointback/grounding retrieval) · cloud: kimi-k2-thinking, deepseek-v4-pro (judge/verify only —
MITM caveat [[ollama-recovery-discipline]]). **AgentCPM-Report-GGUF is NOT yet pulled — get it for R5.**

---

## 6. Measurement protocol (unchanged discipline)
- `RESEARCH_ENGINE_RETRIEVAL_CACHE=1` record-then-replay; archive `engine.jsonl`/`scores.jsonl` + purge serp
  before each recorded run; watchdog attached; N=3 (51/52/53) once a lever passes N=1 on 53.
- **Prove generality, not just task 53:** the user's ask is "questions *similar to* 53" — add a 2nd vague
  task (e.g. an underspecified-cohort prompt from the bench's other English tasks) so R1/R2 are shown to fix
  the *class*, not one instance.
- Kimi judge for comparable absolutes (outside a Claude session per MITM note); mistral judge is directionally
  fine for same-run A/B.

## 7. Sources (all read this session)
- RhinoInsight arXiv:2511.18743 (RACE 50.92, inference-time checklist + evidence audit)
- DuMate-DeepResearch arXiv:2606.07299 (leaderboard #1; coarse-to-fine scope; persistent+ephemeral rubric; reflection gate)
- AgentCPM-Report arXiv:2602.06540 + `openbmb/AgentCPM-Report(-GGUF)` (8B local, WARP, Insight 52.64, WARP-without-training §3.3.1)
- Co-ReAct arXiv:2605.23590 (`github.com/ZBWpro/Co-ReAct`) (step-level rubric inject-verify-retry; unreliable-rubric-misleads warning)
- AgenticLU / Chain-of-Clarifications arXiv:2502.15920 (autonomous self-clarification, prompt-level, ~2% overhead)
- Supporting: MindDR arXiv:2604.14518 (30B-A3B, 52.5) · WebWeaver arXiv:2509.13312 (`github.com/Alibaba-NLP/DeepResearch`, Qwen3-30B-A3B 46.77) · OpenResearcher (`github.com/TIGER-AI-Lab/OpenResearcher`, fully-open 30B-A3B recipe) · DiscoBench 2606.27669 · IDRBench 2601.06676 · IntentRL 2602.03468 · ScaffoldAgent 2606.20122 · DeepResearch Bench II 2601.08536
