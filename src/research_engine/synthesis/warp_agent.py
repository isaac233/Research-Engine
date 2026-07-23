"""WARP native-loop agent — run a trained deep-research report model (AgentCPM-Report)
as the AGENT driving its OWN loop, with our retrieval stack as its Search tool.

Ports AgentCPM-Report's WARP framework (arXiv:2602.06540, Figs 7-10): the model
interleaves Initialize -> (Search -> Write)* -> Expand / Terminate, revising the
outline while it writes. This is the NATIVE loop the model's RACE 50 lives in —
v11 measured that slotting these models PASSIVELY (one section-write call) caps at
~35; the loop's iterative deepening is what drives Insight.

Design: the model emits ``<thought>…</thought><action>…</action>``; this driver
parses the action and executes it. Search actions call injected ``search_fn``
(keywords -> result URLs) + ``read_fn`` (url -> text) — our SearXNG shim + CDP
fetcher — assigning a bibkey per source. Write actions produce prose citing
``\\cite{bibkey}``; we map bibkeys -> ``[eN]`` so the RACE/FACT scorers ingest the
report unchanged. Default path is untouched: this only runs behind an env flag.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from research_engine.llm.provider import LLMProvider, Message

logger = logging.getLogger(__name__)

# Injected retrieval tools (reuse the orchestrator's / a standalone shim).
SearchFn = Callable[[list[str]], list[str]]  # keywords -> result URLs
ReadFn = Callable[[str], str]  # url -> page text

_ACTION_RE = re.compile(r"<action>\s*(.*?)\s*</action>", re.DOTALL | re.IGNORECASE)
_MAX_TOTAL_ACTIONS = 60  # hard non-termination backstop
_READ_CHARS = 2500  # per-source text handed to the writer (smaller = safer for the GGUF template)


def _sanitize(text: str) -> str:
    """Drop control/non-printable chars that can break the model's chat template."""
    return "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")


# --- prompts (verbatim intent from paper Figs 7-10) ---------------------------
_INITIALIZE = """You are a professional report generation expert, skilled at creating high-quality report outlines. \
Analyze the user's question and provide a simple article outline (only top-level sections).
** User Query ** {query}
** Latest Retrieved Information ** {info}
## Notes
1. The outline must be comprehensive, logically sound, and aligned with the user's requirements.
2. The output language must match the user's query.
** Available Actions **
- initialize: Generate the top-level section outline plus an appropriate title.
## Action Format:
<action> {{"name": "initialize", "title": "...", "sections": [{{"title": "...", "plan": "..."}}]}} </action>
** Output Format ** <thought> reasoning </thought><action> Action (JSON) </action>
Output strictly in the specified format."""

_SEARCH = """You are a searcher. Select the most accurate search keywords (one to five) based on the user's query, \
the current outline, and the writing instruction. Same language as the query.
** User Query ** {query}
** Current Article Outline ** {outline}
** Instruction ** {instruction}
## Action Example:
<action> {{"name": "search", "keywords": ["keyword-1", "keyword-2"]}} </action>
** Output Format ** <thought> reasoning </thought><action> Action (JSON) </action>
Output strictly in the specified format."""

_WRITE = """You are a writer. Based on the instruction, the current writing status, and the retrieved information, \
compose ONE new paragraph with breadth and depth — analytical and comparative, not a bare summary. Tables and \
examples are encouraged. Do not write other sections.
BE FAITHFUL: every claim, especially facts and numbers, must be supported by the retrieved information you cite. \
Cite with \\cite{{bibkey}} (or \\cite{{bibkey1, bibkey2}}). Same language as the query.
** User Query ** {query}
** Current Article Summary ** {draft}
** Instruction ** {instruction}
** Retrieved Information ** {info}
## Action Example: <action> content </action>
** Output Format ** <thought> reasoning </thought><action> Your paragraph in Markdown, with \\cite{{bibkey}} </action>
Output strictly in the specified format."""

_EXPAND = """You are a report-generation expert. Decide whether any section needs expansion into subsections.
## Notes
1. Select only the single section most in need of expansion.
2. If no expansion is needed, output a terminate action.
3. Expand only one hierarchy level at a time; do not re-expand an already-expanded section.
4. Keep new subsections relevant, non-redundant, coherent.
** User Query ** {query}
** Current Full Report ** {draft}
## Action Format:
<action> {{"name": "expand", "position": "section-x", "subsections": [{{"title": "...", "plan": "..."}}]}} </action>
<action> {{"name": "terminate"}} </action>
** Output Format ** <thought> reasoning </thought><action> Action (JSON) </action>
Output strictly in the specified format."""


@dataclass
class Section:
    title: str
    plan: str
    written: bool = False


@dataclass
class WarpResult:
    title: str
    markdown: str  # report with [eN] citations
    sources: list[dict[str, str]]  # [{"id": "e1", "url": ..., "text": ...}]
    actions: int
    expands: int
    bibmap: dict[str, str] = field(default_factory=dict)  # bibkey -> eN


def _extract_action(text: str) -> str:
    """Return the raw <action> body, or '' if absent."""
    m = _ACTION_RE.search(text or "")
    return m.group(1).strip() if m else ""


def _parse_json_action(body: str) -> dict[str, Any] | None:
    """Parse a JSON action body ({name: ...}); None if not JSON."""
    body = body.strip()
    if not body.startswith("{"):
        return None
    try:
        obj = json.loads(body)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        # tolerate trailing prose: take the outermost balanced {...}
        depth = 0
        for i, ch in enumerate(body):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(body[: i + 1])
                        return obj if isinstance(obj, dict) else None
                    except (json.JSONDecodeError, ValueError):
                        return None
        return None


class WarpAgent:
    """Drives AgentCPM-Report's WARP loop with injected retrieval tools."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        search_fn: SearchFn,
        read_fn: ReadFn,
        max_expands: int = 8,
        per_search_k: int = 4,
        max_tokens: int = 4000,
    ) -> None:
        self.provider = provider
        self.model = model
        self.search_fn = search_fn
        self.read_fn = read_fn
        self.max_expands = max_expands
        self.per_search_k = per_search_k
        self.max_tokens = max_tokens
        self._bib: dict[str, tuple[str, str]] = {}  # bibkey -> (url, text)
        self._bib_order: list[str] = []
        self._actions = 0

    def _complete(self, prompt: str) -> str:
        """One action call; resilient to a transient provider error (e.g. an
        occasional Ollama 400 on this GGUF's template) — retry once, then degrade
        to '' so the loop skips that action instead of crashing the whole run."""
        self._actions += 1
        for attempt in range(2):
            try:
                return self.provider.complete(
                    [Message(role="user", content=prompt)],
                    model=self.model,
                    temperature=0.0,
                    max_tokens=self.max_tokens,
                )
            except Exception as e:  # noqa: BLE001
                if attempt == 0:
                    continue
                logger.warning("WARP action call failed (skipping): %r", e)
                return ""
        return ""

    def _do_search(self, keywords: list[str], instruction: str) -> str:
        """Run one Search: keywords -> URLs -> text, assign bibkeys, format context."""
        urls = self.search_fn(keywords)[: self.per_search_k]
        chunks: list[str] = []
        for url in urls:
            if url in {u for u, _ in self._bib.values()}:  # already fetched
                bib = next(b for b, (u, _) in self._bib.items() if u == url)
                text = self._bib[bib][1]
            else:
                text = (self.read_fn(url) or "").strip()
                if not text:
                    continue
                text = _sanitize(text)[:_READ_CHARS]
                bib = f"s{len(self._bib_order) + 1}"
                self._bib[bib] = (url, text)
                self._bib_order.append(bib)
            chunks.append(f"[{bib}] ({url})\n{text}")
        return "\n\n".join(chunks) if chunks else "(no results)"

    def run(self, query: str) -> WarpResult:
        # 1. Initialize: one broad search then the Level-1 outline.
        seed_info = self._do_search([query], "initial scoping")
        init_raw = self._complete(_INITIALIZE.format(query=query, info=seed_info[:_READ_CHARS]))
        init = _parse_json_action(_extract_action(init_raw)) or {}
        title = str(init.get("title") or query)
        sections = [
            Section(title=str(s.get("title", "")), plan=str(s.get("plan", "")))
            for s in (init.get("sections") or [])
            if isinstance(s, dict) and s.get("title")
        ]
        if not sections:  # degrade: single section
            sections = [Section(title=title, plan=query)]

        draft_parts: list[str] = [f"# {title}\n"]
        expands = 0
        # 2. Draft each section (Search -> Write); 3. Deepen (Expand/Terminate).
        i = 0
        while i < len(sections) and self._actions < _MAX_TOTAL_ACTIONS:
            sec = sections[i]
            i += 1
            if sec.written:
                continue
            instruction = f"Write section: {sec.title}. Plan: {sec.plan}"
            outline_str = "\n".join(f"- {s.title}" for s in sections)
            # Search
            kw_raw = self._complete(
                _SEARCH.format(query=query, outline=outline_str, instruction=instruction)
            )
            kw = _parse_json_action(_extract_action(kw_raw)) or {}
            keywords = [str(k) for k in (kw.get("keywords") or [sec.title])][:5] or [sec.title]
            info = self._do_search(keywords, instruction)
            # Write
            draft_so_far = "\n\n".join(draft_parts)[-6000:]
            write_raw = self._complete(
                _WRITE.format(query=query, draft=draft_so_far, instruction=instruction, info=info)
            )
            body = _extract_action(write_raw) or _strip_thought(write_raw)
            sec.written = True
            draft_parts.append(f"## {sec.title}\n\n{body.strip()}")

            # Deepen only after all current sections drafted
            if i >= len(sections) and expands < self.max_expands:
                full = "\n\n".join(draft_parts)
                exp_raw = self._complete(_EXPAND.format(query=query, draft=full[:12000]))
                exp = _parse_json_action(_extract_action(exp_raw)) or {"name": "terminate"}
                if exp.get("name") == "expand":
                    subs = [
                        Section(title=str(s.get("title", "")), plan=str(s.get("plan", "")))
                        for s in (exp.get("subsections") or [])
                        if isinstance(s, dict) and s.get("title")
                    ]
                    if subs:
                        sections.extend(subs)
                        expands += 1
                # terminate => fall out of the loop naturally

        markdown, sources, bibmap = self._finalize("\n\n".join(draft_parts))
        return WarpResult(
            title=title, markdown=markdown, sources=sources,
            actions=self._actions, expands=expands, bibmap=bibmap,
        )

    def _finalize(self, draft: str) -> tuple[str, list[dict[str, str]], dict[str, str]]:
        r"""Map \cite{bibkey} -> [eN] for cited-and-fetched bibkeys; build sources + References."""
        cited = _cited_bibkeys(draft)
        bibmap: dict[str, str] = {}
        sources: list[dict[str, str]] = []
        for bib in self._bib_order:
            if bib not in cited or bib not in self._bib:
                continue
            eid = f"e{len(sources) + 1}"
            bibmap[bib] = eid
            url, text = self._bib[bib]
            sources.append({"id": eid, "url": url, "text": text})

        def _repl(match: re.Match[str]) -> str:
            keys = [k.strip() for k in match.group(1).split(",")]
            eids = [f"[{bibmap[k]}]" for k in keys if k in bibmap]
            return "".join(eids)

        body = re.sub(r"\\cite\{([^}]*)\}", _repl, draft)
        if sources:
            refs = "\n".join(f"[{s['id']}] {s['url']}" for s in sources)
            body = f"{body}\n\n## References\n{refs}"
        return body, sources, bibmap


def _strip_thought(text: str) -> str:
    """Remove <think>/<thought> blocks (AgentCPM emits them) leaving the content."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def _cited_bibkeys(draft: str) -> set[str]:
    keys: set[str] = set()
    for m in re.finditer(r"\\cite\{([^}]*)\}", draft):
        keys.update(k.strip() for k in m.group(1).split(",") if k.strip())
    return keys


def run_warp(
    query: str,
    provider: LLMProvider,
    model: str,
    search_fn: SearchFn,
    read_fn: ReadFn,
    **kwargs: Any,
) -> WarpResult:
    return WarpAgent(provider, model, search_fn, read_fn, **kwargs).run(query)
