# ScoopScope — Project Status

Last updated: 2026-10-14

## Current Status: Milestone 2C Complete

---

## Workspace & Repository Confirmation
- **Canonical Workspace & Git Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\`
- **Active Git Commit Base**: `713a134` (plus Milestone 2C checkpoint)
- **Resolved Path**: No references to stale paths. Clean environment.

---

## Milestone 2C — Real Search Provider, Bounded Retrieval & Passages (COMPLETE)

### 1. Serper Search Provider Implementation (`backend/app/search/serper_provider.py`)
- **API Contract Adherence**: Real provider conforming to the `SearchProvider` runtime-checkable Python `Protocol`.
  - Connects to official `https://google.serper.dev/search` JSON endpoint.
  - Requires `SERPER_API_KEY` provided via environment variable (read via `backend/.env`).
  - Sends query payload `{"q": query, "num": max_results}`.
  - Enforces explicit error mapping:
    - 401: `SearchProviderError("Serper API authentication failed: invalid or missing SERPER_API_KEY")`
    - 403: `SearchProviderError("Serper account credit exhausted or forbidden (403)")`
    - 429: `SearchProviderError("Serper rate limit exceeded (429)")`
    - 5xx / Network timeouts: At most 1 retry (bounded to 2 total requests per search action).
  - Sanitizes all exceptions and logs so `SERPER_API_KEY` is never exposed or logged.
  - Returns `SearchResultHit` items where `is_snippet_only: Literal[True] = True` (permanently frozen).

### 2. Search & Retrieval Budget Enforcement (`backend/app/config.py`, `backend/app/research.py`)
- **Strict User Action Limits**:
  - Exactly one selected claim per research action (`claim_id` mandatory).
  - At most 2 search API requests per action, including retries.
  - At most 5 hits per search query.
  - At most 3 distinct candidate pages fetched per research action (including supplied `source_url` if applicable).
  - Overall monotonic research deadline of 90 seconds covering search, fetch, and extraction.
- **Deduplication & Provenance Preservation**:
  - URLs deduplicated by normalized string comparison; identical URLs are never re-fetched.
  - Distinct URLs are never conflated as independent sources (`source_dependence=SourceDependence.UNKNOWN`).
  - Preserves initial URL, final URL, retrieval timestamp, HTTP status code, resolved IP, redirect count, and raw byte size.
  - Missing dates default strictly to `None` (`publication_date=None`, `event_date=None`).

### 3. Safe Passage Extractor (`backend/app/retrieval/passage_extractor.py`)
- **No Script Execution**: Uses Python's native `html.parser.HTMLParser` without browser engines or JavaScript execution.
- **Readable Text Extraction**: Filters out `<script>`, `<style>`, `<noscript>`, `<nav>`, `<header>`, `<footer>`, `<svg>`, and `<aside>` tags. Unescapes HTML entities cleanly into inert plain text.
- **Programmatic Verbatim Provenance**:
  - Passages are exact verbatim substrings of the decoded `extracted_text`.
  - Records exact character bounds: `start_offset` and `end_offset`.
  - Validated programmatically via `verify_passage_provenance(passage, extracted_text) -> bool` (`extracted_text[start:end] == exact_passage`).
  - Zero LLM generation: Passages are never rewritten, evaluated, or invented by an LLM in this milestone.

### 4. Fetcher Destination Pinning & Deadlines
- `backend/app/retrieval/safe_fetcher.py`:
  - Enforces destination pinning by resolving DNS, checking SSRF rules (`is_public_ip`), and binding socket directly to the validated IP to defeat TOCTOU DNS rebinding.
  - Preserves SNI hostname for strict TLS certificate verification.
  - Sequential connection fallback across resolved public IPs to avoid IPv6 unreachable route failures on dual-stack hosts.
  - Correct monotonic deadline recalculation after DNS resolution and between redirect hops.

### 5. Research Orchestrator & API Endpoint (`backend/app/research.py`, `backend/app/main.py`)
- **Endpoint**: `POST /api/research`
  - Validates request payload (`submission_id`, `claim_id`, `claim_text`, `claim_type`).
  - If `SERPER_API_KEY` is missing in `backend/.env`, returns `HTTP 503 Service Unavailable` with explanatory detail. Never silently falls back to mock search in production.
  - In orchestrator: runs deterministic claim queries, caps hits to 5, deduplicates URLs, fetches up to 3 candidate pages using `SafeFetcher` within the 90s deadline, extracts verbatim candidate passages, and returns structured `ResearchResponse`.

### 6. Frontend UI & State Ownership (`frontend/app.js`, `frontend/style.css`)
- **Target User Experience**:
  - Claim cards render a dedicated "Find sources" button.
  - Clicking "Find sources" transitions button to loading state ("Researching…") with a spinner and 90s notice.
  - Double-clicks and concurrent research actions on the same claim are blocked.
  - Modifying input text or submitting a new text immediately increments `activeResearchSeq` and invalidates any in-flight research, preventing stale results or error states from taking ownership.
  - External search snippets and retrieved pages are presented in distinctly labeled sections:
    - Search Hits: Marked with prominent "Snippet Only #N" badges and disclaimers stating that snippets only indicate index presence and never count as examined evidence.
    - Retrieved Sources: Display source URL, HTTP status, resolved IP, size in KB, redirect count, and audit status (`Retrieved (200)`, `SSRF Blocked`, or `Inaccessible`).
    - Verbatim Passages: Render exact quoted excerpts with character offsets and a "Show surrounding context" toggle.
    - Collapsible Raw Text: "Inspect full extracted page text" toggle lets users audit the complete decoded text.
  - **Inert Text Rendering**: All external titles, URLs, snippets, and passages are set exclusively via `textContent` or `document.createTextNode()`. No raw HTML injection.
  - **Zero Verdicts**: No supported/contradicted verdicts or truth scores are generated or displayed.

---

## Milestone 2B — Search-Provider Contract & Safe URL-Fetching Foundation (COMPLETE)
- `SearchProvider` Protocol and `SearchResultHit` frozen snippet schema.
- Comprehensive SSRF validation: loopback, private ranges, CGNAT (`100.64.0.0/10`), IPv4-mapped IPv6, 6to4, and documentation IPs.
- Socket-level destination pinning, TLS certificate verification, manual 3-hop redirect controller, 1MB decompressed size limit, and strict MIME filter.

---

## Milestone 2A — Validation Reconciliation & Frontend Ordering (COMPLETE)
- Reconciled retry policy to 2 retries (3 total attempts), complying with `AGENTS.md`.
- Reconciled worst-case timeout math (312s overall).
- Request-ordering sequence protection in frontend (`currentSubmissionSeq`).

---

## Milestone 1 Baseline — Claim Extraction Vertical Slice (Prior Evidence)
- Backend structured claim extraction via Gemini structured output (`ClaimExtractionResultLLM`).
- Factual vs. opinion separation, location preservation, and qualification preservation.

---

## Automated Test Suite (115 passing — all fixture-based or mocked)

| Suite | Tests / Assertions | What it covers | Status |
|---|---|---|---|
| `test_extraction.py` | 14 tests | Claim extraction, validation, error handling, unique IDs | PASSED |
| `test_frontend_ordering.py` | 1 test (65 browser assertions) | Headless Chrome browser test: request ordering, stale discard, Try Again, research action, snippet rendering, passage rendering, input/URL modification invalidation (R4), inert text XSS protection | PASSED |
| `test_search_contract.py` | 9 tests | `SearchProvider` Protocol, `SearchResultHit` snippet immutability, date/dependence defaults, query generation | PASSED |
| `test_safe_fetcher.py` | 65 tests | IP ranges, IPv4-mapped IPv6, CGNAT, scheme/standard & bad port/credential validation (R3), public success, private/loopback rejection, public-to-private redirect block, DNS rebinding block, 3-hop redirect limit, MIME rejection, 1MB size limit, cancellable deadline and slow DNS enforcement with elapsed bounds (R2), socket connection enforcement | PASSED |
| `test_serper_provider.py` | 12 tests | Serper contract adherence, missing key handling, search response parsing, 5-hit cap, 401/403/429 status mapping, bounded 5xx retries, outbound attempt accounting, secret redaction | PASSED |
| `test_passage_extractor.py` | 9 tests | Script/style stripping, entity decoding (single decode R1), exact substring offsets, provenance verification, URL deduplication, void element handling (<embed> R1), table cell number separation (R1), plain-text MIME preservation (<exception> R1) | PASSED |
| `test_research_endpoint.py` | 5 tests | Orchestrator flow with mock provider & fetcher (injected DNS R5), candidate page budget cap (3), partial fetch failures, 503 on missing credentials, cancellable orchestrator deadline enforcement (R2), malformed port error isolation (R3) | PASSED |
| **Total** | **115 passed** | Full regression and Milestone 2C capabilities | **ALL PASSED (30.32s)** |

---

## Live vs. Mocked Results Summary

### 1. Mocked & Local Integration Verification (Repaired Snapshot)
- Full orchestrator execution verified offline with mock search provider and mock HTTP network backend.
- DNS resolution injected in offline tests to prevent reliance on host system resolver.
- Candidate budgets (max 2 queries, max 5 hits/query, max 3 fetched pages) verified.
- Programmatic character offsets verified (`extracted_text[start:end] == exact_passage`).
- Headless Chrome browser suite verified with 65 assertions across 8 tests (stale response discard, edit-during-extraction, URL-only edits, edit-during-research, Try Again recovery, research action, inert rendering).

### 2. Prior Live Smoke Results (Historical Builder Evidence)
- The live smoke run against live Gemini and Serper APIs was conducted during the initial Milestone 2C verification pass:
  - Input: `"Mayor Karen Bass took office in December 2022 as the 43rd Mayor of Los Angeles."`
  - Factual claim extracted and researched in 6.26s.
  - Queries: 1 query sent to Serper (1 of 2 allowed search requests).
  - Search hits: 5 hits returned (capped at 5), all marked `is_snippet_only: True`.
  - Candidate pages fetched: 3 pages attempted (limit 3):
    * `https://lacity.gov/news/karen-bass-sworn-43rd-mayor-los-angeles`: **Retrieved** (HTTP 200, IP: `23.48.203.178`, 31,545 bytes).
    * `https://en.wikipedia.org/wiki/Karen_Bass`: **Retrieved** (HTTP 200, IP: `198.35.26.224`, 757,252 bytes).
    * `https://www.nytimes.com/2022/12/12/us/karen-bass-los-angeles-mayor.html`: **Inaccessible** (HTTP 403 Forbidden, IP: `151.101.73.164`, 0 bytes).
  - Verbatim candidate passages: 4 passages extracted. Programmatic character offset check verified 100% exact substring match (`extracted_text[start:end] == exact_passage`).
  - Browser presentation verified via headless Chrome browser subagent with distinct search hit and candidate source groups, collapsible text inspectors, and inert text rendering.
  - Zero verdicts, truth scores, or confidence ratings generated. Zero secrets leaked.
  - Note: In this repair pass, live smoke assertions in `live_smoke_investigation.py` were updated to explicitly assert elapsed time <= 90s, at least 1 retrieved source, and at least 1 extracted passage. Per instructions, live external API calls were not re-executed during this offline repair pass.

---

## Sources Attempted & Successfully Retrieved (Test Fixtures)
- `https://example.com/source-one`: Successfully retrieved (HTTP 200, IP 93.184.216.34, 45 KB), verbatim passage extracted.
- `https://example.com/source-two`: Successfully retrieved (HTTP 200, IP 93.184.216.34, 32 KB), verbatim passage extracted.
- `https://example.com/source-oversize`: Correctly aborted when decompressed byte stream exceeded 1 MB cap; marked `INACCESSIBLE`.
- `http://169.254.169.254/metadata`: SSRF blocked before socket connection; marked `SSRF_BLOCKED`.
- `http://example.com/redirect-to-private`: 302 redirect to `10.0.0.1` blocked at redirect hop; marked `SSRF_BLOCKED`.

---

## Remaining Integration Limitations
1. **No External Live Search Key Configured by Default**: Requires the user to add `SERPER_API_KEY` to `backend/.env` for live queries.
2. **No Verdicts or Truth Scores**: Candidate passages are gathered and displayed for human audit only; no supported/contradicted labels or confidence percentages are computed.
3. **No LLM Passage Summarization or Semantic Filtering**: Passages are extracted via keyword matching and verbatim substring slicing without LLM rewriting.
4. **Dates and Source Dependence Unknown**: Publication dates and source independence remain explicitly unknown unless verifiable metadata is extracted in future milestones.

