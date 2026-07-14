# HANDOFF — 2026-07-14

## ⛔ BLOCKER (2026-07-14) — Ollama local runner missing; measurement impossible until reinstall

**Phase 3.2 (page-bound evidence extraction) is BUILT + committed + unit-green (`9fb15ce`)** — the pinned next build. But it **cannot be measured**: the local Ollama install is broken.

**Diagnosis (airtight):** every local-model call returns `500` from `/api/chat` with `error starting llama-server: llama-server binary not found`. The runner tree `…/Programs/Ollama/lib/ollama/` (holding `llama-server.exe` + GPU backend DLLs, modified Jul 13) is **gone** — `lib/` now contains only `Ollama.lnk`. The `.exe` launchers (Jul 8) survive and `ollama serve` runs, so `/api/tags` lists models and **`:cloud` models still work** (they route to Ollama Cloud, no local binary) — which is why the kimi *judge* ran but every *engine* stage (screening scorer, extraction, synth, writer) 500s. Result: screening scorer raises on all candidates → all rejected → `screening_yielded_zero` → empty briefs → bench scored 0/3. Two N=3 runs void (archived `bench/out/void_20260714_noenv/`, `bench/out/prev_20260714_phase32/`).

**FIX (user action — reinstall restores the runner):** download latest `OllamaSetup.exe` from ollama.com/download and run it (in-place repair, keeps pulled models in `~/.ollama`). Then verify: `curl -s http://localhost:11434/api/chat -d '{"model":"gemma4:12b","messages":[{"role":"user","content":"say 4"}],"stream":false}'` returns content, not a 500. THEN re-run the Phase 3.2 measurement below.

**Re-run cmd (env INLINE — `export … && nohup &` did NOT propagate the SERP endpoint; that void'd the first run):**
```
podman machine start && (cd ../search-infra && podman-compose up -d searxng whoogle)
# purge serp cache rows + archive bench/out/*.jsonl first
PYTHONUNBUFFERED=1 RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json' RESEARCH_ENGINE_WRITER=attribute_first \
  python -m research_engine.main bench --tasks 3 --language en --judge ollama --judge-model kimi-k2.7-code:cloud
```
**Gate (plan Task 1.0/3.2):** FACT c_acc ≥ 40% (baseline 20%). Then wire Planner (Phase 3.3).

---

## ⏭️ NEXT SESSION — START HERE

**Goal (user's finish line):** local-model (gemma4/qwen) engine BEATS Opus on DeepResearch Bench. **Proven achievable** — WebWeaver on Qwen3-30B-A3B (local MoE) scores RACE 46.77 > Claude 40.67; architecture hits 93% citation accuracy. Full evidence + architecture: `docs/plan/finish_line_research.md`. Granular 6-phase build plan: `docs/plan/finish_line_plan.md`.

**Trustworthy baseline (kimi judge):** RACE 21.48 / FACT 20.4% vs Claude 40.67 / 93.68%. Gap is ARCHITECTURAL (quality slider gave no lift). Measure everything with `kimi-k2.7-code:cloud` (the ONLY trustworthy judge; local mistral is a mirage). Bench cmd: `research-engine bench --tasks N --judge ollama --judge-model kimi-k2.7-code:cloud`.

**Where we stopped:** Phase 1.0 spike CONCLUSIVE (below). Attribute-first citation mechanism validated (67% where spans aligned); root cause of low FACT pinned = **evidence spans not bound to their cited URL**. Committed, tested primitives (default-off flag `RESEARCH_ENGINE_WRITER=attribute_first`): `memory/evidence_bank.py`, `synthesis/attribute_writer.py`, `synthesis/verify_citations.py` — reuse these.

**THE NEXT BUILD (do this first):** **page-bound evidence extraction** (plan Phase 3.2). Fetch a specific page → extract verbatim spans FROM that fetch → bank each span WITH that exact URL. Then verify-before-cite passes by construction. After that: Planner ReAct loop (search/write_outline/terminate) + Writer (retrieve/write, section-by-section) + grammar-constrained decoding (plan Phase 2). Then 10-task kimi sweep for DoD (RACE > 40.67 AND FACT > ~90%).

**Session ops:** `podman machine start` → `cd beta/search-infra && podman-compose up -d searxng whoogle` (sibling of repo; use `podman-compose` pip pkg) → `export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'`. Archive `bench/out/*.jsonl` + purge `data/cache.db` serp rows before each measure. Ollama Cloud signed in (kimi/deepseek `:cloud` models work via localhost:11434).

---

## Phase 1.0 spike — CONCLUSIVE: mechanism sound, needs page-bound evidence (2026-07-13, v4 commit 2134bef)

**v4 (quote-tight writer + verify-before-cite) settled it.** verify-before-cite re-fetches each span's URL the FACT way and strips any citation whose verbatim span is not on the page. Result: it stripped nearly EVERY citation (t51 0/0, t52 1/4, t53 0/0; FACT 8%). This is the working primitive doing its job and exposing the ROOT CAUSE: **the engine's evidence spans are not bound to the URL they are cited to.** Spans are mined from `paper.abstract`, but that is NOT the live content of `paper.url` (what gets cited and what FACT re-fetches) — they are disconnected, so spans don't re-verify on their cited page.

**Conclusion (4 spike runs):** attribute-first is sound (t51 v1 verbatim claim-spans = 67%); verify-before-cite is a correct honesty primitive to KEEP; the mandatory fix is **page-bound evidence extraction** — fetch a specific page, extract verbatim spans FROM that fetch, bank each span WITH that exact URL (the plan's Phase 3.2 two-stage URL→page→span→bank). No reuse-existing-spans shortcut works because the current extraction doesn't bind span↔URL. This is NOT a spike tweak; it is the real Planner build. Spike primitives (EvidenceBank, AttributeFirstWriter, verify_citations) are committed behind `RESEARCH_ENGINE_WRITER=attribute_first` (default off; legacy synth path unchanged) and are the reusable foundation for that build. **Next: build page-bound evidence extraction per `docs/plan/finish_line_plan.md` Phase 3.2, then the Planner/Writer.**

## Phase 1.0 falsification spike — earlier attempts + diagnosis (2026-07-13, commits 594258d/6e79eeb/397bcfd)

Built the attribute-first writer + Evidence Bank spike (`RESEARCH_ENGINE_WRITER=attribute_first`). Gate = FACT c_acc ≥ 40% on 3-task kimi. **Did not pass; 3 honest attempts, declining:**
- v1 claims-only (verbatim `claims[].evidence` spans): overall 22%, but **t51 = 2/3 = 67%** (up from 50% baseline) — verbatim spans verify. t52/t53 = empty bank (finance pages yield no structured claims) → 0 cites.
- v2 + summary-field spans (results_summary/conclusions): FACT 17.6% — paraphrased summaries DON'T re-verify (t51 crashed 67%→8%).
- v3 + verbatim page-spans from `paper.abstract`, query-ranked: FACT 8.1%.

**Diagnosis (from reading t51 v3's delivered brief):** three concrete leaks — (1) **writer distortion**: local synth model expands spans into fluent claims not literally on the page (not true attribute-first); (2) **bad citable URLs**: `_citable_url`'s "not .pdf/not doi.org ⇒ verifiable" heuristic trusted a paywalled `igi-global.com/viewtitle.aspx` stub → 6 citations to one unverifiable page; (3) coverage additions multiplied cites against unverifiable sources, dragging the ratio down.

**Verdict:** direction validated (verbatim claim-spans → 67% on the one HTML-rich task), naive implementation leaks. Real fix = a proper build, not a spike tweak: **(a) verify-before-cite** — re-fetch each span's URL the FACT way, keep the span only if its verbatim text is found on the page (auto-drops paywalled stubs, guarantees every cite verifies); **(b) quote-tight writer** — delivered sentence must track the verbatim span; **(c) real readability gate** (fetch+check, not URL-suffix); needs **grammar-constrained decoding** (plan Phase 2) so the local writer stops distorting. Spike code is committed behind the flag (default off — legacy synth path unchanged). Next: build the corrected Phase 1 per `docs/plan/finish_line_plan.md`.

## TRUSTWORTHY BASELINE established — kimi judge (2026-07-13 PM)

**Judge unblocked:** user's Ollama Cloud key → judge = **`kimi-k2.7-code:cloud`** (the real tag; no plain `kimi-k2.7:cloud` — see [[kimi-judge-tag]] / memory). Returns clean JSON (`think=false`). Replaces the degenerate local mistral (which reported a mirage RACE 52.82).

**First trustworthy number (3 en tasks, kimi judge, enricher + safe guard active):**
| | RACE Overall | Comp | Depth | Inst | Read | FACT C.Acc | E.Cit |
|---|---|---|---|---|---|---|---|
| **Research Engine** | **21.48** | 19.89 | 17.97 | 23.01 | 30.71 | **20.37%** | 1.33 |
| Claude-3.7 w/Search (bar) | 40.67 | 38.99 | 37.66 | 45.77 | 41.46 | 93.68% | 32.48 |

Per task: t51 RACE 15.0 / FACT 2-of-4 (50%); t52 25.8 / 0-of-6 (0%); t53 23.7 / 2-of-18 (11%). Differentiated, non-degenerate → trustworthy.

**HONEST STATE:** the engine is **~half** Claude-3.7's RACE and **~1/5** its citation accuracy. Beating Opus is a large, multi-lever gap, NOT one session. Weakest RACE dims = Depth (18) + Comprehensiveness (20); best = Readability (31). FACT is the biggest gap (20 vs 94). **This is the real starting line** — the mistral 52.82 was judge inflation, now exposed (the anti-cover-up working as designed). Roadmap levers: (1) FACT — cite HTML-verifiable pages + tighter claim↔source binding (raises c_acc + e_cit); (2) Depth/Comp — more sources + deeper synthesis (quality slider → bigger synth lane, higher volume); (3) re-measure every change with `--judge ollama --judge-model kimi-k2.7-code:cloud`.

## Lever results — what moved the benchmark and what didn't (2026-07-13 PM, kimi judge, N=3 en)

| Run | RACE | FACT c_acc | commit |
|---|---|---|---|
| baseline (default quality) | 21.48 | 20.4% | enricher+guard |
| `--quality 1.0` (best 7-lane models) | 19.78 | 19.2% | — |
| synth-specificity + conservative guard + 3500-tok briefs | 21.17 | 13.8% | `a388367` |
| **Claude-3.7 w/Search (bar)** | **40.67** | **93.68%** | — |

**Honest conclusion: no session-scale lever closed the gap.** Engine is pinned at RACE ~21 / FACT ~15-20% across every config. At N=3 the ±3-pt moves are noise. Two findings worth keeping:
- **The quality slider does NOT improve the benchmark** — bigger models per lane gave flat/worse RACE+FACT. The bottleneck is structural (discovery breadth, report comprehensiveness, per-sentence citation binding), not model size. Important negative result about the Prompt-2 investment.
- **Local-model synthesis is the ceiling**: it writes reports ~half as comprehensive as the reference and citations that mostly don't verify. Specific-claim prompting + longer budget did not fix it at N=3.

**Roadmap to actually beat the bar (multi-session, structural):** (1) **Discovery breadth+depth** — more relevant sources per task (the reference reports draw on many); current campaigns deliver ~5-9 sources. (2) **Per-sentence retrieval-grounded synthesis** — bind each sentence to the exact source span (RAG-style), not free-form synth then post-hoc guard; this is the only reliable path to Claude's 93.68% c_acc. (3) **Cite HTML-verifiable pages** — the FACT verifier can't read PDFs/DOIs; prefer/relabel citations to the readable landing page. (4) **Longer multi-pass reports** for RACE Comp/Depth. (5) **Always measure with `--judge ollama --judge-model kimi-k2.7-code:cloud`** at N>=10 to beat the noise floor. What NOT to repeat: the lexical/word-overlap grounding (proven harmful), the quality slider as a benchmark lever (no effect).

## "Beat Opus" grind — honest findings (2026-07-13 PM, commits `e2274a1`, `8962181`, `0d7aef9`)

**Goal reframed by user:** finish = accomplish the Prompt-1 vision — gemma4-class local models drive the whole campaign and deliver **better insights than Opus**, measured by the DeepResearch Bench scoreboard vs the Claude-3.7-Sonnet-w/Search bar (RACE 40.67 / FACT c_acc **93.68%** / e_cit 32).

**What shipped (all tested green, mypy+ruff clean):**
1. **Snippet enricher** (`e2274a1`) — thin web snippets (<300 char) replaced with capped page-text excerpts before SCREEN. Real web sources now reach screening.
2. **Citation grounding** (`8962181` + `0d7aef9`) — post-synthesis guard that strips `[n]` a source doesn't support. **The re-fetch-based variant was built, measured, and REMOVED**: on an isolated A/B (same article, same judge) it *helped* task 51 (12%→22%) but *hurt* task 52 (16%→7%, dropped 3 of 4 genuinely-supported HTML citations) — lexical overlap on re-fetched page boilerplate ≠ semantic support. Kept only the conservative same-source anti-hallucination guard (checks a claim against its OWN extract); it keeps unreadable/PDF/DOI citations (can't disprove → don't hide a real source) and a floor prevents stripping every citation.

**THE BLOCKER (why a certified win can't be produced autonomously):** the measurement instrument is untrustworthy. Local **mistral judge** returns **degenerate RACE** (identical 52.82 across three different runs) and **non-reproducible FACT** (same task 51 read 12% / 36% / 50% across passes). No frontier judge is available in-repo: `API_KEYS.MD` holds only financial-data keys (no ANTHROPIC/GEMINI/OPENAI), `gemini` CLI is unauthenticated, ollama is local-only. **Certifying "beats Opus" needs a trustworthy judge = a user-provided `GEMINI_API_KEY` (free, AI Studio) or `ANTHROPIC_API_KEY`, plus a 10-20 task sweep.**

**Structural verdict (honest):** the *vision* is demonstrably working — local models run discovery→full-text extraction→grounded synthesis and deliver citation-rich briefs from real web sources (task 51: Carnegie/WHO/PMC/UNDP/nippon; task 52: 7 HTML finance sources). The specific FACT **93.68%** number is NOT yet hit: the engine cites PDFs/DOIs the FACT verifier can't re-read (auto-fail) and local-model synthesis mis-attributes some claims. **Next real lever (not done): bias discovery + citation to HTML-verifiable pages and use an LLM (not lexical) claim↔source alignment — then measure with a real judge.** Infra note: SearXNG web lane confirmed live this session (`beta/search-infra`, sibling of the repo, Podman).

## Snippet enrichment — next lever DONE (2026-07-13, commit `e2274a1`, branch `feat/deepresearch-bench`)

**The HANDOFF's top-ranked remaining lever is shipped.** "Resolver full-text fetch for web URLs pre-screening (snippet→page text)" is now `src/research_engine/screening/enricher.py::enrich_snippets`. A red TDD test (`tests/unit/screening/test_enricher.py`, was untracked/unbuilt) drove it green (7/7).

- Fetches the page for thin **web** sources (`serp`/`web_crawl`/`web`) whose abstract is <300 chars (`SNIPPET_TEXT_CHARS`), replaces the snippet with a capped `markdownify` page excerpt (default 2000 chars), preserves the original snippet in `meta["snippet"]`, flags `meta["enriched_from_page"]`. Immutable (`dataclasses.replace`), `URLPolicy`-gated (blocks link-local/private before fetch), `max_fetches`-capped (default 8), non-fatal on fetch failure, academic sources untouched.
- Wired into `orchestrator._run_screen`: enriches before `ranker.rank` when a browser is present (`self.browser.fetch_bytes`). So the relevance rubric + extraction now see real page text, not a 150-char snippet.
- **Verified:** full unit suite green (`pytest -q --no-cov`), mypy clean, ruff clean.
- **NOT exercised live** — the enricher's path only fires on the web/serp lane, which needs the Podman+SearXNG stack up (per-session manual, see below). Unit-proven; a live bench run with the stack up is the confirmation.

## Finish-line status (2026-07-13) — user chose STOP HERE

Branch `feat/deepresearch-bench` is **47 commits ahead of `main`** (v0.1.0). It subsumes PR #17's 7-lane full-text work + benchmark scoreboard + Track B + web lane + this enricher. All green. Local ~3 commits ahead of origin (**unpushed**; no PR to main).

**The finite objectives (v0.1.0 DoD, the 7-lane prompt-2 spec) are met.** What remains is not finite code work — it forks into (a) **release**: push branch → PR → merge → tag v0.2.0 (irreversible; user-gated), and (b) **benchmark grind** ("beat Opus"): open-ended, needs the stack up + `gemini` auth for trustworthy numbers. User elected to defer both. Next session: pick a fork. Remaining ranked levers if grinding: authenticated `--judge gemini` run; `--tasks 20` sweep; task-52-class FACT variance (fetch result pages before support judging). LLM query planner still heuristic (low value).

## Snippet-rubric calibration — lever 1 DONE (2026-07-09 night, commit `8ce0309`)

**The task-51 blocker is fixed.** Web snippets (~150 chars) can never "directly address" a query, so the strict relevance rubric MUST-failed every good web source. New `LLMRubricCriterion.snippet_prompt`: when source text is snippet-thin (<300 chars, `SNIPPET_TEXT_CHARS` in ranker.py), the rubric judges **topic match** of title+snippet instead of answer completeness. Still 1-5, still MUST — off-topic floodgate stays closed (test-guarded). Also neutralized scorer labels (Title/Text, "research sources" system prompt — the old "academic papers"/"Abstract:" framing biased against web results).

**Measured (2 en tasks, ollama judge, fresh caches):** RACE 52.82 (~flat, within judge noise) | **FACT c.acc 50.0%** (was 33.3), e.cit total 8 (was 6).
- Task 51 (Japan demographics): **0 → 5/8 supported citations (62.5%)**, 6 real web sources included (Carnegie, WHO, UNDP, AARP, EU-Japan report) — exactly the ones previously rejected. RACE stuck at 40.5: known mistral-judge coarseness (identical grids), treat directional.
- Task 52 (Buffett/Munger/Duan): RACE 65.1, FACT 3/8 (was 6/9 — run variance; different serp results each run).

**Remaining levers, ranked:** (1) resolver full-text fetch for web URLs pre-screening (snippet→page text, makes rubric + extraction stronger); (2) authenticated `--judge gemini` run for trustworthy numbers; (3) `--tasks 20` sweep; (4) task-52-class FACT variance — consider fetching result pages before support judging.

**Session ops reminder:** `podman machine start` → `cd beta/search-infra && podman-compose up -d searxng whoogle` (pip `podman-compose`, NOT `podman compose`); export `RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'`; archive `bench/out/*.jsonl` before re-measuring (resume caches). Old runs parked in `bench/out/prev_20260709/`.

## Web lane LIVE + FACT>0 (2026-07-09 evening, branch `feat/deepresearch-bench`, commits `2d54dbe`, `2f8f5c9`, `2752d84`)

**Container stack + loop closed.** `beta/search-infra`: `searxng` + `whoogle` containers running (websurfx/yacy skipped — flaky image / empty index). SearXNG JSON verified at `http://localhost:8080/search?q={query}&format=json`. Bench invocation: `export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'` then `python -m research_engine.main bench --tasks 2 --judge ollama`.

**Container engine = PODMAN (switched from Docker Desktop 2026-07-09).** Podman 5.8.3 + Podman Desktop, own WSL2 VM (`podman-machine-default`), no license tier/login. Same compose file, verified byte-identical SearXNG/SERPAdapter behavior. **Per session:** `podman machine start` (or Podman Desktop auto-start), then `cd beta/search-infra && podman-compose up -d searxng whoogle`. **Use `podman-compose` (pip pkg), NOT `podman compose`** — the built-in subcommand silently borrows Docker's `docker-compose.exe` if present. Docker Desktop being uninstalled; engine is container-agnostic (only needs the localhost:8080 HTTP endpoint). Full setup in `beta/search-infra/README.md`.

**Three real bugs found only by running live (each TDD-fixed, suite+mypy+ruff green):**
1. **SSRF policy blocked the local endpoint** (`2d54dbe`): localhost + non-80/443 ports rejected before the allow-list could apply, and `ssrf_guard` DNS-pinned everything to public IPs. New `URLPolicy(trusted_origins=[...])` — exact (scheme,host,port) from operator's endpoint config; bypasses localhost/port/DNS-pinning gates only, never scheme/credential checks; SERPAdapter endpoint calls also skip robots.txt (SearXNG ships `Disallow: /*?*q=*` for external crawlers — meaningless for the operator's own instance). Result-URL fetches stay fully gated.
2. **Benchmark leakage** (`2f8f5c9`): web-searching the verbatim task prompt returned pages republishing the benchmark's own dataset/reference reports (huggingface datasets page, `research-hb.zhipuai-infra.cn/samples/...`) — and they beat real sources on the relevance rubric (verbatim match → 5/5). New `RESEARCH_ENGINE_SERP_BLOCKLIST` (comma-separated URL substrings) filtered in SERPAdapter; bench runner sets a default leakage blocklist. **Purge `data/cache.db` serp rows when changing the blocklist** — cached results bypass the adapter filter.
3. **Brotli corruption** (`2752d84`): fingerprint headers advertise `Accept-Encoding: br` but the decoder wasn't installed — httpx silently returned raw brotli bytes and ssrf_guard strips Content-Encoding, hiding it. Every br-served page (tikr, substack) was garbage for extraction AND for FACT support checks. Dep now `httpx[brotli]`.
   Also: scorecard reasons printed the CLAMPED rubric score (everything below minimum displayed as "3.0 vs minimum 3.0") — now prints the raw score.

**RESULT (2 en tasks, ollama judge, directional):** RACE overall **52.96** (was 40.5; 50 = ties reference) | FACT c.acc **33.3%**, eff.cit 6 (was 0 / 0).
- Task 52 (Buffett/Munger/Duan): 0 included → **6 real web sources** (tikr/gainify/yahoo/llmquant), RACE 65.4, FACT 6/9 supported (67%).
- Task 51 (Japan demographics): unchanged 40.5, 1 source. Web lane found excellent sources (Carnegie, WHO, UNDP, EU-Japan consumer report) but **screening rejects them: raw relevance <3 on the strict "directly addresses" rubric** while snippet-thin. THE next lever: relevance-rubric calibration for web snippets (score topical relevance of title+snippet; don't demand the full answer in a 150-char snippet). Careful: don't re-open the off-topic floodgate Track B closed.

**Next levers, ranked:** (1) rubric calibration above → task-51-class breadth; (2) resolver full-text fetch for web URLs pre-screening (snippet→page text makes rubric fair); (3) authenticated `--judge gemini` run for trustworthy numbers; (4) `--tasks 20` sweep.

## Track B — discovery relevance + citation grounding (2026-07-09, branch `feat/deepresearch-bench`, commits `327a39f` + `1531516`)

**What was built (all TDD, mypy strict + ruff green, full unit suite green):**

*Option 2 — discovery relevance:*
- **Relevance rubric was blind**: the default prompt had no `{query}` placeholder, so `format(query=...)` was a no-op — the LLM scored papers without ever seeing the research query. Fixed; rubric is now a MUST gate.
- **Rubric was unfailable**: `clamped = max(minimum_score, ...)` floored every low score up to passing. Pass/fail now uses the raw score.
- No-LLM environments pass rubrics unchecked (offline CI safe); scorer errors fail visibly.
- Query planner skips arXiv for non-STEM queries (keyword-term heuristic; screening's LLM gate is the backstop).
- `has_full_text` demoted MUST→SHOULD (it excluded every crossref/openalex record wholesale); new `has_abstract` SHOULD (w=2.0) and **`readable` MUST** (abstract OR full text — a relevant-sounding title-only stub cannot be extracted or cited).
- **OpenAlex abstracts were always empty**: adapter read `raw["abstract"]`, which the API never sends; now rebuilds text from `abstract_inverted_index` (live: 7/10 papers gained abstracts).
- New honesty flag `screening_yielded_offtopic` (≥50% of candidates fail relevance) beside `screening_yielded_zero`.

*Option 3 — citation grounding:*
- Synthesizer renders per-source URLs, instructs inline `[n]` citations, and code-appends a deterministic `## References` section (URL-less sources listed so `[n]` never dangles). Reporter fallback same.
- `drop_failed_claims`: Verifier-rejected claims are stripped before synthesis — unverified claims never ship.
- `unique_insight_filter` keeps abstract-only sources that have content but 0 structured claims (they were silently dropped, collapsing briefs to 1 source).

**Measured (1 en task, ollama judge, N=1 directional):** RACE 40.5 (unchanged), FACT extraction now finds (fact,url) pairs (0→2) but 0 supported — the single on-topic readable source is a paywalled IGI DOI the judge cannot verify. **Sources are now on-topic** (was: gravitational-wave papers for a Japan-demographics query; now: population-aging economics).

**UPDATE (2026-07-09, commit `f9aae42`): web lane now CODE-WIRED.** `SERPAdapter` parses SearXNG JSON (HTML fallback kept); `EngineConfig.serp_endpoint` reads `RESEARCH_ENGINE_SERP_ENDPOINT`; when set, `main.py` enables the `serp` source + planner emits a web query. A shared self-hosted stack lives at `beta/search-infra/` (SearXNG/Whoogle/Websurfx/YaCy compose + `search_router.py`). **Not yet exercised live** — Docker Desktop is not installed on this machine. To close the loop and prove FACT>0: install Docker, `cd beta/search-infra && docker compose up -d`, `set RESEARCH_ENGINE_SERP_ENDPOINT=http://localhost:8080/search?q={query}&format=json`, then re-run the bench. That is the remaining step of the finding below.

**THE structural finding (next session's target):** DeepResearch Bench tasks are general web-research questions. For task 51 (Japan elderly market) only 1/30 academic candidates was both relevant and readable; for task 52 (Buffett/Munger investment philosophies) 0/21 — the engine honestly delivered nothing (`screening_yielded_zero` + `_offtopic` both fired; the anti-cover-up works). Academic APIs are the wrong lane for these tasks. **The engine needs the web discovery lane live**: `SERPAdapter` exists but requires a configured endpoint (SearXNG instance or paid API) — none configured. Wiring a SearXNG endpoint (or serper.dev key) + enabling `serp`/`web_crawl` in the planner for non-academic topics is the single highest-value next move for both RACE breadth and FACT (web sources are fetchable, unlike paywalled DOIs).

**Bench gotchas learned:** `bench/out/engine.jsonl` is a resume cache — a re-run with the file present re-scores the OLD article (delete/move it to re-measure after engine changes). The local mistral judge at temp=0 can emit identical RACE grids for different mediocre articles — treat as coarse/directional only.

## DeepResearch Bench scoreboard — Track A (2026-07-09, branch `feat/deepresearch-bench`)

**Why:** the engine had never been scored against any external benchmark or against Opus — "hasn't beaten Opus" was a feeling, not a number. Built the apples-to-apples scoreboard first (measure before upgrading), per the approved plan `C:\Users\Isaac\.claude\plans\lexical-bubbling-starfish.md`.

- **Ported DeepResearch Bench** (arXiv:2506.11763, Apache-2.0) into a new top-level `bench/` package: **RACE** (report quality vs a vendored reference report, 4 weighted dims, 0-100 where 50 = ties reference) + **FACT** (extract cited (fact,url) pairs → fetch via the engine's own `raw_http`+`markdownify` → judge support → citation accuracy + effective citations).
- **Vendored** `bench/data/{query,criteria,reference}.jsonl` (100 tasks / criteria / reference reports) + `LICENSE.md` provenance.
- **Model-agnostic judge**: new `src/research_engine/llm/gemini_cli_client.py` (shells to `gemini -p`, stdin for bulk, auth-error surfaced) + `bench/judge.py build_judge(gemini|ollama|anthropic)`. Registered `gemini` in `model_registry`.
- **CLI**: `research-engine bench --tasks N --judge {gemini|ollama|anthropic} [--reuse-engine --quality]` → writes `Research/benchmarks/<date>_scorecard.MD` (engine row vs published Opus/Gemini/OpenAI bar in `bench/leaderboard.py`, flags weakest dimension = Track B target).
- **Verified:** 22 new bench unit tests + full unit suite green (EXIT=0); mypy strict clean (87 files); ruff clean. RACE math + scorecard render verified with a fake judge.
- **Judge availability in this env:** Gemini CLI + MCP are NOT authenticated (no key/oauth; MCP `spawn EINVAL`). Ollama IS up (gemma4:31b, mistral-small3.2, qwen3.6-27b) — used as the offline validation judge. For the closest-to-official number the user must authenticate `gemini` once (or set `GEMINI_API_KEY`) and run `--judge gemini`.
- **TLS note:** corporate cert revocation blocks `curl`; used `--ssl-no-revoke` to vendor data (engine itself already fixed via truststore).

### FIRST REAL SCORECARD (1 en task, local mistral-small judge — directional, N=1)
`Research/benchmarks/2026-07-09_scorecard.MD`:

| | RACE Overall | Comp | Depth | Inst | Read | FACT C.Acc | E.Cit |
|---|---|---|---|---|---|---|---|
| **Research Engine** | **40.52** | 42.86 | 37.78 | 41.50 | 40.15 | **0.00** | **0** |
| Claude-3.7-Sonnet w/Search | 40.67 | 38.99 | 37.66 | 45.77 | 41.46 | 93.68 | 32 |
| OpenAI Deep Research | 46.98 | 46.87 | 45.25 | 49.27 | 47.14 | 77.96 | 41 |

**What the scoreboard exposed on run one (the whole point of measuring):**
1. **FACT = 0.** The delivered brief had **zero citations** (0 URLs, 0 `[n]` refs). The engine reads full text but does not ground claims to sources in the deliverable — the vision's "citation-rich report" is measurably absent.
2. **Off-topic sources.** Task = "elderly demographic market size in Japan 2020-2050"; the engine returned **particle-physics / gravitational-wave arXiv papers** ($B^0_s$ decay, CMS/LHCb). Discovery has an arXiv/physics bias and failed relevance for a demographics query.
3. **RACE ~40 is judge-inflated.** A lenient local judge scored fluent-but-off-topic prose near Claude's level. FACT + a stronger judge (Gemini) expose what RACE alone hides. Without the scoreboard this run reads "campaign completed, Insights.MD delivered" — a green check over an ungrounded, off-topic result. That is the exact cover-up failure the project fears, now visible.

### CHOSEN TRACK B WORK (user picked both, 2026-07-09) — build next, then re-measure
- **Option 2 — Discovery relevance (biggest gap).** Off-topic sources are the #1 problem. The query planner + source registry over-weight arXiv and don't filter for topical relevance, so a demographics/market query pulled physics papers. Fixes: (a) relevance gate in screening that scores paper-vs-query semantic match and drops off-topic sources (reuse `screening/ranker.py` + a local-LLM relevance criterion in `screening/criteria.py`); (b) query planner should pick sources by topic (OpenAlex/Crossref/web for non-CS topics, not arXiv-first) in `discovery/query_planner.py` + `discovery/source_registry.py`; (c) add a "screening_yielded_offtopic" honesty flag like the existing `screening_yielded_zero`. Target metric: on-topic sources -> RACE Comp/Depth up.
- **Option 3 — In-pipeline citation grounding (FACT 0 -> real).** Every delivered claim must carry a verified statement->source-URL span; unsupported claims dropped/flagged before DELIVER. Fixes: the synthesizer (`synthesis/synthesizer.py`) + reporter (`evaluation/reporter.py`) must emit inline citations (`[n]` + a reference list with URLs) from `ExtractedSource.citations`/paper URLs, and the adversarial `Verifier` (`adversarial/verifier.py`) already checks quote/URL presence — wire its pass/fail so uncited claims don't ship. Reuse the bench `FactScorer` logic as the in-loop grounding check. Target metric: FACT C.Acc 0 -> competitive; E.Cit > 0.

**Verify each with the scoreboard:** after a change, run `research-engine bench --tasks 5 --judge ollama --reuse-engine` (re-score) or without `--reuse-engine` (fresh campaigns), and diff the scorecard. Authenticate `gemini` for a trustworthy multi-task number: `research-engine bench --tasks 20 --judge gemini`.

**Files added this session (branch `feat/deepresearch-bench`):** `bench/` (package + `data/{query,criteria,reference}.jsonl` + `LICENSE.md`), `src/research_engine/llm/gemini_cli_client.py`, `bench` command in `main.py`, gemini branch in `model_registry.py`, `tests/unit/bench/` (22 tests), `docs/architecture/benchmark.md`. Approved plan: `C:\Users\Isaac\.claude\plans\lexical-bubbling-starfish.md`.

## PUSHED — PR #17 open (2026-07-08)
Branch `feat/llm-fulltext-lanes` (29 commits) pushed to origin; **PR #17**: https://github.com/isaac233/Research-Engine/pull/17 (base `main`). Covers golden-eval + anti-poison + self-improvement loops + the full LLM-fulltext 7-lane upgrade (Phases 0-6) + audit TLS/gzip fixes. ~395 tests green, mypy+ruff clean, live campaign verified.

## Whole-Project Audit + "does it actually research?" — 2026-07-08

Audited cohesion/organization/consistency-with-both-prompts and — critically — ran a REAL end-to-end campaign. Found and fixed TWO blockers that made real research impossible; the engine now genuinely performs research.

- **Structure:** clean, domain-organized, no orphan files (only `_run_stub` remains as a safety default; its "future subsystems" comment is now stale — all stages implemented).
- **BLOCKER 1 (TLS) — fixed (`15a5929`):** every HTTPS source failed with CERTIFICATE_VERIFY_FAILED (corporate TLS-inspection root CA absent from certifi). `src/research_engine/__init__.py` now injects `truststore` at import → all httpx/urllib use the OS trust store. Added truststore dependency.
- **BLOCKER 2 (gzip) — fixed (`15a5929`):** crossref/openalex failed "incorrect header check" — `ssrf_guard.safe_request` rebuilt the response with decompressed body but kept `Content-Encoding: gzip` → double-decode. Now strips content-encoding/length on the reconstructed response.
- **PROOF IT WORKS:** live campaign `run "efficient routing in sparse mixture-of-experts models" --sources 3 --quality 0.5` completed end-to-end and delivered `Research/.../*_Insights.MD` with 3 REAL arXiv papers, real quantitative results (e.g. within/across routing similarity 0.8435±0.0879, Cohen's d 1.44), method + data + **replication steps** per source, a source's GitHub code repo, and cross-source synthesis. gemma4:12b (extract) + Mistral-Small (synth) ran on GPU. This is the vision realized (full-text, replication-grade, local-model-driven).
- Discovery now: arxiv + crossref + openalex return papers; semantic_scholar 429s without an API key (graceful, handled). Multi-source works.
- FOLLOW-UP (minor): semantic_scholar needs an API key or backoff for reliability; clean the stale `_run_stub` comment.

## LLM Full-Text Extraction + 7-Lane Plan — 2026-07-08

**Why this work:** user observed the research phase was seconds long and the GPU never spiked. Root cause: the local LLM was **never wired into a run** (`_make_orchestrator` built `SourceRanker()`/`StructuredExtractor()` with no provider), and extraction was regex on abstract-level text — the exact "reads only abstracts, can't replicate" failure the project exists to kill. New spec in `Research Engine Prompt 2.txt`: 7 model lanes, quality/speed + volume sliders, constraint triangle, sequential VRAM load/unload, replication-grade full-text insight.

**Approved plan:** `C:\Users\Isaac\.claude\plans\jolly-wobbling-steele.md` (6 phases). Branch `feat/llm-fulltext-lanes` (cut from `feat/self-research-golden-eval`).

**DONE this session (Phase 0 + Phase 1, live-verified):**
- Phase 0 (`cc1dff2`, `b4fa9a2`): `config/model_lanes.yaml` (7 lanes w/ fallbacks) + `scripts/pull_models.py` (normalize HF tags, pull, record `data/model_pull_report.json`, degrade missing→installed fallback). **All 7 requested tags 404 as written** (`gemma4:12b/26b/31b`, `batiai/qwen3.6-35b:iq3`, etc. are speculative) → every lane currently falls back to an installed model (`gemma4:latest`, `mistral-small3.2:latest`, `qwen2.5-coder:14b`). A real pull is running in the BACKGROUND; check `data/model_pull_report.json` + `data/pull_models.log` next session for any tag that actually resolved.
- Phase 1 (`0849c2c`, `3948e05`): `extraction/llm_extractor.py::LLMSectionExtractor` (chunked map-reduce, defensive JSON parse, ABSENT handling, **verbatim-evidence substring guard** dropping hallucinated claims) + `extraction/chunker.py` + `extraction/prompts.py`. `StructuredExtractor` gained `llm_extractor`; uses LLM path on real full text, regex fallback otherwise, flags `meta.degraded=abstract_only`, sets `extraction_tool=llm:<model>`; added `conclusions`+`replication_notes`. `main.py::_make_orchestrator` wires deep lane via `ModelRegistry` with ping-guarded regex fallback (CI/offline safe).
- **Key fix (`3948e05`):** `gemma4` is a *thinking* model — with a bounded token budget it spent it all on hidden reasoning and returned EMPTY content. Set `think=false` by default on `OllamaClient`. Now clean JSON in ~2.5x fewer tokens.
- **Live acceptance PASSED:** `gemma4:latest` read full text → methodology/data/results/conclusions + 5 evidence-verified claims (0 hallucinated) in ~8s; `ollama ps` showed the model resident with 3.3 GB on the GPU. The GPU-driven full-text extraction the user wanted now works.
- Verification: all tests pass, mypy clean (75 files), ruff clean. New tests: `tests/unit/extraction/test_llm_extractor.py` (8, incl. anti-hallucination + abstract-only skip).

**Phase 2 DONE (`71e162d`), live-verified:**
- `llm/lane_roster.py::LaneRoster.from_yaml` (resolves effective tag from pull report); `llm/lifecycle.py::ModelLifecycleManager` (load/unload keep_alive=0, switch evicts old before loading new, `with_model` ctx-mgr evicts on error, `active()` via `/api/ps`, event hook). `ollama_client.py`: complete() options+keep_alive, `ps/warm/unload`. `model_registry.build_ollama_client()`. `validate-models` now prints a lane table.
- Live: load→switch→unload keeps exactly ONE model resident (no VRAM stacking). Tests added (roster + lifecycle).
- **ALL 7 lanes resolved to REAL models** (`be808af`, `validate-models` all ok): fast `gemma4:12b` (in-VRAM), deep `gemma4:12b` (in-VRAM; the aspirational `gemma4:26b-a4b` MoE does NOT exist, so deep uses 12b — user confirmed fine), overnight `gemma4:31b`, online_a `batiai/qwen3.6-27b:q3` (user-corrected tag), online_b `hf.co/unsloth/Qwen3.6-27B-GGUF:IQ4_XS`, synth_a `hf.co/lmstudio-community/Mistral-Small-3.2-24B-Instruct-2506-GGUF:Q4_K_M`, synth_b `hf.co/KikoCis/gemma-4-31b-it-IQ3_XS-GGUF:IQ3_XS`. Extra installed: `batiai/qwen3.6-35b:iq3` (unused spare).
- **Pull script hardened:** captures raw bytes (no text-mode) to survive ollama's ANSI progress on Windows cp1252; strips control chars from stored errors; incremental report writes. `_resolve_deep_model` in main.py reads the report → deep extraction now runs on gemma4:12b.

**Phase 3 DONE (`23c5cbb`), live-verified:**
- `monitoring/gpu_probe.py::GpuProbe.snapshot()` (nvidia-smi VRAM + `/api/ps` per-model RAM-offload split; None on CI). `telemetry.py`: `model_event`/`gpu_snapshot` + `lifecycle_telemetry_hook`. `orchestrator.status_snapshot` includes live `gpu` + per-stage `models`; `_run_extract` emits model assignment + extractor agent-history action (the deferred P1 item). `status` CLI prints `model[extract]`, VRAM, per-model offload %. Live: probe read 1779/16303 MiB.

**Phase 4 DONE (`dc1ca08`), live-verified:**
- `planning/constraint_triangle.py::solve` (2-of-3 derive 3rd; time governs→no slider→auto-optimize quality; <2 & no time→needs_slider; maps quality tier→per-stage lane assignment). `planning/quality_floor.py::QualityFloor.check` (goal/omission/fabrication). `cli/slider.py` (arrow-key via optional prompt_toolkit, numbered fallback, never hangs/aborts a run — non-TTY/EOF→balanced defaults). `main.py run`: `--quality/--time-budget/--sources`, persists `ResolvedPlan` to campaign meta, volume caps max_sources. `prompt_toolkit` added as optional `[tui]` extra.
- Live: `--time-budget 600`→quality auto 0.63 no slider; `--quality 0.9 --sources 5`→time 409s; bare→balanced default, no hang.
- NOTE: ResolvedPlan.lane_assignment is persisted to meta but stages don't yet READ it to pick lanes — that wiring is Phase 5 (with lifecycle.with_model + handoff docs).

**Phase 5 DONE (`eda41f4`):**
- `synthesis/synthesizer.py::Synthesizer` (deep reads → replication-grade brief via synth lane) + `unique_insight_filter` (drop dup-insight sources, cap at volume). `planning/handoff.py::HandoffDoc` (written on model switch). `main.py`: one Ollama provider drives all lanes — fast-lane `build_llm_scorer` into screening, deep lane into extraction, synth lane into Synthesizer; lane tags via LaneRoster+pull report; heuristic fallback when Ollama absent. `orchestrator`: synthesizer builds the brief (unique-insight sources) w/ reporter fallback + writes extract→evaluate handoff.
- 389 tests pass; mypy+ruff clean (86 files).
- STILL PARTIAL: `ModelLifecycleManager` (Phase 2) is NOT yet wired into the run loop — stages don't call `with_model`/`switch` to sequentially load per-`resolved_plan` lanes; each lane call currently relies on Ollama's own load/keep_alive. Full sequential VRAM handoff per quality-slider lane assignment is the main remaining integration (fold into P6 or a P5.1). Also: LLM query_planner still heuristic (optional, low priority).

**Phase 6 DONE (`44b0bea`) — ALL 6 PHASES COMPLETE:**
- Wired the Phase 2 lifecycle into the run loop (the gap): `orchestrator._switch_lane(stage)` loads the stage's `resolved_plan` lane model via LaneRoster, evicting the previous (one model resident, no VRAM stacking); emits switch telemetry; frees the model at FINALIZE. `main.py` builds ModelLifecycleManager + LaneRoster when Ollama reachable.
- `docs/architecture/model-lanes.md` documents the whole LLM-driven system. Security confirmed (paper text = data, agent-history summaries-only + redaction).
- 392 tests pass; mypy+ruff clean (86 files).

**LOW-PRIORITY REMAINING (optional, next sessions):**
- LLM query planner still heuristic (works fine; low value).
- Overnight/synth_b IQ3 lanes are configured but only used if the quality slider/plan assigns them; not yet exercised live end-to-end.
- Not pushed / no PR — user has not asked to push. Branch `feat/llm-fulltext-lanes` has Phases 0-6.
- Consider a live full campaign on a real OA-paper query at `--quality 0.9` to exercise the full multi-lane handoff path end-to-end (unit-tested; not yet run live as a single campaign).
- **Correct model tags:** user should supply real Ollama tags (or confirm the background-pull resolved ones) to replace the speculative lane tags; IQ3 lanes = synthesis/overnight only, never deep extraction.
- Env: RTX 5080 16GB VRAM + 64GB RAM. Ollama auto-offloads to RAM (no custom bridge). MoE tolerates offload; dense does not.

## This Session
- Done:
  - Read and parsed `Research Engine Prompt1.MD`.
  - Loaded reference/skills/catalog/agents per CLAUDE.md v12.
  - Researched current open-source patterns for research agents, browser automation, and multi-agent orchestration.
  - Used the `planner` agent to produce `docs/plan/master_plan.md`.
  - Created full project directory tree and Phase 0 scaffold (README, HANDOFF, .gitignore, pyproject.toml, routers, eval harness skeleton, GitHub templates).
  - Fixed `router_sim.py` keyword matching and added a load table to `research-engine-router.md` so all `.claude/router_eval/` self-checks pass.
  - Initialized GitHub repo `isaac233/Research-Engine`, opened Pull Request #1, merged it to `main`, and deleted the feature branch.
  - Amended `docs/plan/master_plan.md` to require a consuming-project `Research/` folder with per-campaign sub-folders and differentiated `<campaign>_Insights.MD` files plus an aggregated `Research/Insights.MD`; merged via PR #3.
  - Implemented Phase 1: core orchestrator + model-agnostic LLM layer.
    - `src/research_engine/state.py`: immutable `ResearchRequest`/`Campaign` dataclasses + SQLite append-only store.
    - `src/research_engine/events.py`: append-only event bus.
    - `src/research_engine/llm/`: `LLMProvider` ABC, `OllamaClient`, `AnthropicClient`, `ModelRegistry`.
    - `src/research_engine/orchestrator.py`: campaign lifecycle state machine with pause/resume/kill.
    - `src/research_engine/monitoring/telemetry.py`: sanitized stage telemetry.
    - `src/research_engine/main.py`: `research-engine run/status/pause/resume/kill` CLI.
    - `src/research_engine/config.py`: project path resolution (including `Research/` layout).
    - Tests: 21 unit/integration tests, 80% coverage.
  - Implemented Phase 2: AI-only browser subsystem.
    - `src/research_engine/browser/ai_browser.py`: `AIBrowser` ABC, `BrowserAction`, `BrowserResult`, `BrowserActionType` enum.
    - `src/research_engine/browser/cdp_driver.py`: Playwright/Chromium driver with policy + robots.txt guards.
    - `src/research_engine/browser/raw_http.py`: pooled httpx client with retries, backoff, jitter, header rotation.
    - `src/research_engine/browser/policy.py`: SSRF/ethical URL policy (private IP, localhost, file:// block).
    - `src/research_engine/browser/robots.py`: per-host robots.txt fetcher/cache.
    - `src/research_engine/browser/fingerprint.py`: legitimate header/viewport rotation.
    - `src/research_engine/browser/graphql_client.py`: GraphQL-aware POST helper.
    - `src/research_engine/browser/unblock_probe.py`: browser-based unblocking research probe; never reports "no solution" without an evidence log.
    - `src/research_engine/orchestrator.py`: blocker detection + unblocking campaign dispatch during discovery.
    - `src/research_engine/main.py`: wires `UnblockProbe` as the default browser.
    - Tests: 38 new browser unit tests, total 59 tests, 80% coverage.
  - Implemented Phase 3: discovery + academic search.
    - `src/research_engine/discovery/schema.py`: normalized `Paper`, `SourceQuery`, `SearchResult`, `DuplicateGroup`, `ResolveResult`, `DiscoveryResult` dataclasses.
    - `src/research_engine/discovery/query_planner.py`: decomposes a request into source-specific `SourceQuery` objects.
    - `src/research_engine/discovery/sources/base.py`: `SourceAdapter` ABC.
    - `src/research_engine/discovery/sources/semantic_scholar.py`, `crossref.py`, `arxiv.py`, `openalex.py`, `serp.py`, `web_crawl.py`: academic + web source adapters.
    - `src/research_engine/discovery/dedup.py`: DOI/URL exact match + title fuzzy deduplication with different-DOI guard.
    - `src/research_engine/discovery/snowball.py`: forward/backward citation expansion via source adapters.
    - `src/research_engine/discovery/resolver.py`: full-text resolution through pdf_url, arXiv, Unpaywall, and DOI landing page; never paywalls.
    - `src/research_engine/discovery/source_registry.py`: builds and dispatches adapters by source name.
    - `src/research_engine/discovery/pipeline.py`: end-to-end `DiscoveryPipeline` (plan → search → dedup → snowball → resolve).
    - `src/research_engine/orchestrator.py`: `DISCOVER` stage runs `DiscoveryPipeline`; unblocking campaigns still dispatch browser probe.
    - `src/research_engine/main.py`: constructs `SourceRegistry` + `DiscoveryPipeline` and passes to `Orchestrator`.
    - `pyproject.toml`: added `feedparser>=6.0` dependency.
    - Tests: 56 new discovery unit tests, total 115 tests, 86% coverage.
  - Updated routers with Phase 3 keyword rows and R013–R019 learned-route deltas in `.claude/research-engine-routes.md`.
  - Updated `.claude/agents/discovery-router.md` keyword table for pipeline, schema, registry, orchestrator integration, and main.py.
  - Implemented Phase 4: screening + structured extraction.
    - `src/research_engine/screening/criteria.py`: `BooleanCriterion`, `NumericCriterion`, `LLMRubricCriterion`, `MatchMode`, `CriterionType`, plus factory + default academic criteria.
    - `src/research_engine/screening/ranker.py`: `SourceRanker` applies criteria with optional LLM scorer, returns sorted `SourceScorecard`s; supports must/should/optional weights and `build_llm_scorer` helper.
    - `src/research_engine/extraction/markdownify.py`: HTML → markdown conversion (headings, bold/italic, links, lists, tables) with nav/footer/script/style removal.
    - `src/research_engine/extraction/pdf_converter.py`: `PDFConverter` tries `pdfplumber` then `pypdf`, keeps original on failure.
    - `src/research_engine/extraction/structured.py`: `StructuredExtractor` extracts methodology, data summary, results summary, claims, citations, and conflict detection; abstract fallback when no full text.
    - `src/research_engine/extraction/citation.py`: `extract_citations()`, `normalize_doi()`, `citations_to_dict()`.
    - `src/research_engine/orchestrator.py`: added `SCREEN` and `EXTRACT` stage handlers; persists `scorecards`, `included_papers`, `extracted_sources` to campaign meta; fixed stage-to-stage campaign state freshness.
    - `src/research_engine/main.py`: wires `SourceRanker` and `StructuredExtractor` into `Orchestrator`.
    - `src/research_engine/discovery/schema.py`: added `Paper.to_dict()` / `Paper.from_dict()` for JSON-safe SQLite meta serialization.
    - `src/micro_tools/pdf_to_md/`: standalone PDF → markdown micro-tool with CLI entry point.
    - Tests: 19 new screening/extraction unit tests, total 134 tests, 87% coverage.
  - Updated `.claude/agents/extraction-router.md` keyword table for screening, extraction, orchestrator integration, main.py, and state.
  - Added R020–R027 learned-route deltas to `.claude/research_engine-routes.md` for Phase 4 subsystems.
  - Implemented Phase 5: adversarial verification + evaluation apparatus.
    - `src/research_engine/adversarial/challenge.py`: `Challenge`, `VerificationResult`, `ChallengeDispatcher`, plus dict helpers.
    - `src/research_engine/adversarial/devil.py`: `DevilAgent` rule-based challenger with optional frontier-model deep audit.
    - `src/research_engine/adversarial/verifier.py`: `Verifier` checks quoted evidence, DOI shape, source locators, and URL reachability.
    - `src/research_engine/evaluation/harness.py`: `EvaluationHarness` computes claim, challenge, verification, citation, coverage, and quality metrics.
    - `src/research_engine/evaluation/reporter.py`: `Reporter` produces a Markdown insight brief with claims, evidence, challenges, and caveats.
    - `src/research_engine/evaluation/improvement.py`: `ImprovementProposer` emits candidate R### deltas (never auto-applies).
    - `src/research_engine/evaluation/deep_audit.py`: `DeepAuditor` stub with frontier-model audit path.
    - `src/research_engine/orchestrator.py`: `ADVERSARIAL`, `EVALUATE`, and `DELIVER` stage handlers; persists challenges, verifications, evaluation report, and insight brief.
    - `src/research_engine/extraction/structured.py`: added `paper` to `extracted_source_to_dict()` and `extracted_source_from_dict()` so adversarial stages can reconstruct sources.
    - Tests: 14 new adversarial/evaluation unit tests, total 148 tests, 85% coverage.
  - Updated `.claude/agents/evaluation-router.md` keyword table for orchestrator integration, main.py, and state.
  - Added R028–R033 learned-route deltas to `.claude/research_engine-routes.md` for Phase 5 subsystems.
  - Implemented Phase 6 monitoring/telemetry/status + closed Phase 0–4 gaps.
    - `src/research_engine/llm/__init__.py`: lazy `__getattr__` imports for `AnthropicClient` / `OllamaClient`; no hard runtime dependency on optional clients.
    - `config/default.yaml`: conservative defaults for Unpaywall email, rate limits, browser timeout/retries, and enabled sources.
    - `.claude/agents/{discovery,browser,extraction,evaluation}-router.md`: added `FROZEN EVAL` read-only mode to all four router agents.
    - `src/research_engine/extraction/pdf_converter.py`: `convert_bytes()` for in-memory PDF conversion preserving original byte metadata.
    - `src/research_engine/extraction/structured.py`: URLPolicy-gated full-text fetch with PDF conversion, markdownify HTML extraction, and abstract fallback; wired through `orchestrator.py` via `resolved_map`.
    - `src/research_engine/monitoring/progress.py`: `StageProgressTracker` with uniform/custom weights.
    - `src/research_engine/monitoring/estimator.py`: `TimeEstimator` using per-campaign stage history.
    - `src/research_engine/monitoring/calibrator.py`: `Calibrator` normalizing stage weights from observed durations.
    - `src/research_engine/monitoring/telemetry.py`: `TelemetryAnalyzer` with stuck-stage, stage-failure, and thrashing alerts.
    - `src/research_engine/cleanup/janitor.py`: `CleanupJanitor` vacuums SQLite state DB without touching research artifacts.
    - `src/research_engine/orchestrator.py`: `INIT`, `PLAN`, `FINALIZE` handlers; telemetry/estimator/progress/analyzer integration; `status_snapshot()`; `_run_adversarial` uses `ChallengeDispatcher`; `_run_evaluate` wires `ImprovementProposer` and optional `DeepAuditor`.
    - `src/research_engine/main.py`: `_make_orchestrator` constructs `TimeEstimator`; `status` command prints progress, ETA, remaining stages, and alert count.
    - Tests: 191 tests collected, 88% coverage (`python -m pytest -q`).
  - Added R034–R041 learned-route deltas to `.claude/research-engine-routes.md` for Phase 6 / gap-closure subsystems.
  - Implemented Phase 7: campaign analytics dashboard, model-stack validation, production config loading, and storage cache.
    - `src/research_engine/dashboard.py`: `CampaignDashboard` aggregates campaign status/stage/duration metrics, per-campaign summaries with stage timings, and markdown report generation.
    - `src/research_engine/main.py`: added `report` and `validate-models` CLI commands.
    - `src/research_engine/llm/validator.py`: `ModelStackValidator` pings every configured provider, validates specific model availability, and checks for a small-capacity local model (Gemma/Qwen/Phi/Llama class).
    - `src/research_engine/config.py`: loads `config/default.yaml` with `EngineConfig.get()` dotted access and optional `config_overrides`; added `cache_db_path()`.
    - `src/research_engine/storage/cache.py`: `SourceCache` SQLite-backed cache for discovered `Paper` records keyed by query/source.
    - `src/research_engine/llm/model_registry.py`: moved provider client imports inside `build_provider()` so importing the registry no longer requires optional runtime dependencies.
    - Tests: 31 new unit tests for dashboard, config, validator, and cache; total 219 tests, 88% coverage.
- Open:
  - Continue adversarial review of browser policy and unblocking flow.
  - Wire `SourceCache` into `DiscoveryPipeline` for automatic cache hits/misses (module exists; integration pending).
  - Expand integration tests for `report` and `validate-models` CLI commands.
- Blocked: none.
- Risks:
  - Ethical/legal boundary for "advanced penetration techniques" must remain pinned to authorized/defensive/public-only scope as browser capabilities grow.
  - Local model capability assumption (Gemma/Qwen-class) must be validated during Phase 4 screening/extraction.
  - Unblocking campaigns must not drift into gray-area sources; the SSRF/robots.txt policy is the guardrail.

## v0.1.0 Finish Session — 2026-07-07
- Branch: `finish-v0.1.0` (cut from the `phase-5-adversarial` finish work).
- Bundles A–D audit:
  - ✅ SourceCache wired into `DiscoveryPipeline` (`src/research_engine/discovery/pipeline.py`).
  - ✅ MCP adapter exposes `research_engine_run` and `research_engine_status` with query length / source caps and project-root traversal guard (`src/research_engine/mcp_adapter.py`).
  - ✅ `scripts/github_pr.py` + `scripts/end_session.py` implemented with dry-run default, branch guards, and git-repo validation.
  - ✅ `src/research_engine/cleanup/dedup_files.py` hash-based dedup wired into `CleanupJanitor`.
  - ✅ Architecture docs populated under `docs/architecture/` and Main AI runbook at `docs/runbooks/main-ai-integration.md`.
  - ✅ `Dockerfile` + `docker-compose.yml` added (multi-stage Python 3.12).
  - ✅ E2E campaign test (`tests/e2e/test_campaign.py`) passes with mocked sources.
- Security hardening applied:
  - `URLPolicy._is_public_ip` now rejects multicast/reserved/private/loopback.
  - `URLPolicy._decode_host` percent-decodes hostnames until stable; non-ASCII/IDNA hostnames blocked unless allow-listed.
  - `ssrf_guard.safe_request` reconstructs the response with the original URL so the pinned-IP URL never leaks.
  - `cdp_driver.py`: context-level request routing intercepts every page/popup; popup closes immediately after routing.
  - `discovery/resolver.py`: Unpaywall OA URLs re-validated with `resolve_hosts=True`; RuntimeError from SSRF guard sanitized.
  - `scripts/end_session.py` and `scripts/github_pr.py` validate git repo presence and refuse `main` without `--allow-main`.
- Verification:
  - `pytest -q` → all tests passing, 87% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `.claude/router_eval/*.py` self-checks → all green.
  - `bandit -r src` → 0 HIGH/CRITICAL findings.
  - `scripts/end_session.py` dry-run → completes without touching remotes.
  - `tests/e2e/test_campaign.py` and `tests/integration/test_mcp_adapter.py` pass.
- Security/code review findings fixed in this session:
  - Removed non-existent `WebSocket.close()` handler; HTTP upgrade is already blocked by context-level routing.
  - Prevented internal-IP disclosure in policy / SSRF guard error messages.
  - Fixed `end_session.py` so `github_pr.py` stages/commits/pushes/opens PR instead of committing twice.
  - Added module-level mocked-DNS fixture to `tests/unit/discovery/test_resolver.py` so unit tests no longer hit real DNS.
  - `CDPDriver._fetch` now applies per-action `BrowserAction.headers` via `page.set_extra_http_headers`.

## State of the Build
- **Current work: LLM-driven full-text research engine — PR #17 OPEN** (branch `feat/llm-fulltext-lanes` → `main`, 30 commits).
  - https://github.com/isaac233/Research-Engine/pull/17
  - 7 model lanes + VRAM lifecycle, quality/speed + volume sliders + constraint triangle, replication-grade full-text extraction (methods/data/results), synthesizer + handoff docs, model/GPU telemetry.
  - Audit fixed two blockers that made real research impossible: TLS trust-store (truststore) + gzip double-decode.
  - **Verified:** ~395 tests green, mypy + ruff clean; live end-to-end campaign delivered replication-grade `Insights.MD` from full-text arXiv papers on GPU.
- `main` still at **v0.1.0** (`33c393d`, PR #12, tag `v0.1.0`) until #17 merges.
- To resume next session: `git checkout feat/llm-fulltext-lanes`; read the "PUSHED — PR #17" + audit sections above and `docs/architecture/model-lanes.md`.
- Optional follow-ups: Semantic Scholar API key (429s without it, handled); LLM query planner (still heuristic); a live `--quality 0.9` full multi-lane campaign.

## Next Priority Tasks
1. Gather real-world usage feedback and bug reports from v0.1.0.
2. Plan v0.2.0 scope (likely: DuckDB corpora store, async pipeline, richer browser unblocking, production telemetry sink).
3. Keep router eval baseline current as the codebase grows.

## Decisions / Assumptions
- ADR-001: Python 3.12+ primary; SQLite for state, DuckDB for corpora.
- ADR-002: Port router/eval pattern from Financial Model Training Data.
- Load-bearing assumption: local models can drive deterministic discovery/screening with adversarial oversight.

## v0.1.0+ Standards Document
- Added `Standards.MD` (PR #14) capturing all quality, organization, security, ethics, monitoring, source-management, and session-ritual requirements from `Research Engine Prompt1.MD`.
- It includes pre-change and post-change verification checklists. **Review `Standards.MD` before starting and after completing any future work.**

## v0.1.0+ Source Memory & Agent History Session — 2026-07-07
- Added two searchable SQLite databases to make the engine's prior work reusable and auditable:
  - `src/research_engine/storage/source_memory.py`: `SourceMemory` catalog of good sources with topic/information tags, access methods, reliability scores, search hints, and FTS5 full-text search.
  - `src/research_engine/storage/agent_history.py`: `AgentHistory` append-only audit log of agent actions with URL/API, request/response summaries, outcomes, reasons, evidence links, and redacted headers.
- Added `src/research_engine/storage/_redaction.py` for shared URL/secret/metadata sanitization and `src/research_engine/orchestrator_instrumentation.py` to keep `orchestrator.py` under 800 lines.
- `EngineConfig` gained `source_memory_db_path()` and `agent_history_db_path()`.
- `_make_orchestrator` in `src/research_engine/main.py` now constructs both stores and injects them into `Orchestrator`.
- `Orchestrator` records stage transitions, browser unblocking probes, and discovery search results into `AgentHistory`; discovery sources are remembered in `SourceMemory`.
- Added input-length and URL-policy validation before passing untrusted query/context/URLs to the browser, discovery pipeline, and extractor.
- Added unit tests:
  - `tests/unit/storage/test_source_memory.py`
  - `tests/unit/storage/test_agent_history.py`
  - `tests/unit/storage/test_redaction.py`
  - updated `tests/unit/test_orchestrator.py`
- Updated architecture docs in `docs/architecture/storage.md`.
- Merged via PR #16: https://github.com/isaac233/Research-Engine/pull/16 (commit `efc4e147a48ea3cf13db29427742d335ed4fb57e`).
- Verification:
  - `pytest -q` → all tests passing, 87% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `bandit -r src` → 0 HIGH/CRITICAL findings in changed modules (11 pre-existing LOW/MEDIUM issues elsewhere).

## Self-Research & Golden-Answer Eval Session — 2026-07-08
- Added a deterministic golden-answer evaluation harness and a self-research loop that runs the engine on its own codebase.
  - `src/research_engine/evaluation/harness.py`: `EvaluationReport` gained `precision`/`recall`/`f1_score`; `EvaluationHarness.evaluate()` accepts `expected_claims` and computes precision/recall/F1 via maximum bipartite (Kuhn) claim matching. Paraphrase matching guards against negation, directional opposites, morphological antonyms, qualifier/scope mismatch, numeric mismatch, causal-vs-correlational mismatch, and tautologies.
  - `src/research_engine/main.py`: new `self-eval` CLI command runs a fixture of synthetic sources with known expected claims and reports mean F1, utility mean F1, and a trap robustness score; `--output`/`--force`/`--threshold` options; shared `_validate_output_path` (extracted from `report`).
  - `src/research_engine/extraction/structured.py`: richer claim markers, adjacent-claim merging for multi-sentence findings, confidence scoring (quantitative claims → high), and confidence-based filtering to raise precision.
  - `src/research_engine/evaluation/improvement.py`: R050/R051/R052 delta candidates driven by F1, missing expected claims, and a saturated benchmark.
  - `src/research_engine/evaluation/reporter.py` + `orchestrator.py`: surface precision/recall/F1 in the brief and persisted evaluation report.
  - `scripts/self_research.py`: builds a local doc/source corpus, monkey-patches discovery to return it, drives a full campaign through the orchestrator, then runs the golden-answer benchmark and captures metrics/proposals to JSON. Runtime + F1 thresholds gate exit code.
  - `tests/fixtures/eval_qa.json`: 14 fixtures — 7 utility (all score F1 1.0) + 7 adversarial traps (all correctly score F1 0.0, robustness 1.0).
  - Tests: `tests/unit/evaluation/test_harness.py` (+215), `test_improvement.py`, `test_reporter.py`, `tests/unit/extraction/test_structured.py`, `tests/integration/test_self_eval.py`, `tests/integration/test_self_research.py`.
  - `pyproject.toml`: `pytest.pythonpath` now includes `.` so `scripts.self_research` is importable in tests.
  - `.gitignore`: ignore `data/self_research/` and `coverage.json` generated artifacts.
- Verification:
  - `pytest --no-cov -q` → all tests passing; full run 88% coverage.
  - `mypy src/research_engine` → clean.
  - `ruff check .` → clean.
  - `bandit -r src scripts` → 0 HIGH/CRITICAL (18 pre-existing LOW, 1 MEDIUM).
  - `research-engine self-eval --fixture tests/fixtures/eval_qa.json` → utility F1 1.0, robustness 1.0.
  - `python scripts/self_research.py` → completes in ~0.25s, 20-doc corpus, campaign `completed`.

## Anti-Poison Hardening + 3× Self-Improvement Loop — 2026-07-08

### Anti-poison audit (pre-loop)
- Verified every learning surface can improve without self-poisoning; fixed two gaps (commit `08b148e`):
  - `SourceMemory.remember`: `reliability_score` now defaults to `None` — an incidental re-remember keeps the learned score (new source → 0.5); explicit score still updates. Kills the destructive `INSERT OR REPLACE` regression.
  - `research-engine-router.md`: added FROZEN EVAL read-only mode (the only router lacking it) so eval runs can't mutate the shared learned-routes memory.
- Safe already: `ImprovementProposer` (all `auto_apply:False`, never applied), router routes log (PROVISIONAL-until-verified, one-delta/miss, `.claude/router_eval/replay` contradiction check), `Calibrator` (0.1 floor, normalized, ETA-only).

### Self-improvement loop (ran the engine on itself 3×, verified each insight, implemented sound ones)
- **Loop 1** (`b729b19`): engine flagged R052 "benchmark saturated at F1 1.0". Probed matcher → found `12 mg` matched `12 kg`. Added unit-aware numeric conflict (compares (number, unit) against a fixed unit set) + `unit-mismatch` trap fixture.
- **Loop 2** (`704e0bd`): R052 again. Found `A outperforms B` matched `B outperforms A`. Added comparative operand-swap guard (same word multiset reordered around a comparative marker → conflict) + `comparative-swap` trap fixture. Benign non-comparative reorders still match.
- **Loop 3** (`a7755ca`): self-research's own metrics came back null. Root cause: corpus screened to 0 included papers (20 scored, 0 kept) → EXTRACT/ADVERSARIAL/EVALUATE/DELIVER silently no-op'd via `_run_stub` reporting "not yet implemented", campaign completed with empty brief and no signal. Added `_run_skipped(reason)` for honest skip reporting + `screening_yielded_zero` meta flag so an empty deliverable is visible, not silent.
- Golden-answer benchmark now 17 fixtures (7 utility + 10 traps); self-eval utility F1 1.0, robustness 1.0. All tests/mypy/ruff clean each loop.

### Known / open for next session
- **Root observation still open:** the default screening criteria exclude the self-research doc corpus entirely (0/20). The loop-3 fix makes this *visible* but does not tune criteria — a docs corpus is genuinely not "academic papers". Next: either (a) add a doc-oriented criteria set for self-research, or (b) have `scripts/self_research.py` assert `screening_yielded_zero` is False so the benchmark exercises the full evaluate path. Until then self-research exercises only the golden-answer benchmark path, not the live-campaign evaluate path.
- Benchmark keeps reporting "saturated" each loop because fixed traps pass; that is expected (bar rises each loop). Real signal is the matcher weaknesses found by probing, not the generic R052 text.
- Branch `feat/self-research-golden-eval`; commits `08b148e`, `b729b19`, `704e0bd`, `a7755ca` on top of `67a21cb`. NOT pushed, no PR.

## Notes for Next Agent
- All routers live under `.claude/agents/` and learned routes under `.claude/research-engine-routes.md`.
- The eval harness under `.claude/router_eval/` must remain isolated from `src/`.
- `scripts/end_session.py` is a stub; do not run it for real until Phase 9.
- The `Research/` folder layout is documented in `docs/plan/master_plan.md` section 4.13 and implemented in `src/research_engine/config.py`.
- Discovery subsystem is fully wired into the orchestrator; start Phase 4 with `screening/criteria.py` and `screening/ranker.py`.
- New Phase 7 modules: `dashboard.py`, `llm/validator.py`, `storage/cache.py`; CLI commands: `report`, `validate-models`.
