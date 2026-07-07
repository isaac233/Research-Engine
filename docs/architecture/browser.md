# Browser

The browser is an AI-only HTTP/automation layer. It performs every outbound
request the engine makes on behalf of the user and enforces a hard safety
policy so the engine cannot reach private infrastructure.

## Components

- `AIBrowser` — facade: chooses between headless browser (CDP/Playwright) and
  raw HTTP client based on target type.
- `BrowserRouter` — context firewall: decides when to route to raw HTTP,
  headless rendering, GraphQL/API helpers, or an adapter-specific raw client.
- `URLPolicy` — SSRF/ethical policy: dotted-IP normalization, credential
  blocking, public-only URLs, and robots.txt/ToU checks.
- `RobotsChecker` — robots.txt cache and crawl-delay enforcement.
- `SourceCache` — upstream call deduplication keyed by normalized URL + query.

## SSRF guards

- Reject loopback, link-local, multicast, and private address spaces.
- Reject URLs containing embedded credentials.
- Resolve hostnames to IPs before connecting; block internal-facing DNS.
- Normalize dotted-decimal IP forms (e.g., `0x7f.0.0.1`).
- Maintain an allow-list of safe URL schemes (`http`, `https`).

## Ethical guards

- Respect `robots.txt`.
- Obey `Crawl-Delay` and per-host rate limits.
- Add a clear user-agent identifying the Research Engine.
- Refuse to submit forms, perform logins, or execute client-side code on
  untrusted pages.

## Usage

Adapters do not make direct network calls. They call `AIBrowser.get()` or
`AIBrowser.crawl()` and rely on the browser layer to apply policy and caching.
