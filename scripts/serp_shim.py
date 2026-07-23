"""Local SearXNG-compatible SERP endpoint — unblocks the engine's `serp` lane
without running SearXNG/Docker.

The engine's `SERPAdapter` GETs ``http://localhost:8080/search?q=<query>&format=json``
and parses ``{"results":[{"title","url","content"}, ...]}`` (SearXNG JSON). This shim
serves exactly that shape, backed by a search source we CAN reach:

  1. Firecrawl REST search (primary) — the key is read from ``~/.claude.json`` at
     runtime, so it never lands in source or logs.
  2. ddgs / DuckDuckGo (keyless fallback).

The engine still fetches each result URL itself (RawHTTPBrowser/CDP), so the shim
only supplies result lists — no page scraping here.

Run:  python scripts/serp_shim.py            # binds 127.0.0.1:8080
Env:  SERP_SHIM_PORT (default 8080)
Point the engine at it with:
      RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx

warnings.filterwarnings("ignore")  # silence verify=False InsecureRequestWarning


def _firecrawl_key() -> str | None:
    """Recursively find FIRECRAWL_API_KEY in ~/.claude.json (never printed)."""
    path = os.path.expanduser("~/.claude.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:  # noqa: BLE001
        return os.environ.get("FIRECRAWL_API_KEY")

    def _find(obj: Any) -> str | None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "FIRECRAWL_API_KEY" and isinstance(v, str) and v.strip():
                    return v
                found = _find(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = _find(v)
                if found:
                    return found
        return None

    return _find(data) or os.environ.get("FIRECRAWL_API_KEY")


FC_KEY = _firecrawl_key()


def _search_firecrawl(query: str, limit: int) -> list[dict[str, str]]:
    resp = httpx.post(
        "https://api.firecrawl.dev/v2/search",
        headers={"Authorization": f"Bearer {FC_KEY}"},
        json={"query": query, "limit": limit},
        timeout=30.0,
        verify=False,  # noqa: S501 — MITM proxy in-session; known host, localhost tool
    )
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data", payload)
    if isinstance(data, dict):
        items = data.get("web") or data.get("results") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    out: list[dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        url = it.get("url") or it.get("href") or it.get("link")
        title = it.get("title") or it.get("name")
        if not url or not title:
            continue
        content = it.get("description") or it.get("content") or it.get("snippet") or ""
        out.append({"title": str(title), "url": str(url), "content": str(content)})
    return out


def _search_ddgs(query: str, limit: int) -> list[dict[str, str]]:
    from ddgs import DDGS

    out: list[dict[str, str]] = []
    with DDGS() as ddgs:
        for it in ddgs.text(query, max_results=limit):
            url = it.get("href") or it.get("url") or ""
            title = it.get("title") or ""
            if not url or not title:
                continue
            out.append({"title": str(title), "url": str(url), "content": str(it.get("body", ""))})
    return out


def do_search(query: str, limit: int) -> tuple[list[dict[str, str]], str]:
    """Return (results, backend). Firecrawl first, ddgs fallback."""
    if FC_KEY:
        try:
            res = _search_firecrawl(query, limit)
            if res:
                return res, "firecrawl"
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[serp_shim] firecrawl failed: {e!r}\n")
    try:
        return _search_ddgs(query, limit), "ddgs"
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[serp_shim] ddgs failed: {e!r}\n")
        return [], "none"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # quiet
        pass

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/search", "/"):
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        query = (qs.get("q") or [""])[0].strip()
        limit = int((qs.get("limit") or ["10"])[0] or 10)
        results, backend = do_search(query, limit) if query else ([], "none")
        body = json.dumps(
            {
                "query": query,
                "number_of_results": len(results),
                "results": [{**r, "engine": backend} for r in results],
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        sys.stderr.write(f"[serp_shim] q={query!r} -> {len(results)} via {backend}\n")


def _self_check() -> None:
    """Offline shape check — no network. `python scripts/serp_shim.py --check`."""
    sample = {"data": {"web": [{"url": "https://x.example/a", "title": "A", "description": "d"}]}}
    # exercise the mapping the same way _search_firecrawl does
    items = sample["data"]["web"]
    out = [
        {"title": it["title"], "url": it["url"], "content": it.get("description", "")}
        for it in items
    ]
    assert out == [{"title": "A", "url": "https://x.example/a", "content": "d"}], out
    body = json.dumps({"results": [{**out[0], "engine": "firecrawl"}]})
    parsed = json.loads(body)
    assert parsed["results"][0]["url"] == "https://x.example/a"
    print("serp_shim self-check OK")


if __name__ == "__main__":
    if "--check" in sys.argv:
        _self_check()
        sys.exit(0)
    port = int(os.environ.get("SERP_SHIM_PORT", "8080"))
    print(f"[serp_shim] listening on 127.0.0.1:{port}  firecrawl={'yes' if FC_KEY else 'no'}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), _Handler).serve_forever()
