# Finish Plan — Research Engine v0.1.0

**Date:** 2026-07-07  
**Current branch:** `phase-5-adversarial`  
**Current state:** Phases 0–7 implemented; 219 tests passing at 88% coverage; router eval self-checks green.

---

## 1. What’s Already Done

| Phase | Status | Key deliverables |
|---|---|---|
| 0 | ✅ | Repo, CI skeleton, routers, eval harness, HANDOFF |
| 1 | ✅ | Orchestrator, state/events, LLM layer, CLI skeleton |
| 2 | ✅ | Browser (CDP, raw HTTP, GraphQL, robots, SSRF policy, unblock probe) |
| 3 | ✅ | Discovery pipeline, adapters (Semantic Scholar, Crossref, arXiv, OpenAlex, SERP, web crawl), dedup, snowball, resolver |
| 4 | ✅ | Screening criteria/ranker, markdownify, PDF conversion, structured extraction, citations |
| 5 | ✅ | Devil, Verifier, challenge dispatcher, evaluation harness, reporter, improvement proposer, deep-audit stub |
| 6 | ✅ | Progress tracker, time estimator, calibrator, telemetry analyzer, janitor |
| 7 | ✅ | Dashboard, model-stack validator, config loading, `SourceCache`, artifact manager |

Verified:
- `pytest -q` → 219 passed, 88% coverage.
- `python .claude/router_eval/*.py` self-checks → all green.
- Current PR: #11 covers Phases 5–7.

---

## 2. What “Finish” Means

Reach the **v0.1.0 Definition of Done** in `docs/plan/master_plan.md` §7. The remaining gaps fall into four bundles:

### Bundle A — Close Phase 7 open items
1. **Wire `SourceCache` into `DiscoveryPipeline`.**
   - Cache raw `SearchResult.papers` per `(query, source)` before deduplication.
   - Skip upstream calls when cache hit exists; refresh on miss.
   - Add unit test in `tests/unit/discovery/test_pipeline.py`.
2. **Adversarial review of browser policy + unblocking flow.**
   - Add SSRF tests for edge cases (IPv6 loopback, URL-encoded hosts, IDNA homoglyphs).
   - Ensure `UnblockProbe` never reports “no solution” without an evidence log (already coded; verify with test).
3. **Integration tests for `report` and `validate-models` CLI commands.**
   - Add `tests/integration/test_cli.py` using `click.testing.CliRunner` and temporary project root.

### Bundle B — Phase 9 automation hardening
4. **Implement `scripts/github_pr.py`.**
   - Create branch, stage changes, commit, push, open PR via `gh` CLI / `GITHUB_TOKEN`.
   - Add unit test with mocked subprocess.
5. **Implement `scripts/end_session.py`.**
   - Run janitor → update `HANDOFF.md` → run tests → commit → push → open PR.
   - Safe dry-run mode; refuses to run on `main`.
6. **Implement `src/research_engine/cleanup/dedup_files.py`.**
   - Hash-based file dedup under `data/`; keeps at least one copy; logs deletions.
   - Wire into `CleanupJanitor`.
7. **Integration tests for source adapters.**
   - Add `tests/integration/discovery/test_adapters.py` with mocked HTTP responses for each adapter.

### Bundle C — Phase 8 Main AI integration
8. **Implement `src/research_engine/mcp_adapter.py`.**
   - Expose `research_engine_run` and `research_engine_status` stdio MCP tools.
   - Add `tests/integration/test_mcp_adapter.py`.
9. **Write `docs/runbooks/main-ai-integration.md`.**
   - Step-by-step for Claude Code calling the engine via MCP.
10. **Add E2E campaign test.**
    - `tests/e2e/test_campaign.py`: run a toy blocker query against mocked sources, verify `Research/<slug>/<slug>_Insights.MD` and `Research/Insights.MD` exist.

### Bundle D — Phase 10 ship-ready polish
11. **Write `docs/architecture/*.md`.**
    - `orchestrator.md`, `browser.md`, `discovery.md`, `screening.md`, `adversarial.md`, `evaluation.md`, `monitoring.md`, `storage.md`.
12. **Update `README.md`.**
    - Install, quickstart, architecture overview, status reflect Phases 1–7 completion and v0.1.0 readiness.
13. **Add `Dockerfile` + `docker-compose.yml` (optional but in master plan).**
    - Multi-stage Python 3.12 image; runs E2E test on build.
14. **Security review.**
    - Run `security-reviewer` agent on all changed files; fix CRITICAL/HIGH; scan for secrets.
15. **Eval harness benchmark baseline.**
    - Run `.claude/router_eval/run_benchmark.py`, record baseline F1 / token savings in `.claude/router_eval/README.md`.
16. **Tag `v0.1.0` and merge PR #11 / open PR #12.**
    - Final CI green; create annotated tag.

---

## 3. Proposed Execution Order

| Order | Bundle | Task | Est. files | Risk |
|---|---|---|---|---|
| 1 | A | SourceCache integration | 2 | Low |
| 2 | A | Browser adversarial tests | 1 | Low |
| 3 | A | CLI integration tests | 1 | Low |
| 4 | B | `dedup_files.py` + janitor wiring | 2 | Low |
| 5 | B | `github_pr.py` | 1 | Medium (subprocess) |
| 6 | B | `end_session.py` | 1 | Medium (orchestrates scripts) |
| 7 | B | Source adapter integration tests | 1 | Low |
| 8 | C | MCP adapter | 1 | Medium (new interface) |
| 9 | C | Main AI runbook | 1 | Low |
| 10 | C | E2E campaign test | 1 | Medium (end-to-end) |
| 11 | D | Architecture docs + README | 9 | Low |
| 12 | D | Dockerfile (optional) | 2 | Low |
| 13 | D | Security review + eval baseline | process | Medium |
| 14 | D | Tag v0.1.0 + final PR | process | Low |

---

## 4. Acceptance Criteria for “Finished”

- `pytest -q` ≥ 80% coverage, zero failures.
- `ruff check .` clean.
- `mypy src/research_engine` clean.
- Router eval self-checks green.
- E2E campaign test passes with mocked external APIs.
- MCP adapter exposes run + status tools.
- `scripts/end_session.py` can run in dry-run mode end-to-end.
- No hardcoded secrets; security review CRITICAL/HIGH count = 0.
- `README.md` and architecture docs allow a new user to install and run one example campaign in <15 min.
- `v0.1.0` tag exists on `main`.

---

## 5. Decisions Needed

1. **DuckDB corpora / `sources_db.py`:** Master plan listed `storage/sources_db.py` and `storage/cache_db.py`. Current implementation uses `CampaignStore` + `SourceCache` (SQLite). Do we still need a separate DuckDB corpora store for v0.1.0, or is the current storage surface sufficient? **Recommendation:** Defer DuckDB corpora to post-v0.1.0 unless required for the E2E test.
2. **Docker:** Master plan lists Dockerfile as Phase 10.5. Is this required for v0.1.0 or optional? **Recommendation:** Build it; low cost and proves reproducibility.
3. **PR strategy:** Finish work on `phase-5-adversarial` branch and update PR #11, or open a fresh PR #12? **Recommendation:** Open PR #12 from a new `finish-v0.1.0` branch to keep PR #11 scoped to Phases 5–7.

---

## 6. Risks

- **Scope creep:** The master plan has 30+ remaining tasks if interpreted literally. This plan focuses on the v0.1.0 DoD only.
- **Subprocess / Git automation:** `github_pr.py` and `end_session.py` touch real git remotes; must default to dry-run and require explicit `--live`.
- **Security:** Any new file-system or subprocess code triggers §6.6 security review.
- **Time:** Full execution is likely 3–6 hours; the Loop Safety Contract (§6.10) applies.
