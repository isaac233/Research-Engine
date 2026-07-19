# Finish-Line Research v8 — Task 53 Gap: Diagnosis + Online-Research-Backed Fix Plan (2026-07-18)

**Question:** task 53 ("Researching how the world's wealthiest governments invest") scores far below
task 52 (Buffett/Munger). Best known: 53 = RACE 32.7 / FACT 32.5% vs 52 = RACE 38.6 / FACT 72.5%
(CDP-era N=3, `bench/out/scores_20260717_142110.bak.jsonl`). Goal: 53 ≥ 52's best; overall goal:
beat the bar (RACE 40.67 / FACT ~93%) on local models.

---

## 1. Diagnosis (local evidence)

Per-dim, task 53 vs 52 (CDP-era run):

| dim | 53 | 52 | gap |
|---|---|---|---|
| comprehensiveness | .322 | .390 | −.068 |
| insight (weight 0.39!) | .319 | .359 | −.040 |
| instruction_following | .339 | .432 | **−.093 (worst)** |
| readability | .342 | .389 | −.047 |
| FACT c.acc | .325 | .725 | **−.400 (crater)** |

Best 53 article (`engine_20260717_142110.bak.jsonl`, 19.5k chars, 68 cites, 16 hosts):

1. **IF drift** — the report opens with a "richest countries by per-capita purchasing power" essay
   (Macao casinos…). Judge criteria demand SWFs/state investors + "how they invest". Cohort
   misdefined ⇒ IF and comp bleed.
2. **Headings = raw imperative objectives** ("Identify the top…", "Understand the primary…").
   Title repeats the prompt verbatim. Reference = one compound analytical title, 70k chars.
3. **Zero tables, thin data.** Judge readability criterion (w0.2) explicitly rewards
   data/tables; insight criteria want allocation NUMBERS and comparative synthesis.
4. **Length 19.5k vs reference 70k** — RACE is judged comparatively vs the reference article.
5. **Sources:** 16 hosts × 1 page each; no fund annual reports (all PDFs — dropped by design),
   no IMF/SWFI data pages (bot-hostile; CDP recovered some).
6. **FACT 32.5%** — see §2: much of this is our harness being harsher than the official bench,
   concentrated exactly on bot-hostile tasks like 53.

## 2. FINDING A — our FACT harness is systematically harsher than the official bench (the crater is partly instrument)

Read the official pipeline sources (`Ayanami0730/deep_research_bench`, downloaded to scratchpad):
`utils/scrape.py`, `utils/validate.py`, `utils/stat.py`, `utils/extract.py`, `utils/api.py`.

Official semantics vs ours (`bench/fact.py`):

| axis | official | ours | effect on us |
|---|---|---|---|
| fetcher | **Jina Reader** (renders JS, reads PDFs, bypasses most bot walls), 3 retries + 1s sleep | RawHTTPBrowser, no CDP, no retry | 403s on exactly the hosts CDP recovered |
| failed / invalid page | judge labels all its statements **`unknown`** | `scrape failed` prefix → counted **unsupported** | inflates denominator |
| denominator | `stat.py:27` — **`unknown` excluded**; `validate_error` citations skipped | all 40 pairs count | up to ~half of task-53 pairs auto-fail |
| support standard | "facts/data found **entirely or partially** … supported (**data accepts rounding**)" | "strict… **directly states or clearly entails**; too vague → not supported" | stricter judge |
| call shape | all statements for one URL judged in **one batched call** | one call per (fact,url) pair | cost + judge-context differences |

Implication: our FACT numbers are **not comparable** to the leaderboard bar and are biased
*against* bot-hostile tasks. Task 53's 32.5% (13/40) under official semantics — where failed
fetches drop out of the denominator and partial support counts — plausibly reads 55-75%.
Fixing this is **fidelity to the official bench, not gaming** (they fetch via Jina; a
CDP-rendering fetcher is the local equivalent).

Corollary: `orchestrator.py` W5 currently refuses to make PDF spans citable because *our*
FACT fetcher can't read PDFs (`orchestrator.py:193`). Official Jina **reads PDFs** — so once the
bench fetcher converts PDFs (we already have `PDFConverter`), PDF citations are legitimate, and
task-53's richest sources (SWF annual reports) become both readable and citable.

## 3. FINDING B — rubric-as-scaffold is how the leaderboard #1 does it (inference-time, no training)

- **DuMate-DeepResearch** (arXiv:2606.07299; leaderboard #1, RACE 58.03): generates a
  **persistent rubric** from (topic, outline) at start → injected into planner AND writer;
  an **ephemeral rubric** refreshed each cycle from (outline, accumulated evidence) → drives
  gap queries and serves as the **stopping criterion** (no outstanding gap → stop). Writer
  consumes only the persistent rubric. All inference-time — portable to our ReactPlanner.
- This is the *principled* version of our W2 (coverage ledger) + W4 (grounding brief), which
  measured net-negative because the 80-cell grid **diluted** retrieval. DuMate's ephemeral
  rubric is generated *conditioned on evidence already banked* — it targets gaps to ADD depth,
  not to spread the page budget thin. Matches HANDOFF retune note verbatim.
- Rubric-based evaluation/steering is the field's converged direction: DeepResearch Bench II
  (2601.08536, 9,430 binary rubrics), RubricEM (2605.10899), DEEPRUBRIC (2606.17029),
  query-specific rubric generators (2602.03619), FinResearchBench II (2607.12252).
- **We can port the official criteria generator**: `prompt/criteria_prompt_en.py` (in the bench
  repo, Apache-2.0, downloaded) contains the exact dimension-weight + criteria-generation
  prompts the judge uses to build task rubrics. Running that *style* of prompt on the task
  prompt with a local model at campaign start = self-generated rubric. No test-set leakage —
  it uses only the task prompt (bench's own `criteria.jsonl` stays untouched at run time).
- Recurring criteria shapes across tasks (from the official prompt's structure + task-53
  criteria): **definition/scope of cohort · breadth of entities · quantitative detail ·
  comparative synthesis · trends/emerging factors · risks/governance · source breadth**.
  Generic section seeds, not task-53-specific.

## 4. FINDING C — fetchability last-mile: archive fallbacks are standard practice

- Standard playbook for blocked pages (2026 scraping guides): **Wayback Machine**
  (`https://web.archive.org/web/2/<url>` latest-snapshot redirect; CDX API for bulk) and
  **r.jina.ai** reader prefix (free tier) as read fallbacks. Keyless wayback fits our stack:
  read_fn lane after CDP also fails. Archive content ≈ what the official Jina fetch would see
  for stable pages (SWF/IMF reports are stable).
- gpt-researcher's bench PR (#1861) got +36% verified citations from small surgical fixes
  (token limits actually applying, citation plumbing) — precedent that harness/plumbing fixes
  move FACT more than model changes.

## 5. Ranked plan (expected Δ on task 53; all env-gated, default-off per project convention)

### P0 — FACT harness parity (bench-side; expected FACT +20-35pt on 53, +5-10pt on 51/52)
1. `bench/fact.py`: port official semantics —
   (a) 3-way verdict supported/unsupported/**unknown**; unknown + fetch-failed **excluded from
   denominator** (report both raw and official-parity numbers during transition);
   (b) official EN validate prompt verbatim (partial support OK, rounding OK, invalid page →
   unknown); (c) batch all statements per URL in one judge call; (d) 3 fetch retries.
2. Judge fetcher = engine's CDP-fallback browser + `PDFConverter` for `.pdf` → Jina-parity.
3. Flip W5's "PDF spans uncitable" restriction once (2) lands (`orchestrator.py:1330-1332`).
4. **Cheapest validation experiment first: re-score the EXISTING best articles**
   (`engine_20260717_142110.bak.jsonl`) under parity FACT. No engine run needed. If 53's FACT
   jumps ≥55%, the crater was mostly instrument → engine work then targets RACE only.

### P1 — Rubric scaffold, DuMate-style (engine; expected RACE +2-5 on 53, helps all tasks)
5. `planning/rubric.py`: persistent rubric from task prompt at campaign start (port official
   criteria-prompt style; local model; temp 0; cached by task under RETRIEVAL_CACHE).
6. Seeded outline built FROM rubric dimensions (replaces raw-objective headings → kills dupes
   + imperative headings + cohort drift). Noun-phrase headings + compound analytical title.
7. Writer section prompts get the persistent rubric (grounding for insight/comparative asks).
8. Retuned ephemeral loop (replaces W2/W4 defaults): each react round, gap-rubric =
   f(outline, evidence digest) → ≤2 gap queries/round, only after core objectives banked;
   stop when no outstanding gap. (Exactly HANDOFF's retune prescription, now with a
   principled generator.)
9. Generic section seeds when rubric is sparse: scope/definition · comparative synthesis ·
   trends · risks/governance.

### P2 — Fetchability last mile (engine; expected +1-3 RACE via spans on thin tasks)
10. read_fn lane: CDP fail → **Wayback fallback** (`web.archive.org/web/2/<url>`, keyless).
11. Objectives dedup + fetchability-aware serp rerank (HANDOFF items c,d — rubric outline may
    subsume dedup; measure).
12. Thin-objective retry appends data-oriented terms ("annual report", "allocation",
    "statistics") — surfaces the PDFs W5 needs (it measured inert: 0 PDFs surfaced).

### P3 — Reference-scale report (engine; expected +1-3 RACE comp/read)
13. `WRITER_MAX_SENTENCES` 16→24-32, `_MAX_TOKENS` 2400→3600; rubric outline gives 8-10
    sections → 30-45k chars (reference 70k). Watch FACT precision as claim count grows.
14. Writer nudge: emit a markdown table when a section's bank holds ≥3 comparable numeric
    facts (readability criterion explicitly rewards data presentation).

### Measurement protocol (per HANDOFF instrument)
- `RESEARCH_ENGINE_RETRIEVAL_CACHE=1` record-then-replay; archive `engine.jsonl`/`scores.jsonl`
  + purge serp rows before each recorded run; kimi judge; N=3 (51/52/53); watchdog attached.
- Order: **P0.4 re-score first** (no engine run) → P0 full → P1 on cached evidence where
  possible → P2/P3 live.
- Caveat: kimi-judged numbers are internally comparable only; official bar now GPT-5.5-judged
  (evaluator switched 2026-05-11; legacy Gemini-2.5 branch preserved). The 40.67 bar is
  Gemini-era Claude-3.7 — keep as internal target, re-baseline if we submit.

## 6. Sources
- Official bench: github.com/Ayanami0730/deep_research_bench (utils/{scrape,validate,stat,extract,api}.py, prompt/criteria_prompt_en.py; README news 2026-05-11 evaluator switch)
- DuMate-DeepResearch: arXiv:2606.07299 (rubric scaffold, recursive search, #1 leaderboard)
- Rubric line: DRB-II 2601.08536 · RubricEM 2605.10899 · DEEPRUBRIC 2606.17029 · 2602.03619 · FinResearchBench-II 2607.12252
- Citation attribution: G-Cite/P-Cite 2509.21557 (known) · CiteFix 2504.15629 (measured negative here) · WebWeaver 2509.13312
- Fetch fallbacks: webscrapingapi.com 2026 playbook (Wayback CDX) · jina.ai/reader
- Precedent: gpt-researcher PR #1861 (+36% verified citations from plumbing fixes)
