# Plan — R5 Backbone Integration (scoped to in-session code port)

## 1. Recon findings (changes the original handoff assumptions)

| Target | Original handoff assumption | Current reality (2026-07-20 web check) |
|---|---|---|
| **AgentCPM-Report 8B** | `ollama pull liyishanthu/AgentCPM-Report` → run as agent | It is a **corpus-RAG** system built on **UltraRAG + Milvus + vLLM/llama.cpp**. The web-facing release is Docker-based and indexes local files/Wiki2024. Using it for live web research requires feeding SearXNG/CDP-fetched pages into Milvus as a corpus, then running the AgentCPM-Report pipeline. This is an **infrastructure port**, not a model swap. |
| **WebWeaver / Alibaba-NLP/DeepResearch** | Clone repo → port planner/writer scaffold | The public README does **not** expose a WebWeaver planner/writer scaffold, tool schema, or checkpoint. The only released model is **Tongyi-DeepResearch-30B-A3B** (already pulled). The repo is essentially a model card + inference pointers. |
| **Tongyi-DR-30B-A3B** | Already pulled; use as reasoning backbone | Confirmed available locally. Phase 0.1 wiring (`RESEARCH_ENGINE_REACT_REASONING_MODEL`) already routes `objectives/refine/outline/summarise` to it, but it is treated as an opaque per-call model override, not a managed lane. |

**Conclusion:** the two handoff options are both **outside-session infrastructure projects**, not clean in-session code changes. The best in-session R5 is to **finish the Tongyi integration properly**: add it as a first-class model lane, manage its VRAM residency across the react plan phase, and make it the default reasoning backbone behind the existing env-gated `RESEARCH_ENGINE_REACT_REASONING_MODEL` mechanism.

---

## 2. Goal and non-goal

**Goal:** Tongyi-DeepResearch-30B-A3B becomes a usable, default-off reasoning backbone for the react planner, with correct lane configuration, lifecycle-managed VRAM residency, and tests proving the wiring.

**Non-goal:** We do NOT port AgentCPM-Report's UltraRAG/Milvus stack or fabricate a WebWeaver scaffold that does not exist in the public repo. Those remain outside-session tracks (user runs the pulls; we can scaffold code hooks for them later if desired).

---

## 3. Proposed implementation

### 3.1 Add a Tongyi-DR lane to `config/model_lanes.yaml`

New lane:

```yaml
  tongyi_dr:
    role: planner
    tag: "hf.co/mradermacher/Tongyi-DeepResearch-30B-A3B-GGUF:Q4_K_M"
    fallback: "mistral-small3.2:latest"
    est_vram_gb: 18
    fits_in_vram: false
    num_ctx: 32768
    enabled: true
    use: "Deep-research trained reasoning backbone for the react planner (offloaded 30B-A3B MoE)."
```

Also add a Q3 native-fit variant (commented or separate lane) for users who want native VRAM:

```yaml
  tongyi_dr_q3:
    role: planner
    tag: "hf.co/mradermacher/Tongyi-DeepResearch-30B-A3B-GGUF:Q3_K_M"
    fallback: "mistral-small3.2:latest"
    est_vram_gb: 14
    fits_in_vram: true
    num_ctx: 24576
    enabled: false
    use: "Native-VRAM variant; enable only if Q4 offload is too slow."
```

### 3.2 Default reasoning model selection in `orchestrator.py`

Add an env helper `_react_reasoning_lane()`:

- If `RESEARCH_ENGINE_REACT_REASONING_MODEL` is set → use it verbatim (backward compatible).
- Else if `RESEARCH_ENGINE_REACT_REASONING_LANE=tongyi_dr` (new default-off flag) → resolve the tag from `LaneRoster`.
- Else → fall back to the synthesizer model (today's behavior, byte-identical).

Change the call site in `_react_plan` (currently `reasoning_model = os.environ.get("RESEARCH_ENGINE_REACT_REASONING_MODEL") or model`) to use this helper.

### 3.3 Lifecycle-managed VRAM residency for the react plan phase

Currently the synthesizer model is loaded at campaign start and stays loaded. Tongyi Q4 is 18 GB offloaded; keeping it resident while also loading the writer model will thrash. We need:

1. In `_react_plan`, before the planner runs, call `self.lifecycle.switch(reasoning_tag, num_ctx=...)` to load Tongyi.
2. After `planner.run(query)` returns (in a `finally`-like block), switch back to the synthesizer/writer tag so the write phase has its model resident.

Implementation details:

- Add `Orchestrator._resolve_lane_tag(name: str) -> str` that reads `config/model_lanes.yaml` via `LaneRoster.from_yaml(..., pull_report=...)`.
- Add `_react_plan` guard: if a reasoning lane is requested, `self.lifecycle.switch(reasoning_tag)` before building lambdas; after run, `self.lifecycle.switch(writer_tag)` (or the synthesizer model) so `_react_brief` can write.
- This must degrade gracefully: if `self.lifecycle` is None (tests/headless), skip switching.

### 3.4 Tests

| Test | File | What it proves |
|---|---|---|
| `test_lifecycle_switches_to_reasoning_lane_and_back` | `tests/unit/test_orchestrator_react.py` | Fake lifecycle records load/unload/switch events; planner run loads Tongyi; afterward switches back to writer. |
| `test_react_reasoning_lane_resolves_from_model_lanes_yaml` | `tests/unit/test_orchestrator_react.py` | `RESEARCH_ENGINE_REACT_REASONING_LANE=tongyi_dr` resolves to the configured tag. |
| `test_react_reasoning_model_env_still_overrides_lane` | `tests/unit/test_orchestrator_react.py` | Old `RESEARCH_ENGINE_REACT_REASONING_MODEL=foo` still wins, preserving Phase 0.1 behavior. |
| `test_no_lifecycle_when_lifecycle_none` | `tests/unit/test_orchestrator_react.py` | Tests without lifecycle manager do not crash. |
| `test_tongyi_dr_lane_config_loads` | `tests/unit/llm/test_lane_roster.py` | `LaneRoster.from_yaml` sees the new lane and its attributes. |

### 3.5 Update `docs/plan/hybrid_tongyi_plan.md`

Record that Phase 0.1 is now productionized as a first-class lane, and Phase 0.2 findings still stand (fixed budget → volume-bound, not model-bound). Phase 1 = lifecycle residency is what this plan implements.

---

## 4. A/B plan (after code is green)

Run the same react task-53 config twice under `RESEARCH_ENGINE_RETRIEVAL_CACHE=1`:

```powershell
# Control: current planner lane (online_a / qwen3.6-27b)
RESEARCH_ENGINE_PLANNER=react RESEARCH_ENGINE_REACT_REASONING_LANE=online_a ...

# Treatment: Tongyi-DR backbone
RESEARCH_ENGINE_PLANNER=react RESEARCH_ENGINE_REACT_REASONING_LANE=tongyi_dr ...
```

Compare: pages/spans banked, RACE Comp/Depth/E.Cit, FACT, wall-clock. Gate: Tongyi improves RACE-Comp or E.Cit meaningfully without blowing up wall-clock. If not, the assumption is falsified and we do not promote it to default.

---

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Q4 offload is too slow for the loop | Provide Q3 native-fit lane as opt-in; also keep mistral fallback via `RESEARCH_ENGINE_REACT_REASONING_MODEL`. |
| Lifecycle switch fails / Ollama wedged | Degrade: if `switch()` returns False, log and continue with current resident model. |
| Tongyi tag does not exist on user's Ollama | `LaneRoster` already has fallback mechanism; fallback to `mistral-small3.2:latest`. |
| Keeping default path byte-identical | All new behavior is behind `RESEARCH_ENGINE_REACT_REASONING_LANE`; unset = old `RESEARCH_ENGINE_REACT_REASONING_MODEL` logic = byte-identical. |
| FACT dilution | No change to EvidenceBank or writer; FACT stays on our v8 parity harness. |

---

## 6. Definition of done

- [ ] `config/model_lanes.yaml` has a `tongyi_dr` planner lane (Q4 offload) and a disabled `tongyi_dr_q3` native-fit lane.
- [ ] `orchestrator.py` has `_react_reasoning_lane()` + lifecycle switch in `_react_plan`.
- [ ] 4+ new unit tests green for lane resolution, lifecycle switching, and backward compatibility.
- [ ] `pytest -q` full suite green, `mypy` clean, `ruff` clean.
- [ ] Default path (no new flag) is byte-identical.
- [ ] `docs/plan/hybrid_tongyi_plan.md` updated to reflect Phase 1 completion.
- [ ] User is given exact outside-session command to pull the Q4 tag if it is not already present.

---

## 7. Outside-session dependency (user action)

The Tongyi Q4 tag must be pulled **outside a Claude session** because MITM breaks Ollama/HF TLS in-session:

```powershell
# Already pulled per HANDOFF, but if reinstalling:
ollama pull hf.co/mradermacher/Tongyi-DeepResearch-30B-A3B-GGUF:Q4_K_M
```

If the user wants to pursue the **AgentCPM-Report** track instead, that requires:

```powershell
ollama pull liyishanthu/AgentCPM-Report
# AND building the UltraRAG + Milvus + corpus-RAG → web shim (outside this in-session scope)
```

This plan does not implement that track.
