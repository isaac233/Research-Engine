# Vendored benchmark data — provenance & license

These files are vendored **verbatim** from **DeepResearch Bench**:

- Repo: https://github.com/Ayanami0730/deep_research_bench
- Paper: https://arxiv.org/abs/2506.11763
- License: **Apache-2.0** (redistribution permitted with attribution)

| File | Upstream path | Purpose |
|---|---|---|
| `query.jsonl` | `data/prompt_data/query.jsonl` | 100 PhD-level research tasks (50 zh + 50 en) |
| `criteria.jsonl` | `data/criteria_data/criteria.jsonl` | per-task RACE criteria + dimension/criterion weights |
| `reference.jsonl` | `data/test_data/cleaned_data/reference.jsonl` | reference reports RACE normalizes against |

Citation:

```
@article{du2025deepresearch,
  author  = {Mingxuan Du and Benfeng Xu and Chiwei Zhu and Xiaorui Wang and Zhendong Mao},
  title   = {DeepResearch Bench: A Comprehensive Benchmark for Deep Research Agents},
  journal = {arXiv preprint arXiv:2506.11763},
  year    = {2025}
}
```

The RACE/FACT scoring logic under `bench/` is a reimplementation against the
upstream prompts and score-calculator (also Apache-2.0), adapted to the engine's
model-agnostic provider layer.
