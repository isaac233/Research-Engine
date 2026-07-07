# Research Engine — Project Standards

> **Status:** Living document derived from `Research Engine Prompt1.MD`.  
> **Purpose:** Capture the organizational, quality, security, and operational standards that must be upheld in every change to the Research Engine project.  
> **Usage:** Review this document **before starting** any work and **after completing** any work to verify compliance. Treat deviations as defects to be corrected before merge.

---

## 1. Project Organization Standards

The codebase must always look like it is a week away from launch, even in the middle of construction.

### 1.1 No dead or stranded artifacts
- [ ] No orphaned files that are not imported, referenced, or documented.
- [ ] No dead branches left unpurged on the remote after merge.
- [ ] No commented-out code blocks left behind.
- [ ] No temporary debug `print()` statements or `DEBUG` markers committed.
- [ ] No `.tmp`, `.log`, or scratch files committed unless they are part of a documented fixture.

### 1.2 File and directory hygiene
- [ ] Files are organized by feature/domain, not by type.
- [ ] Each source file has a single, clear responsibility.
- [ ] File length is kept under **800 lines**; typical range is **200–400 lines**.
- [ ] Function length is kept under **50 lines**.
- [ ] Naming follows the active codebase convention (`snake_case` functions, `PascalCase` types, `is`/`has`/`should` boolean prefixes).
- [ ] Constants live in `UPPER_SNAKE_CASE`.

### 1.3 Documentation parity
- [ ] New subsystems include an architecture note under `docs/architecture/`.
- [ ] New operational workflows include a runbook under `docs/runbooks/`.
- [ ] Significant decisions are recorded under `docs/plan/decisions/` as an ADR.
- [ ] `HANDOFF.md` is updated at the end of every session with:
  - What problems were fixed and how.
  - What problems remain open, in priority order.
  - The next priority tasks and their owners.
  - The current position in the master plan (`docs/plan/master_plan.md`).
  - Any blockers and what is needed to unblock them.
- [ ] `README.md` remains accurate enough for a new user to install and run one example campaign in **< 15 minutes**.

---

## 2. Planning & Execution Standards

### 2.1 Planning is mandatory for non-trivial work
- [ ] Any task touching **> 3 files** or adding meaningful functionality starts with an excruciatingly granular plan.
- [ ] The plan identifies files that **must** change and stops there (no scope creep).
- [ ] The plan includes a definition of done and a verification/stopping condition.
- [ ] The planner agent or `feature-dev:code-architect` is consulted for large features.

### 2.2 No surrender to uncertainty
- [ ] "I don't know how" is not an acceptable stopping point; research unknown approaches, libraries, or protocols until a viable path is found.
- [ ] Refusal due to ethical, legal, security, or out-of-scope boundaries is mandatory and must be clearly stated.
- [ ] If a library, protocol, or integration is unfamiliar, read its docs or use `context7`/`WebSearch` before writing code.
- [ ] Load-bearing assumptions are named; low-confidence assumptions are validated before commit.

### 2.3 Find-skills exhaustion
- [ ] Before inventing a custom solution, check whether an existing skill, agent, pattern, or third-party tool solves the problem.
- [ ] Prefer composition over bespoke boilerplate.

---

## 3. Router & Token Efficiency Standards

The project must maintain a self-improving, non-self-poisoning router that minimizes token burn as the project scales.

### 3.1 Router maintenance
- [ ] The router agent under `.claude/agents/` and learned routes under `.claude/research-engine-routes.md` are kept current with new subsystems.
- [ ] Router keyword tables are updated when new modules, commands, or concepts are added.
- [ ] The router evaluation harness under `.claude/router_eval/` remains isolated from `src/` and all self-checks pass.
- [ ] New subsystems are represented in the router so future agents do not load the entire codebase by default.

### 3.2 Cost routing
- [ ] Use the cheapest capable tier for the task (Ollama/Haiku → Sonnet → Opus → Human).
- [ ] Escalate only on a named signal: lint/type failures, multi-file coordination, planning, security, architecture, or adversarial review.
- [ ] Never use lightweight models for secrets, auth, payments, or PHI.

---

## 4. AI-Only Browser & Research Standards

The browser is built for AI consumption, not human convenience. It must operate beneath the UI layer where advantageous and always within legal and ethical bounds.

### 4.1 Browser design
- [ ] The browser exposes no human-oriented features that do not serve an AI-driven research workflow.
- [ ] It supports direct server-to-server interaction: raw HTTP, GraphQL, API-first adapters, and CDP/Playwright page-level access.
- [ ] It prefers non-UI layers when they yield better data fidelity or source access (e.g., API endpoints, source branches, structured feeds).
- [ ] It never relies on a single access path; unblocking probes document evidence for every fallback.

### 4.2 Research depth
- [ ] Discovery must retrieve full-text or methodology sections, not just abstracts, before claiming an insight.
- [ ] The pipeline differentiates between initial discovery and deep verification passes.
- [ ] Sources are scored by evidence quality, not merely by match count.

### 4.3 Ethical and legal boundaries
- [ ] All access must be **publicly available** or **explicitly authorized** by the data owner.
- [ ] Access that is merely "technically possible" but not public or authorized is **out of scope** and must be rejected by the URL policy and review gates.
- [ ] For publicly available endpoints, use polite automation: rate limiting, header rotation, robots.txt respect, and the SSRF/URL policy to avoid unnecessary disruption.
- [ ] The SSRF/URL policy blocks private IPs, loopback, multicast, reserved ranges, file schemes, IDNA homoglyphs, and URL-encoded bypass attempts.
- [ ] "Advanced research techniques" are limited to: API-first discovery, structured data extraction, archive/search discovery, metadata analysis, and authorized defensive penetration testing. Any expansion of this list requires a documented authorization scope and a `security-reviewer` pass.
- [ ] A clear audit trail exists for every external request (URL, timestamp, reason, source).

---

## 5. Security & Adversarial Standards

Primitive AI has an incentive to hide mistakes. The project must challenge itself continuously.

### 5.1 Built-in adversarial review
- [ ] Every non-trivial change (row 3+ blast radius, security-sensitive, architecture, or public API) runs `code-reviewer` + `security-reviewer` + a devil's advocate in parallel.
- [ ] The `adversarial/` subsystem challenges claims, verifies evidence, and flags weak excuses.
- [ ] The `evaluation/` subsystem measures claim quality, citation fidelity, and coverage.
- [ ] `ImprovementProposer` emits candidate learned-route deltas; it never auto-applies them.

### 5.2 Deep audit by frontier models
- [ ] A frontier-model deep audit runs periodically against `adversarial/`, `evaluation/`, error-reporting, and logging pipelines to detect silent crippling.
- [ ] Audit findings are tracked as issues and resolved before the next release.

### 5.3 Security-sensitive gates
- [ ] Auth, authorization, user input, DB queries, file system ops, external APIs, crypto, and payments trigger an immediate `security-reviewer` pass.
- [ ] No hardcoded secrets. Secrets are env vars or secret-manager backed.
- [ ] Error messages do not leak internal IPs, paths, secrets, or stack traces to untrusted callers.
- [ ] `bandit -r src` returns **zero HIGH/CRITICAL** findings before merge.

---

## 6. Monitoring & Telemetry Standards

Progress must be observable, estimable, and self-improving.

### 6.1 Campaign observability
- [ ] A research campaign reports:
  - Exact percentage complete.
  - Estimated time until completion.
  - Current stage.
  - Brief list of remaining steps.
- [ ] The dashboard (`dashboard.py`) aggregates status, stage durations, and per-campaign summaries.

### 6.2 Self-improving estimates
- [ ] Time estimates are calibrated against observed stage durations.
- [ ] If estimates are wrong after completion, the discrepancy is investigated and the calibrator is updated.
- [ ] The monitoring subsystem is treated as a first-class feature with its own tests.

---

## 7. Source Management & Conversion Standards

### 7.1 Source persistence
- [ ] Source documents are saved as **Markdown** or **database** files to minimize storage.
- [ ] Downloaded artifacts are preserved in their original format when conversion would corrupt them.
- [ ] If conversion is lossy, the original is retained alongside the converted copy.
- [ ] File conversion utilities are improved when they fail, rather than silently accepting lossy output.

### 7.2 Deduplication and cleanup
- [ ] The `cleanup/` subsystem removes temporary caches at the end of every session.
- [ ] Duplicate files are deduplicated while keeping at least one canonical copy.
- [ ] SQLite state DB is vacuumed; research artifacts are untouched.

---

## 8. Model Agnosticism & Integration Standards

### 8.1 Universal compatibility
- [ ] The engine is model agnostic: local Ollama, Anthropic Opus, and any future provider plug in through the same `LLMProvider` ABC.
- [ ] Optional provider clients are lazily imported so importing the registry does not require every runtime dependency.
- [ ] It works with Claude Code (Opus 4.8, Kimi K2.7, etc.) but ships out-of-the-box for users with different models.

### 8.2 Main AI interface
- [ ] The primary interface is through the main AI (Claude), not direct user chat with the Research Engine.
- [ ] The MCP adapter exposes `research_engine_run` and `research_engine_status` tools.
- [ ] Status queries return percentage, ETA, stage, and remaining steps as if the main AI were doing the work itself.

---

## 9. Session Ritual & Git Standards

### 9.1 End-of-session ritual
- [ ] At the end of every session:
  1. Run janitor cleanup.
  2. Update `HANDOFF.md` with problems fixed, open problems, next tasks, master-plan position, and blockers.
  3. Run `pytest -q`, `mypy src/research_engine`, `ruff check .`, and router eval self-checks.
  4. Commit changes on a feature branch.
  5. Push and open a pull request.
- [ ] `scripts/end_session.py` defaults to dry-run; `--live` is required for real git/GitHub operations.
- [ ] Refuse to run end-of-session directly on `main` without `--allow-main`.

### 9.2 Pull request discipline
- [ ] Work happens on feature branches, not `main`.
- [ ] PRs include a clear title, summary, and verification checklist.
- [ ] CI must be green before merge.
- [ ] After merge, the feature branch is deleted locally and remotely.

### 9.3 Commit discipline
- [ ] Commit messages follow `type: description` format (`feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`).
- [ ] No co-author/tool trailers (attribution disabled globally).
- [ ] No `--no-verify` unless explicitly requested.

---

## 10. Quality Verification Checklist

Review this checklist **before starting** and **after completing** any change.

### Before starting
- [ ] Read `Standards.MD` (this document) for the current task's relevant sections.
- [ ] Check `HANDOFF.md` for open items and context.
- [ ] Identify blast radius (row 1–4) and required reviewers.
- [ ] Confirm the cheapest capable tool/agent for the task.
- [ ] Name load-bearing assumptions and how to validate them.

### During implementation
- [ ] Follow immutable-update patterns; do not mutate in place.
- [ ] Validate input at every system boundary.
- [ ] Handle errors explicitly; never silently swallow exceptions.
- [ ] Keep functions < 50 lines and files < 800 lines.
- [ ] Avoid nesting > 4 levels; use early returns.
- [ ] Replace magic numbers with named constants.

### Before declaring done
- [ ] `pytest -q` passes with ≥ 80% coverage.
- [ ] `mypy src/research_engine` is clean.
- [ ] `ruff check .` is clean.
- [ ] `.claude/router_eval/*.py` self-checks are green.
- [ ] `bandit -r src` shows **zero HIGH/CRITICAL** findings.
- [ ] No secrets, debug prints, or commented-out code remain.
- [ ] `HANDOFF.md` is updated.
- [ ] For row 3+ changes: code-reviewer, security-reviewer, and devil's-advocate have run with majority approval.
- [ ] For UI/security/architecture/public-API changes: task-completion validator and adversarial review passed.

---

## 11. Compliance Statement

Every contributor and agent working on this codebase is expected to uphold these standards. A change that passes tests but violates the standards is **not done**. When in doubt, favor clarity, safety, and organization over speed.
