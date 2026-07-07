# Research Engine

A model-agnostic, locally-driven research apparatus that turns a natural-language research request from a main AI (Claude Code / Opus / Kimi) into a fully executed internet research campaign—delivering structured insights, evidence maps, and status updates while consuming minimal premium-AI tokens.

> **Status:** Phase 1 core orchestrator + model-agnostic LLM layer merged to `main` via PR #4. Phase 2 AI-only browser (CDP/Playwright, raw HTTP, GraphQL, robots.txt, SSRF policy, unblock probe) merged via PR #7. Phase 3 discovery + academic search (query planner, Semantic Scholar/Crossref/arXiv/OpenAlex/SERP/web-crawl adapters, dedup, snowball, full-text resolver, orchestrator integration) merged via PR #9. Phase 4 screening + structured extraction (criteria schema, source ranker, markdownify, PDF conversion, structured extractor, citation parsing, conflict detection, orchestrator integration) is in PR #10. Phase 5 (adversarial verification) is next. The master plan lives in [`docs/plan/master_plan.md`](docs/plan/master_plan.md).

## What it does

1. Accepts a research request from your main AI.
2. Plans, discovers, screens, extracts, and challenges sources using local models (Ollama/Gemma/etc.).
3. Adversarially verifies every insight so hallucinated claims never reach the main AI.
4. Reports progress %, ETA, current stage, and remaining steps on demand.
5. Delivers a Markdown insight brief with numbered claims, source links, and confidence labels.
6. **Never gives up on a blocker:** if the main AI says "I can't find…" or hits a missing resource, the engine runs an unblocking research campaign and returns actionable solutions with sources, access terms, and next steps.
7. Cleans up caches and duplicates at the end of every session, then opens a GitHub PR.

## Project norms

- **Model-agnostic:** every LLM interface goes through a provider abstraction; swap models in `config/models.yaml`.
- **Local-first:** primitive local AI drives the bulk of the work; frontier models only audit and synthesize.
- **Adversarial by default:** a `Devil` agent challenges every claim, and a `Verifier` re-runs source lookups.
- **Self-improving routers:** `.claude/agents/*-router.md` use learned routes (`R###` itemized deltas) with non-self-poisoning memory.
- **Ethical hard floor:** only public or authorized sources; robots.txt, rate limits, and SSRF policy are enforced. No credential bypass, no access-control evasion, no law breaking.
- **Elite organization:** no dead files, no dead branches; every session ends with a PR.

## Quick start (when implemented)

```powershell
# Install
pip install -e .

# Run a campaign
research-engine run "What are the latest methodological improvements in LLM systematic literature reviews?"

# Check status
research-engine status <campaign-id>
```

## Repository

- GitHub: `https://github.com/isaac233/Research-Engine`

## License

MIT
