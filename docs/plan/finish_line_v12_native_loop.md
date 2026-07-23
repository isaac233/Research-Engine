# Finish-Line v12 — Native WARP-Loop Port (AgentCPM-Report as the AGENT)

**Status:** PLAN (2026-07-22). The multi-session build to clear the RACE bar.
**Why:** v11 proved trained DR models slotted PASSIVELY underperform mistral (Tongyi-writer 33, AgentCPM-writer 35 < mistral-vague 38.27) — their RACE 46-50 lives in their **native agent loop**, which our scaffold bypasses. Champion stays mistral-vague + MiniCheck (RACE 37.91 / FACT ~92%). To clear 40.67 we must run the model's OWN loop.
**Target:** AgentCPM-Report (8B, pulled `liyishanthu/AgentCPM-Report:latest`, native 16GB fit) driving its **WARP loop** (Initialize→Search→Write→Expand→Terminate), retrieval shimmed to our SearXNG+CDP stack, citations re-grounded via MiniCheck. Paper RACE 50.11 / Insight 52.64; WARP works even prompt-only (+1.19 Insight over plan-then-write, Table 3).

## Assets in hand
- **Model:** pulled, native fit, writes clean long-form (v11 confirmed: 22.7k chars, no action-junk).
- **Exact WARP prompts + action schemas** (paper Figs 7-10) — see §Prompts below.
- **Reference driver:** `github.com/OpenBMB/AgentCPM` `AgentCPM-Report/` (UltraRAG-based) — consult for parsing edge-cases.
- **Retrieval tools:** SearXNG shim (`scripts/serp_shim.py`) + CDP fetcher + `EvidenceBank` — the Search action's backend.
- **FACT re-grounding:** MiniCheck abstain gate (built, `ABSTAIN_GATE=flan`) + FACT-parity harness + FACT cache.

## Architecture
AgentCPM is the AGENT; our stack is its TOOLS. New module `src/research_engine/synthesis/warp_agent.py`:
1. **Loop:** Initialize (search→Level-1 outline) → per section: Search(keywords)→retrieve→Write(paragraph w/ `\cite{bibkey}`) → Deepening: Expand(add subsections) or Terminate. Cap rounds (paper: 6-15 Expands optimal; start cap 8).
2. **Action parsing:** extract `<thought>…</thought><action>…</action>`; JSON for initialize/search/expand/terminate, raw content for write. Degrade safely on parse-miss (retry once, else terminate).
3. **Search tool:** keywords → our `search_fn` (SearXNG shim) → top-k URLs → `read_fn` (raw+CDP+PDF) → assign `bibkey` (e.g. `s1,s2…`) → format "Retrieved Information" block with bibkeys + text. Track `bibkey → (url, text)`.
4. **Citation map:** AgentCPM writes `\cite{bibkey}`; post-process → our `[eN]` + References list, so RACE/FACT scorers ingest it unchanged.
5. **Model residency:** AgentCPM resident at num_ctx 24576 the whole loop (single model — no swap, native fit).

## Integration (env-gated, default-off, byte-identical default)
- Flag `RESEARCH_ENGINE_WARP_AGENT=1` (+ `_WARP_AGENT_MODEL`, `_WARP_MAX_EXPANDS`). When set, the deliverable path runs `warp_agent.run(query, search_fn, read_fn, provider, model)` instead of the react/synth brief.
- Wire in `orchestrator` deliverable generation (mirror how `_react_brief` is branched) OR a standalone `scripts/run_warp_task.py` for isolated measurement first (cheaper, no orchestrator entanglement).

## Phases (each ends in a runnable test + a measured checkpoint)
- **Phase 1 — WARP driver + retrieval shim (standalone).** `warp_agent.py` loop + action parse + Search→SearXNG/CDP + bibkey tracking. `scripts/run_warp_task.py` runs it on task 53, emits a markdown report + bibkey map. GATE: produces a real multi-section long-form report (>15k chars, ≥6 sections, real cites) with clean prose. Unit tests for the action parser + citation-map.
- **Phase 2 — Scoring integration.** `\cite{bibkey}`→`[eN]` + References; feed RACE+FACT (kimi judge, FACT cache on). GATE: measured RACE/FACT on task 53 vs champion 37.91/92%. Target RACE ≥ 40.
- **Phase 3 — FACT re-grounding + tuning.** MiniCheck abstain on WARP claims (map bibkey→page); tune expand-cap, context caps, per-search k, dedup. GATE: FACT ≥ 85% with RACE held.
- **Phase 4 — Class-prove + decide.** Tasks 51/52/57; promote (new profile) or record if it doesn't clear the bar. Compare full-loop AgentCPM vs mistral-vague+gate.

## Risks / unknowns
- **Reasoning-strip:** AgentCPM emits `<think>` (v11) AND WARP `<thought>` — the parser must read `<action>`, not strip everything. Handle in the driver, not the generic ollama strip.
- **Token budget:** reasoning model → each action call needs headroom (num_predict ≥ 4000) or actions truncate mid-thought.
- **FACT grounding:** off-the-shelf `\cite` may not map to real spans (v11 passive = 38%); the bibkey→retrieved-text binding + MiniCheck is what makes it verifiable — the load-bearing part.
- **Loop cost/wallclock:** many action calls on an 8B (fast) + retrieval per Search; bound with expand-cap + per-section search cap. Watch for non-termination (hard cap on total actions).
- **Bar reality:** even the native loop may land ~40-46 live (paper's 50 was corpus-RAG + Gemini judge); the win is clearing 40.67, not matching 50.

## Prompts (verbatim from paper Figs 7-10 — the driver's system prompts)
- **Initialize** (Fig 7): "professional report generation expert… provide a simple article outline (top-level sections)… Action Format `<action>{"name":"initialize","title":"...","sections":[{"title":"...","plan":"..."}]}</action>`… Output `<thought>…</thought><action>…</action>`".
- **Search** (Fig 8): "searcher… select 1-5 keywords from user query + current outline + instruction… `<action>{"name":"search","keywords":[...]}</action>`".
- **Write** (Fig 9): "writer… compose a new paragraph, analytical+comparative not just summary, tables/examples encouraged… **BE FAITHFUL, every claim/number supported by cited retrieved info**… `\cite{bibkey}` format… `<action>content</action>`".
- **Expand/Terminate** (Fig 10): "determine whether any section needs expansion… only the single most-needed… `<action>{"name":"expand","position":"section-x.y","subsections":[{"title","plan"}]}</action>` or `<action>{"name":"terminate"}</action>`".

## Progress log
- 2026-07-22: plan authored (research: driver released @ OpenBMB/AgentCPM, prompts extracted). Nothing built yet.
