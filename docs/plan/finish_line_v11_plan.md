# Finish-Line v11 — Capitalize on the Writer-Model Finding

**Status:** PLAN (2026-07-22). Supersedes the "scaffolds exhausted, need a big uncertain build" fork in HANDOFF.
**Thesis:** the RACE gap to 40.67 is a **writer-model** problem, not a scaffold problem, and the bar-clearing model **fits the 16 GB rig**. Stop tuning inference-time scaffolds on `mistral-small3.2`; swap the writer to a deep-research-trained MoE and let it drive the outline-optimization/deepen loop it is actually trained for.

## The bet (one number)

WebWeaver (arXiv:2509.13312, Table 1) on **Qwen3-30B-A3B-Instruct-2507** = **RACE 46.77** (Comp 45.15, **Insight 45.78**, Inst 49.21, Read 47.34) on DeepResearch Bench — beats openai-deepresearch (46.45), Claude-research (45.00), kimi-research (44.64). Bar is 40.67 → **+6**. Qwen3-30B-A3B runs **~87 tok/s on RTX 5080 16 GB** (MoE, 3.3 B active → offload cheap). Insight 45.78 vs our local ~31 = the +14 gap scaffolds never moved.

Two project beliefs falsified from source: WebWeaver is a **sequential single-agent** writer (planner then writer, one at a time, context-pruned) — NOT "4×80G dual concurrent" (that was training). "Writer is the ceiling ~35" is true only for `mistral-small3.2`, which we never replaced as the writer.

Full finding + sources: memory `webweaver-qwen3-moe-writer-unlock.md`.

## Division of labor (hold this line)

- Trained MoE writer buys **RACE** (comprehensiveness + insight).
- WebWeaver-30B's weakness is **FACT** (C.acc 25%). Our existing FACT-parity harness + MiniCheck abstain gate + `fix_citations` hold FACT. Keep them ON for every MoE-writer run.
- Model role matters: **Qwen3-30B-A3B-Instruct-2507** (or Gemma4-31B-MoE) = the **writer**; **Tongyi-DR-30B-A3B / DR-Venus-4B / Fathom-Search-4B** = **searchers** (evidence-gatherers), not writers. Do not repeat the R5 mistake (trained model slotted as a passive sub-call scored 22 — "passive-writer swap wastes them"). Whatever model runs, it must **drive its own loop**.

---

## Phase 0 — Cheapest measurement, no new code (hours) 🔒 gate everything on this

Vehicle: `bench/writer_eval.py` (`score --writer-model <tag>` swaps the synth-lane writer over cached fixed evidence; deterministic; Kimi judge). Single variable = the writer model.

- [ ] Infra up: SearXNG :8080, Ollama (`OLLAMA_NO_CLOUD=1` in-session per [[ollama-recovery-discipline]]), kimi bridge :11444. Confirm bridge (`build_judge('ollama','kimi-k2.7-code:cloud')` → OK).
- [ ] Fixed-evidence cache present? `bench/out/fixed_evidence.jsonl`. If missing: `python -m bench.writer_eval collect --tasks 10` (live retrieval, infra up, watchdog attached). If present, reuse.
- [ ] Pull the proven writer model. `python scripts/pull_models.py` path or `ollama pull` the Qwen3-30B-A3B-**Instruct-2507** Q4_K_M GGUF (verify exact HF repo, e.g. `hf.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF:Q4_K_M`; record to `data/model_pull_report.json`). NB the WebWeaver-proven tag is **Instruct-2507**, distinct from the `Qwen3.6-27B` already in lanes.
- [ ] A/B over identical cached evidence, `--variant section_synth` (champion), Kimi judge:
  - baseline `mistral-small3.2:latest` (current writer)
  - `<Qwen3-30B-A3B-Instruct-2507 Q4_K_M>`
  - `hf.co/mradermacher/Tongyi-DeepResearch-30B-A3B-GGUF:Q4_K_M` (already pulled)
  - command: `OLLAMA_HOST=http://localhost:11444 python -m bench.writer_eval score --variant section_synth --writer-model <tag> --judge ollama --judge-model kimi-k2.7-code:cloud`
- [ ] Judge×N (≥3) the resulting articles to average kimi noise (engine deterministic on frozen evidence per the v10 correction — any single-judge Δ<~2.5 is noise).

**GO/NO-GO:**
- MoE writer beats mistral on RACE/insight over identical evidence (Δ > judge noise) → **writer-model lever is real → Phase 1.**
- Flat → our scaffold constrains the model; the model needs its **own** loop → skip to Phase 2b (native-loop port) and treat Phase 0 as the expected "scaffold caps a strong model" signal. (Phase 0 is necessary-not-sufficient: it tests the model inside OUR fixed-evidence scaffold, not its agentic loop, so a flat result does NOT kill the thesis.)

## Phase 1 — Wire the MoE writer as a first-class lane, measure full pipeline (small code, env-gated)

- [ ] Add `synth_moe` lane to `config/model_lanes.yaml` (Qwen3-30B-A3B-Instruct-2507, role synthesizer, est_vram 18, offload, num_ctx 24576, enabled). Keep `synth_a` mistral as default.
- [ ] Route synth → MoE behind an env flag (reuse the `writer_model` override path or add `RESEARCH_ENGINE_SYNTH_LANE`). Default unset = byte-identical (mistral). Reasoning-strip already handled (`llm/ollama_client.py:18`, `test_strip_reasoning.py`) — verify it catches this GGUF's preamble.
- [ ] Rig sanity: load the lane, confirm VRAM fit + tok/s + no scheduler wedge on sustained sequential calls (the mistral-era wedge risk). Record tok/s + peak VRAM.
- [ ] Full-pipeline A/B on the frozen task-53 + task-57 cache (`scripts/run_task53_ab.sh` with `KEEP_CACHE=1`; add a `synth_moe` cell), MoE writer vs mistral, Kimi judge. This adds the retrieval+outline path back (Phase 0 was evidence→article only).
- [ ] TDD any wiring; keep 750+ unit green, ruff+mypy clean, default path byte-identical.

**GO/NO-GO:** MoE writer lifts RACE (target: clear ~40 on the frozen tasks) with FACT held ≥ mistral baseline (via the gate) → **Phase 4 class-proof + consider Phase 2 for the full 46.77 ceiling.** Underperforms → Phase 2.

## Phase 2 — Give the model its own loop (the real 46.77 lives here; gated on P0/P1)

The proven 46.77 is WebWeaver's **iterative outline-optimization + memory-grounded hierarchical write**, driven by the strong model — not a single fixed-evidence pass. Two options, 2a first.

**2a — extend the existing scaffold to full WebWeaver, run by the MoE (lower risk):**
- [ ] Iterate outline-optimization (WebWeaver: 2–3 rounds moved Insight 46.33→48.35). We have `OutlineBuilder` + `SectionWriter(carry_context)` + `deepen_report`; add the outline re-optimization loop (re-plan the outline from accumulated evidence each round) + raise the WARP deepen rounds now that a model that *knows where to deepen* drives it (mistral capped at ~3; trained models fire 6–15 Expands — AgentCPM-Report 2602.06540 §3.3).
- [ ] Env-gated, single-variable A/B vs Phase-1 MoE-writer-without-outline-loop.

**2b — native-loop port (highest fidelity, most work):**
- [ ] Tongyi-DR-30B-A3B native ReAct harness (Alibaba-NLP/DeepResearch `inference/react_agent.py`) OR AgentCPM-Report 8B WARP loop (`openbmb/AgentCPM-Report-GGUF`), with `search`/`visit` (and AgentCPM's `Search`) tools **shimmed to SearXNG + CDP** (both default to Serper+Jina = HTTP-swappable; our stack replaces them). AgentCPM default retrieval is Faiss corpus-RAG → the shim is required for live web.
- [ ] Sequential model residency via `ModelLifecycleManager.switch` (searcher lane → writer lane) so only one 30B is resident.

**GO/NO-GO:** approach the 46.77 neighborhood on frozen tasks → promote. Note judge mismatch (46.77 is Gemini-judged; we use Kimi — relative story robust, absolutes shift).

## Phase 3 — FACT hold + evidence-gatherer upgrade (parallel to P1/P2)

- [ ] Keep MiniCheck abstain gate + `fix_citations` ON for every MoE-writer run; measure FACT alongside RACE each A/B. Build the FACT-fetch record/replay cache (flagged since v8) before FACT-heavy campaigns — repeated live re-fetch rate-limits hosts and adds noise.
- [ ] (Deferred until writer swap proven) task-53 thin-evidence crater: front the pipeline with a trained live-web searcher — DR-Venus-4B-RL (`inclusionAI/DR-Venus`) or Fathom-Search-4B (`FractalAIResearch/Fathom-Search-4B`), native 4B, GGUF-convert if needed, tools → SearXNG+CDP. Fixes FACT-input (evidence), not RACE-output.

## Phase 4 — Class-proof + promote

- [ ] Winner proven on task-53 **and** task-57 (judge×3) → prove the class on 1–2 more diverse tasks.
- [ ] Promote: flip default synth lane to the MoE writer, or add to a profile (`vague`-style). Keep FACT gate wired.
- [ ] Update HANDOFF + `deepresearch-bench-scoreboard.md` + memory. Commit env-gated; push on user ask only.

---

## Risk register

| Risk | Mitigation |
|---|---|
| Judge mismatch (46.77 Gemini vs our Kimi) | Trust relative deltas, not absolutes; judge×3 |
| Qwen3-30B-A3B Q4 ~18 GB offloads on 16 GB | 87 tok/s holds (3.3 B active); WebWeaver context-pruning keeps long ctx small — verify VRAM/tok/s in P1 |
| Ollama scheduler wedge on sustained MoE calls | `OLLAMA_NO_CLOUD=1`; graceful restart only ([[ollama-recovery-discipline]]); watchdog via Monitor |
| WebWeaver summarizer role used GPT-oss-120b; ours must be small/local | measure with a local summarizer (gemma4:12b `fast` lane); watch for quality leak |
| FACT craters under MoE writer | MiniCheck gate + fix_citations (already built) recover precision |
| Exact HF GGUF repo for Instruct-2507 unverified | confirm at pull time via `scripts/pull_models.py` |

## Do NOT

- Build more inference-time scaffolds on mistral (measured dead: V1 the only survivor, ceiling ~35).
- Slot the trained model as a passive per-call helper (R5 = RACE 22). It drives the loop or it doesn't run.
- Run 4 levers at once (confounds; [[diagnose-before-escalate]]). One variable per A/B.

## Progress log

- 2026-07-22: plan authored from the v11 online research finding. Nothing built yet.
