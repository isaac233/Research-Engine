# Main AI Integration Runbook

This runbook explains how a main AI (Claude Code, Opus, Kimi, etc.) launches the
Research Engine as a tool via the MCP/stdio adapter and consumes its deliverables.

---

## 1. What the MCP adapter exposes

`src/research_engine/mcp_adapter.py` runs a stdio MCP server with two tools:

| Tool | Arguments | Returns |
|---|---|---|
| `research_engine_run` | `query: str`, optional `project_root: str` | Campaign ID, slug, status, stage, and path to the generated insight brief |
| `research_engine_status` | `campaign_id: str`, optional `project_root: str` | Current stage, progress %, ETA, remaining stages, and alerts |

The adapter is launched as a separate process; the main AI communicates with it
over JSON-RPC on stdin/stdout.

---

## 2. Install and configure

1. Install the package:

   ```powershell
   pip install -e .
   ```

2. (Optional) Install the MCP SDK if it is not already present:

   ```powershell
   pip install mcp>=1.0
   ```

3. Register the adapter in your MCP client config. For Claude Code, add a block
   similar to this to your MCP settings:

   ```json
   {
     "mcpServers": {
       "research-engine": {
         "command": "python",
         "args": [
           "-m",
           "research_engine.mcp_adapter"
         ],
         "cwd": "C:/Users/Isaac/OneDrive/Desktop/beta/Research Engine"
       }
     }
   }
   ```

   Adjust `cwd` to the directory where the engine is installed.

---

## 3. Running a campaign

From the main AI, invoke the `research_engine_run` tool with a plain-language
research request.

### Example prompts

- *"Run a research campaign: What are the latest methodological improvements in
  LLM systematic literature reviews?"*
- *"Research this blocker for me: find a free public API for real-time U.S.
  treasury yield data."*
- *"Use the Research Engine to investigate whether retrieval-augmented
  generation reduces hallucination in medical QA benchmarks."*

The engine will:

1. Plan the request into source-specific queries.
2. Search Semantic Scholar, Crossref, arXiv, OpenAlex, and optional SERP/web crawl.
3. Deduplicate, rank, and extract structured insights.
4. Run the adversarial `Devil` + `Verifier` chain on every claim.
5. Write `Research/<slug>/<slug>_Insights.MD` and regenerate `Research/Insights.MD`
   in the host project.

### Expected tool result

```json
{
  "campaign_id": "cmp-abc123",
  "slug": "LLM_SLR_Methods",
  "status": "completed",
  "stage": "DELIVER",
  "campaign_dir": "/path/to/host/Research/LLM_SLR_Methods",
  "insights_path": "/path/to/host/Research/LLM_SLR_Methods/LLM_SLR_Methods_Insights.MD"
}
```

---

## 4. Querying status while a campaign runs

Long campaigns can take minutes. Poll with `research_engine_status`:

```json
{
  "campaign_id": "cmp-abc123"
}
```

Expected result:

```json
{
  "campaign_id": "cmp-abc123",
  "stage": "DISCOVER",
  "status": "running",
  "progress_percent": 35,
  "eta_seconds": 180,
  "remaining_stages": ["SCREEN", "EXTRACT", "ADVERSARIAL", "EVALUATE", "DELIVER"],
  "alerts": []
}
```

If the engine reports a stuck stage or repeated failure, the main AI should ask
for a status dump and decide whether to pause, kill, or escalate to a frontier
model.

---

## 5. Reading the deliverable

After the campaign finishes:

1. Open `Research/<slug>/<slug>_Insights.MD`.
2. Verify the numbered claims, evidence URLs, confidence labels, and caveats.
3. Read the folded master brief at `Research/Insights.MD` for cross-campaign
   context.

The main AI should not forward unverified claims to the user. If the `Devil` or
`Verifier` raised unresolved challenges, the brief flags them and the main AI can
ask the engine to re-run the affected stage or escalate to a frontier model.

---

## 6. Unblocking campaigns

If the main AI previously told the user *"I cannot find…"*, phrase the request
as a blocker query. The engine classifies it as an unblocking campaign and
searches for concrete solutions, access terms, and next steps.

Example:

- *"Find a free, public data source for U.S. county-level health statistics with
  an API or bulk download."*

The deliverable will include:

- A restatement of the blocker.
- Ranked solutions with URLs, access terms, and constraints.
- Exact commands, endpoints, or sign-up links where applicable.
- A recommended next action and confidence label per item.

The engine is not allowed to return a brief that says *"no solution found"*. If
it cannot find a solution, it escalates to a frontier model with a full
evidence log.

---

## 7. Safety and trust boundaries

- The engine only hits public or authorized sources; robots.txt, rate limits,
  and the SSRF policy are enforced.
- No credential bypass, no paywall evasion, no anti-bot deception.
- Every claim is challenged before delivery; unresolved challenges appear in the
  brief.
- The main AI should treat the brief as **adversarially reviewed evidence**, not
  as final truth, and present caveats alongside claims.

---

## 8. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `research_engine_run` times out | Long campaign; poll status | Call `research_engine_status` |
| Status shows repeated `DISCOVER` failures | External source rate limit or robots block | Wait and retry; check `config/default.yaml` |
| `Devil` challenges are high | Weak source evidence or missing full text | Re-run with a narrower query |
| MCP server fails to start | `mcp` package missing | `pip install mcp>=1.0` |
| `Campaign not found` | Wrong campaign ID | Use the ID returned by `research_engine_run` |
