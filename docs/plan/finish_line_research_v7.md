# Finish-Line Research v7 — Online SOTA scan (2026-07-17): concrete tools that GREATLY improve the task-53 attack

**Supersedes v6.** v6 distilled the right *concepts* (ADORE, RhinoInsight, attribute-or-abstain)
but from memory, not a live scan, and left the FACT lever as "build an NLI checker." This doc is
a fresh online search (firecrawl paper/web/github + arXiv full-text reads) that turns those
concepts into **named, verified, locally-runnable tools** and adds two architectures that
directly attack task 53's failure and did not appear in v6. Every claim below was read from the
source this session, not recalled.

**The gap to close (live, unchanged):** task 52 RACE .386 / FACT 72.5% (29/40) vs task 53 RACE
.327 / **FACT 32.5% (13/40)**. Task 53 = vague query + sparse/PDF/paywalled evidence + writer
over-cites a thin bank. The bar (Claude-3.7) is RACE 40.67 — and **current SOTA is 52-53**
(ADORE 52.65, DualGraph 53.08), so 40 is not a ceiling, it's a waypoint.

---

## 1. The four weapons (new/sharpened vs v6)

### WEAPON 1 — `bespoke-minicheck` as the citation abstain gate (the biggest concrete FACT lever)
**This is the single highest-ROI find.** MiniCheck (Tang/Laban/Durrett, EMNLP 2024,
github.com/Liyan06/MiniCheck, Apache-2.0) is a small grounded fact-checker: `f(document,
sentence) → {supported, not}` at **GPT-4 quality for ~400× less cost.** Two ways to run it, both
local:
- **`ollama run bespoke-minicheck`** — 7B, 4.7 GB, 32K context, ALREADY in the user's Ollama
  ecosystem. Prompt template is literally `Document: {document}\nClaim: {claim}` → replies
  `Yes`/`No`. SOTA on LLM-AggreFact (11 human-annotated grounding datasets).
- **`pip install minicheck` → `MiniCheck(model_name='flan-t5-large')`** — **770M, sub-1B,
  reaches GPT-4 perf**, runs on CPU in ms/claim → **zero VRAM contention with the main Ollama
  model** (the better choice for our wedge-prone single-GPU box).

**Why it fixes task 53 where v6's verify-regen failed ([[verify-regen-negative]]):** that attempt
scored a claim against its *lone bank span* (a subset → too strict → dropped good cites).
MiniCheck scores the claim against the **whole document/page** — *exactly the granularity the
FACT judge uses* (`bench/fact.py` re-fetches the page and asks entailment vs the full ~6000-char
page). So MiniCheck is aligned with the grader by construction.

**Wiring (Lever F1 — attribute-or-abstain):** post-hoc, after the writer drafts, before scoring.
For each cited sentence `s` with cite `[eN]` → bank span's source page `p`: run
`MiniCheck(doc=p_text, claim=s)`. If `No` (or prob < τ): **drop the `[eN]` marker** (soften to
uncited) rather than delete the sentence. Env-gated `RESEARCH_ENGINE_ABSTAIN_GATE=minicheck`,
τ via `_ABSTAIN_TAU`. Lives in `synthesis/verify_citations.py` (the abstain path, not the failed
regen path). Task 53's 76 markers → keep only the ~13 that verify → FACT precision jumps and the
report stops making unsupported claims. Measure: FACT c.acc on task 53.

### WEAPON 2 — DualGraph-lite: a coverage ledger drives gap retrieval (the RACE/coverage lever)
**DualGraph (arXiv:2602.13830, "A Tale of Two Graphs", RACE 53.08 on DRB) is the definitive
answer to task 53's dropped dimensions — and its own motivating example is our task 52
(Duan/Buffett/Munger).** Its thesis, verified from the paper: outline-only planning (what our
`ReactPlanner` does — rebuild outline each round from the banked evidence) gives **weak
supervision for knowledge gaps**; the agent elaborates what it already has instead of finding
what's missing. Fix: maintain a **Knowledge Graph** *separate* from the outline; analyze its
topology (weak-evidence edges → *Enrich*; missing/hole edges → *Explore*) to generate **targeted
gap queries**. Bounded per round (top ⌊N/4⌋ per candidate type), monotone coverage.

The full version (LLM entity/relation extraction + Leiden community detection + SBM structural
holes + embeddings) is too heavy for our local box. **DualGraph-lite = an evidence-coverage
matrix:** rows = enumerated entities (from the grounding brief, Weapon 4), cols = cross-cutting
sub-questions (asset allocation / governance / returns / geography …). Each cell holds the bank
spans that cover (entity, sub-question). After each react round, cells that are **empty or
weak (< k spans)** emit a concrete gap query ("`{entity} {sub-question} 2024 annual report`").
This is DualGraph's Enrich/Explore split without the graph machinery, and it is a *far* stronger
retrieval-completeness lever than v6's "raise `per_objective_searches` to 4-5." Env-gated
`RESEARCH_ENGINE_COVERAGE_LEDGER=1`, wired into the react loop's gap-query generation.

### WEAPON 3 — ADORE memory-locked synthesis (structural faithfulness, verified #1 at 52.65)
Read from source (arXiv:2601.18267): each section is written under a **hard constraint** — only
the section's *admissible* evidence set (its claim–evidence subset of the bank) is in the write
context. Result: **traceability by construction** — a section physically cannot cite a span it
wasn't given, so over-citation (task 53's 76→13) is impossible. Plus **evidence-coverage-guided
execution**: audit each section's support, and only under-supported sections trigger targeted
re-retrieval; stop when coverage is met (not a fixed page budget). We already have the split
substrate (`EvidenceBank` verbatim + `SummaryBank` per-page) — Weapon 3 is **section-scoped
packing**: at write time, pass `SectionWriter` only the spans assigned to that section (by the
coverage ledger / outline citations), not the whole bank. Env-gated
`RESEARCH_ENGINE_SECTION_LOCKED_WRITE=1`. Pairs with Weapon 1: locked write raises the *ceiling*
of verifiable cites, MiniCheck removes the *residue*.

### WEAPON 4 — Autonomous grounding brief + ScaffoldAgent node-utility (the vague-query lever)
Two mechanisms for "advanced logic to understand and act on a vague question":
- **ADORE Grounding Agent (autonomous):** one pre-search LLM call turns the underspecified
  prompt into a concrete brief with **explicit scope assumptions it proposes itself** (no user
  clarification — correct for the bench): `{scope, definitions, entities[], per-section
  success-criteria[]}`. Seeds the outline + entity rows of the coverage ledger. (v6's S1/S2,
  now confirmed as ADORE's #1-ranked mechanism.)
- **ScaffoldAgent utility signal (arXiv:2606.20122), verified algorithm:** instead of rebuilding
  the whole outline each round, treat it as a tree and apply **Expansion** (node too broad → split
  + retrieve), **Contraction** (redundant siblings → merge), **Revision** (weak support → refresh
  + retrieve). Pick the next node by UCB on **−mean-utility** (revisit weak nodes) + exploration
  bonus; utility = retrieval-novelty (MMR: relevant *and* non-redundant) + structure-coherence +
  generation-grounding. **The key borrow for us: a per-section utility score tells us WHICH
  section is weak** → drives Weapon 2's gap queries and Weapon 3's re-retrieval precisely,
  instead of spraying `per_objective_searches` uniformly. Even a stripped version (retrieval-
  novelty + a groundedness check via Weapon 1) gives the targeting signal.

---

## 2. Why this is a step-change over v6, not a marginal tweak
| Axis | task 53 failure | v6 answer | v7 answer (concrete tool) |
|---|---|---|---|
| **FACT (32.5%)** | over-cite thin bank | "build an NLI checker" | **`bespoke-minicheck` (Ollama) / MiniCheck-flan-t5 770M** — proven, page-granular, aligned to the grader; abstain-drop |
| **Coverage/RACE** | dropped dimensions | "raise per_objective_searches" | **coverage ledger (DualGraph-lite)** — gap queries from empty/weak cells; monotone completeness |
| **Faithfulness** | cites unprovable | "memory-locked writing (L)" | **section-scoped packing** on our existing EvidenceBank — cite-what-you're-given by construction |
| **Vague query** | topic drift | grounding brief (concept) | **ADORE grounding brief + ScaffoldAgent node-utility** — scope + per-section weakness targeting |

The FACT lever alone (Weapon 1) is a drop-in, model-free, ~1-file change that directly targets the
axis where 53 (32.5%) most trails 52 (72.5%). It is the first thing to build and measure.

## 3. Revised build order (highest ROI first; all env-gated, default-off, TDD, measure on task 53)
1. **Weapon 1 — MiniCheck abstain gate.** Smallest diff, biggest FACT lever, no infra beyond an
   `ollama pull bespoke-minicheck` or `pip install minicheck`. Measure task 53 FACT.
2. **Weapon 2 — coverage ledger** → gap queries. Biggest coverage/RACE lever for the vague class.
3. **Weapon 3 — section-scoped packing** (raises the verifiable-cite ceiling; pairs with #1).
4. **Weapon 4 — grounding brief + node-utility targeting** (vague-query scoping; also feeds #2/#3).
5. **PDF ingestion (v6 S3)** still valid and unbuilt — `PDFConverter.convert_bytes` exists,
   `read_fn`/`_fetchable_ref` (orchestrator.py:1178/1205) still drop `.pdf`/`doi.org`. Wire it so
   the coverage ledger's SWF-report cells can actually be filled. Keep size/time caps.

Method discipline unchanged: same winning env + kimi judge, archive `engine.jsonl`/`scores.jsonl`
+ purge serp before each run, watchdog attached, task 53 is the measurement surface.

**⚠️ MEASUREMENT INSTRUMENT (added 2026-07-17, commit `2e0a5c9`): live task 53 swings ~±11 RACE
at N=1** (proven: an inert W5 run — 0 PDFs read = baseline-equivalent config — scored 21.05 vs
baseline 32.68). Single-run deltas are noise. **Before trusting any weapon comparison, run under
`RESEARCH_ENGINE_RETRIEVAL_CACHE=1`** (`discovery/retrieval_cache.py`) which record-then-replays
serp results + page reads so a re-run of the same config banks identical evidence → variance
collapses to judge noise. First run per config RECORDS (live), subsequent runs REPLAY. Reset a
stale recording by deleting the `serp_replay_cache`/`page_replay_cache` tables in `data/cache.db`.
First isolation matrix (all N=1, pre-cache — noise-dominated): baseline 32.68 / W1-abstain 31.31 /
W5-PDF(inert) 21.05 / W3-lock 22.49 / combined 24.19. Mechanistic reads that survived the noise:
W1 neutral/safe; **W2+W4 net-negative (grounding brief's 80-cell grid diluted retrieval 54→33
spans)**; W3 likely-negative (skips deepen = the comp/insight driver); W5 inert unless PDFs surface.

## 4. References (all read/verified this session)
- **MiniCheck** — github.com/Liyan06/MiniCheck (Apache-2.0); Ollama `bespoke-minicheck` (7B, 4.7GB,
  32K); pip `minicheck` `flan-t5-large` (770M, GPT-4-level). arXiv:2404.10774. LLM-AggreFact SOTA.
- **DualGraph** — arXiv:2602.13830, "A Tale of Two Graphs: Separating Knowledge Exploration from
  Outline Structure for OEDR." RACE 53.08 (GPT-5). KG-driven Enrich/Explore gap discovery.
- **ADORE** — arXiv:2601.18267 (Atlassian). RACE 52.65 (#1 DRB). Memory-locked synthesis +
  evidence-coverage-guided execution + section-packed grounding + autonomous grounding agent.
- **ScaffoldAgent** — arXiv:2606.20122. Utility-guided dynamic outline: Expansion/Contraction/
  Revision, UCB node selection, utility = retrieval-novelty(MMR)+structure+generation.
- **AgentCPM-Report** — arXiv:2602.06540 (interleave draft+deepen; outline quality = bottleneck).
- **RhinoInsight** — arXiv:2511.18743 (verifiable checklist from query alone). **WebWeaver** —
  arXiv:2509.13312 (dynamic outline / OEDR, our north star).
- **Attribute or Abstain** — arXiv:2407.07799. **Correctness ≠ Faithfulness in RAG** —
  arXiv:2412.18004. **HALT-RAG** — arXiv:2509.07475 (calibrated NLI ensemble + abstention).
- **DeepResearch Bench II** — arXiv:2601.08536 (evolved rubrics; DualGraph 41.48 Total).
- **MindDR** — arXiv:2604.14518 (leading DRB with 30B models — local-scale is viable).
</content>
</invoke>
