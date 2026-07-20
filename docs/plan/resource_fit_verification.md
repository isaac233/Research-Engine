# Resource-Fit Verification — RhinoInsight / DuMate / AgentCPM-Report (+ backbones) — 2026-07-20

> **Why this doc.** The v9 research doc (`finish_line_research_v9.md`) mapped the 5 SOTA systems to levers
> R1–R5 from a **desk read** of the papers. This session verified, with **current (July 2026) web
> evidence**, whether those resources are actually **obtainable and runnable on our 16 GB RTX 5080 /
> Ollama-Python / SearXNG + CDP** stack, what conflicts exist, and the minimal modification to use each.
> Method: a 4-agent parallel verification workflow (arXiv + GitHub + HuggingFace + Ollama), high confidence.

## Hardware baseline (verified this session)
RTX 5080, **16303 MiB VRAM (~14.4 GB free)**, 612 GB disk. Fit rule: 8B Q4 (~5 GB) native w/ headroom;
24–27B dense Q4 (~15–16 GB) just fits; 30B-A3B MoE Q3 (~14 GB) native at reduced ctx, Q4 (~18 GB) = CPU offload.

## Per-system verdict

| System | Released? | 16 GB fit | Already implemented | Net-new lever | Verdict |
|---|---|---|---|---|---|
| **AgentCPM-Report** 8B (arXiv:2602.06540) | ✅ full: code (`github.com/OpenBMB/AgentCPM`) + BF16 + **GGUF Q4_K_M 4.97 GB** + Ollama (`liyishanthu/AgentCPM-Report`) + prompts; base MiniCPM4.1 = Apache-2.0 | **NATIVE** (best fit of all; 64K ctx, extendable 128K) | R4 WARP prompt loop (our port of this paper's WARP) | **R5**: run the RL-trained *agent*. Needs their `servers/custom` WARP driver + a retrieval-shim mapping its trained corpus-RAG tool-call → our SearXNG+CDP+reranker | **PULL-AND-RUN / MIXED** |
| **RhinoInsight** (arXiv:2511.18743) | ⚠️ **paper only** — no official code/prompts (only 3rd-party Claude skills, e.g. `github.com/flosters/rhino-deep-research`) | N/A (parameter-free scaffold) | R1/R2 Verifiable-Checklist **+ core of Evidence-Audit** — verbatim `EvidenceBank` spans bound to `Outline` nodes (`outline.partitioned()`/`pruned()`), node-by-node constrained writing | **R6 (new)**: evidence-ranking **critic** — rerank a node's spans by relevance+quality+timeliness+consistency **before** the writer sees them (pre-write, complements v8 post-hoc cite-drop). **SKIP** the cluster-summary step (summarizing-before-citing reintroduces the hallucination surface `EvidenceBank` eliminates) | **mostly ALREADY-HAVE; small PORT-PROMPTS for R6** |
| **DuMate** #1 (arXiv:2606.07299, RACE 58.03) | ⚠️ **closed hosted** Baidu product (`dumate.cn`/Qianfan API); repo = benchmark outputs only; paper CC BY-NC-ND 4.0 | N/A (prompt-only) | R1 coarse-to-fine + persistent rubric (`rubric.py` cites this paper); partial non-LLM analog in `coverage_ledger.py` | **R3**: **ephemeral rubric** `ρ^e = G_e(outline, evidence)` refreshed each cycle → ≤2 gap queries **+ "no outstanding gap" adaptive STOP** (Eq. 7 / Alg. 3). **SKIP** the 2-level recursive Search-Agent fan-out (40+ queries/subtask → cost + 403 pressure on 1 GPU) | **PORT-PROMPTS (R3)** |
| **Backbones**: WebWeaver (2509.13312) / Tongyi-DR-30B-A3B (2510.24701) / Co-ReAct (2605.23590) | code ✅ all Apache-2.0; **SFT/GRPO checkpoints NOT released** (WebWeaver-3k SFT, Co-ReAct rubric-gen) | **Tongyi Q3 14 GB native** (cap ctx ~32-64K) / Q4 18 GB offload — already pulled. **WebWeaver as-shipped does NOT fit** (planner/writer agent **+** separate ≥30B summary model concurrently; README "4×80G GPUs"). Co-ReAct needs 2 GPUs | Tongyi Q3/Q4 already in Ollama | **R5-alt**: port WebWeaver's **prompt scaffold** (dynamic-outline planner + memory-grounded section writer) onto Tongyi; replace Serper→SearXNG, ScraperAPI/Jina→CDP; summarize on our own lane. Co-ReAct verify prompt overlaps our R2 → low marginal value | **PORT-PROMPTS onto Tongyi** |

## Three load-bearing conclusions
1. **No clean "pull the SOTA agent and win."** The two open agents that fit (AgentCPM 8B native; Tongyi 30B Q3 native) are RL-trained for a *different retrieval modality* than our live web (AgentCPM = Milvus corpus-RAG; Tongyi = its own search/visit/python tool schema). Either R5 path needs a **retrieval-shim + harness port**, not just a pull.
2. **The backbone bet buys RACE, not FACT.** WebWeaver on off-the-shelf Qwen3-30B-A3B = RACE 46.77 (> our 40.67 bar) but **FACT 25.00%** (Table 1); the WebWeaver-3k SFT that lifts FACT→85.9% is **unreleased**. So FACT stays on our v8 parity harness + MiniCheck cite-gate **whatever backbone we run**. Do not expect a model swap to fix citation accuracy.
3. **Ranked next levers out of this verification:**
   - **R3** (DuMate ephemeral gap-loop + adaptive stop) — PORT-PROMPTS, **zero VRAM**, scaffolding present (`coverage_ledger.py`), in-session buildable. *Highest ROI / lowest risk.* ← build next.
   - **R6** (RhinoInsight evidence-ranking critic) — PORT-PROMPTS, small, pre-write span rerank. Optional follow-on.
   - **R5** (backbone) — bigger lift, **outside-session** (MITM blocks the pull). Two sub-options:
     - **(a) AgentCPM-Report 8B** — native fit, highest Insight (52.64 on *their* corpus → transfer risk), needs WARP-driver + corpus-RAG→web shim.
     - **(b) Tongyi-30B Q3 + ported WebWeaver scaffold** — already pulled, tool-schema shim needed, buys RACE not FACT.

## Obtain commands (run OUTSIDE a Claude session — MITM breaks HF/Ollama TLS in-session)
- AgentCPM-Report 8B: `ollama pull liyishanthu/AgentCPM-Report`  (5.0 GB, 64K ctx; official alt: `ollama pull hf.co/openbmb/AgentCPM-Report-GGUF:Q4_K_M`)
- WebWeaver scaffold + Tongyi harness (code only, no VRAM): `git clone https://github.com/Alibaba-NLP/DeepResearch`
- Tongyi native-fit quant (if re-pulling): `huggingface-cli download bartowski/Alibaba-NLP_Tongyi-DeepResearch-30B-A3B-GGUF --include "*Q3_K_XL.gguf"`

## Sources (verified this session, not recalled)
arXiv 2602.06540 · 2511.18743 · 2606.07299 · 2509.13312 · 2510.24701 · 2605.23590 ·
github.com/OpenBMB/AgentCPM · huggingface.co/openbmb/AgentCPM-Report(-GGUF) · ollama.com/liyishanthu/AgentCPM-Report ·
github.com/Alibaba-NLP/DeepResearch · huggingface.co/Alibaba-NLP/Tongyi-DeepResearch-30B-A3B ·
github.com/baidubce/qianfan-deepresearch · github.com/ZBWpro/Co-ReAct · github.com/flosters/rhino-deep-research
