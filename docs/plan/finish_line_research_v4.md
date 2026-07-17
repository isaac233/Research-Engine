# Finish-line research v4 — the metric-aligned FACT lever (2026-07-16, online-sourced)

Standing order: ~2× FACT (default `section_synth` = **49%** → toward Claude bar **93.7%**)
WITHOUT regressing RACE (**28.31**, project best), E.Cit (16.75), Read (33.3). Prior:
v3 diagnosed "paraphrase drift" and found #10 (post-hoc lexical re-point) FLAT/HARMFUL.
This round read the FACT scorer itself + 3 papers in full and found the diagnosis was
**half-right**: the lever is verify-and-regenerate, and it must mirror the *actual* metric.

## THE UNLOCK — what the FACT metric actually checks (read `bench/fact.py` + `bench/prompts.py`)
FACT is **not** a verbatim/substring check. Per sentence it:
1. Extracts `(fact, url)` pairs from the report (`FACT_EXTRACT_PROMPT`).
2. Fetches the URL live, markdownifies, keeps the **first ~6000 chars** (`_MAX_CONTENT_CHARS`).
3. Asks the judge (`FACT_SUPPORT_PROMPT`, strict): *"is the CLAIM directly stated or clearly
   entailed by this source content? Unrelated / contradicts / error / too vague → not supported."*

So a cite FAILS for one of two reasons:
- **Structural** — the fetched slice is boilerplate / paywall / error, OR the evidence lives
  beyond the first 6000 chars, so the judge sees no support even when the claim is true.
- **Semantic** — the claim as written is not entailed by the visible page text (drift, invented
  specifics, or too-broad/vague summary).

**Key fact that makes this tractable:** our `EvidenceBank` span is a *verbatim substring of the
cited page*. So a **local entailment pre-check of `(claim, bank_span)` predicts the FACT judge's
`(claim, page)` verdict** — if the span is in the fetched slice (usually true for HTML), and the
claim is entailed by the span, the judge (reading the page) should also entail it. This is the
hook: we can approximate the grader offline, per sentence, with no re-fetch.

## WHY #10 (cite_fix) and the old verify_citations both failed — and the gap between them
- `verify_citations.py` — substring-matches the span's first 80 chars against a **re-fetched**
  page, drops the `[eN]` if absent. Two failure modes the HANDOFF already recorded: brittle
  (drops genuine *paraphrases* — exactly the claims we want to keep) and boilerplate re-fetch
  misses. Substring ≠ entailment.
- `cite_fix.py` (#10) — **lexical** term-overlap re-point against the bank. Measured FLAT then
  HARMFUL on synth (dropped genuinely-supported paraphrased cites; FACT 49.3→44.7, E.Cit 16.75→12).
- **Neither uses the model as an entailment judge against the trusted span.** That is the whole
  unexplored space — and it is precisely what the metric rewards.

## THE METHOD — VeriCite's "decouple attribution, verify, refine" (arXiv:2510.11394, read in full)
VeriCite is the closest fit and is **inference-time / no-generator-training**:
1. Draft an initial answer with cites.
2. **Verify** each statement's cite via an NLI/entailment model φ against its passage; **discard
   the unsupported**. "unsupported content must be systematically eliminated, retaining
   exclusively evidence-substantiated statements."
3. **Refine** — the LLM reorganizes the *verified* statements + cites into fluent prose,
   explicitly forbidden from altering content ("rhetorical reorganization rather than content
   alteration"). This is what protects coverage/RACE while attribution stays locked.
Result: "significantly improve citation quality while maintaining answer correctness."

Supporting evidence from the other two papers read in full:
- **FullCite (arXiv:2606.07130)** — three grounding strategies (prompt / grammar-constrained
  decoding / **posthoc span alignment**). Posthoc span alignment (reconstruct near-verbatim
  snippet by Jaccard≥0.7) gave the *largest* snippet-F1 gains (12.8→61.9). But two warnings that
  match our #10 negative: (i) forcing verbatim **lowered claim↔cite semantic similarity** (over-
  tight hurts faithfulness), and (ii) on **free-form long-form** answers the grounding gains
  shrink vs short factoid QA — so don't over-index on lexical tightness; entailment is the target.
- **FineRef (arXiv:2602.18437)** — the **attempt → reflect → correct** per-citation pattern is
  the right shape (localize the failing cite, fix only it), and it distinguishes *mismatch*
  (claim not entailed by cited passage) from *irrelevance*. Their gains need SFT+RL (no budget for
  us), but the inference-time behavioral pattern is copyable via prompt: verify → regenerate only
  the failing sentence constrained to its span → drop if still failing.

## WHAT TO BUILD (this session — cheap, no training, measured on the cache)
Both variants take the RACE-winning `section_synth` draft and add a metric-mirroring pass.
Reuse `EvidenceBank` spans + the FACT entailment framing; **local model** as φ (temp 0).

1. **`section_synth_verify` (verify-and-DROP)** — for each sentence carrying `[eN]`, ask the
   local model "is this sentence entailed by span eN's text?" (the FACT_SUPPORT framing, but
   claim-vs-bank-span). If no → strip that `[eN]`. Pure precision. Prediction: FACT ↑, E.Cit ↓
   a little (dropped cites), RACE ~flat (prose untouched). The floor experiment.
2. **`section_synth_regen` (verify-and-REGENERATE, the VeriCite/FineRef move — primary bet)** —
   same verify, but for a failing sentence **rewrite it to faithfully restate its span** (attempt
   → correct), keep the `[eN]`; only drop if the rewrite still fails. Preserves coverage → should
   protect E.Cit **and** RACE while lifting FACT. This is the one to beat the baseline.

**GATE (from the standing order):** promote only if FACT rises a lot AND RACE stays ≥ ~28 AND
E.Cit does not collapse. Same-run A/B is mandatory (±2 RACE / ±10pt FACT run-to-run):
```
python -m bench.writer_eval score \
  --variant section_synth,section_synth_verify,section_synth_regen \
  --judge ollama --judge-model kimi-k2.7-code:cloud
```
Also keep `section_faithful_deepen` (already staged) in the A/B as the verbatim-tight contrast.

## What NOT to do (carried + reinforced)
- Do NOT substring-match a re-fetched page (`verify_citations` failure) — entailment vs the bank
  span instead.
- Do NOT lexical-re-point (#10 `cite_fix` failure — drops good paraphrases).
- Do NOT chase grammar-constrained verbatim decoding as the FACT lever — FullCite shows it *lowers*
  claim↔cite semantic alignment and the gains evaporate on long-form. Entailment is the target,
  not character-identity.
- Do NOT chase SFT/RL (FineRef/VeriCite-trained numbers) — no budget; inference-time verify-refine.

## Structural failures (deferred, second-order) — the OTHER half of the FACT gap
Verify-refine only fixes semantic failures. Structural failures (page slice lacks the span:
paywall/JS/PDF/deep-page) cap the achievable FACT no matter how tight the prose. Levers, later:
prefer HTML over PDF/DOI at cite time (partly done), prefer spans that occur early in the page,
and prefer URLs whose FACT-style fetch actually returns the span. Measure verify-refine first;
if FACT plateaus below target with clean prose, the residual is structural.

Sources read in full: 2510.11394 (VeriCite), 2606.07130 (FullCite), 2602.18437 (FineRef).
Metric ground truth: `bench/fact.py`, `bench/prompts.py` (FACT_EXTRACT / FACT_SUPPORT).
Prior rounds: finish_line_research_v3.md (why #10 failed, why #11 synth won).
