# ScoopScope — Project Status

Last updated: 2026-10-13

## Current Status: Milestone 2B Complete

---

## Workspace & Repository Confirmation
- **Canonical Workspace & Git Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\`
- **Resolution**: Stale references to `c:\Users\minhb\Projects\ScoopScope\` across `AGENTS.md`, `README.md`, and `tests/live_validation.py` were reconciled. `c:\Users\minhb\Projects` does not exist on disk; there are no duplicate or conflicting copies.

---

## Milestone 2B — Search-Provider Contract & Safe URL-Fetching Foundation (COMPLETE)

### 1. Search Contract & Schemas (`backend/app/search/`)
- **Replaceable Interface**: `SearchProvider` runtime-checkable Python `Protocol` in `app/search/provider.py` with standard `search(query, max_results)` signature and `SearchProviderError`.
- **Strictly Separated Records** in `app/search/models.py`:
  - `ClaimLinkedQuery`: Query linked to `claim_id` with `query_intent` and ISO 8601 timestamp.
  - `RawSearchResult`: Raw hit from provider with rank, title, url, snippet, and engine identifier.
  - `SearchResultHit`: Search hit record where `is_snippet_only: Literal[True] = True` (permanently frozen; cannot be constructed or altered to False).
  - `RetrievedSource`: Fetch audit record capturing `status` (`SourceFetchState`), `final_url`, `resolved_ip`, `http_status_code`, `content_type`, `response_size_bytes`, `redirect_count`, and `extracted_text`.
  - `EvidencePassage`: Verbatim excerpt from a `RETRIEVED` source, defaulting missing dates (`publication_date=None`, `event_date=None`) and unknown source dependence (`source_dependence=SourceDependence.UNKNOWN`).
- **Test-Only Mock Isolation**: `MockSearchProvider` resides strictly in `backend/tests/test_search_contract.py`. Production application settings and adapters never default or silently fall back to mock search.
- **No LLM in Query Generation Tests**: Query construction tests verify deterministic template generation without LLM calls.

### 2. Safe URL Fetcher (`backend/app/retrieval/safe_fetcher.py`)
- **Protocol & Port Enforcement**:
  - Only `http` and `https` schemes permitted.
  - Standard ports only (80 for HTTP, 443 for HTTPS).
  - Embedded credentials (`http://user:pass@host`) strictly rejected.
- **Comprehensive IP & SSRF Protection (`is_public_ip`)**:
  - Validates IPv4 and IPv6 destinations against private, loopback, link-local, multicast, unspecified, reserved, and documentation ranges.
  - Blocks Carrier-Grade NAT (`100.64.0.0/10`).
  - Detects and unwraps IPv4-mapped IPv6 bypasses (`::ffff:127.0.0.1`, `::ffff:7f00:1`, `::ffff:169.254.169.254`).
  - Detects IPv4-compatible IPv6 (`::127.0.0.1`) and 6to4 embedded private IPs (`2002:7f00:0001::`).
- **Socket-Level Connection Enforcement (`SafeNetworkBackend`)**:
  - Resolves destination IP and validates against SSRF rules at connection time.
  - Binds the socket directly to the validated IP, eliminating Time-Of-Check to Time-Of-Use (TOCTOU) DNS rebinding attacks.
  - Preserves origin hostname in `start_tls(server_hostname=...)` for SNI and TLS certificate verification (TLS verification is never disabled).
  - Re-evaluates destination IP when DNS changes between validation and connection.
  - Rejects environment proxies (`trust_env=False`) so proxies cannot bypass local destination enforcement.
- **Manual Redirect Controller**:
  - Automatic redirects disabled. Follows up to 3 hops manually.
  - Re-checks scheme, ports, credentials, DNS resolution, and destination IP on every hop.
  - Immediately rejects public-to-private redirects (e.g., redirecting to cloud metadata `169.254.169.254`).
- **MIME & Decompressed Size Enforcement**:
  - Permits only `text/html`, `text/plain`, and `application/xhtml+xml`. Rejects binary/PDF MIME types before downloading body.
  - Rejects `Content-Length > 1 MB`.
  - Streams response chunks and terminates immediately if cumulative decompressed bytes exceed 1 MB cap.
  - Oversized or incomplete content is marked `INACCESSIBLE` with `extracted_text=None`.
- **Overall Fetch Deadline**: Monotonic deadline (default 30s) covers all phases: DNS, connect, TLS, headers, streamed read, and redirects.
- **Source Audit vs. Evidence**: Returns structured `RetrievedSource`. Downloaded content is tagged as untrusted data, never labeled as verified evidence.

---

## Milestone 2A — Validation Reconciliation & Frontend Ordering (COMPLETE)
- Reconciled retry policy to 2 retries (3 total attempts), complying with `AGENTS.md`.
- Verified 90s timeout is per attempt; maximum overall worst-case duration is 312 seconds (~5.2 minutes).
- Reconciled rate limit claims with dated observations (5–15 RPM observed during Oct 2026 testing).
- Fixed frontend request ordering, loading state ownership, and added Try Again error recovery.
- Established design contract in `docs/evidence-search-design.md`.

---

## Milestone 1 Baseline — Claim Extraction Vertical Slice (Prior Evidence)
- Backend structured claim extraction via Gemini structured output (`ClaimExtractionResultLLM`).
- Verified input preservation on provider errors and unique submission IDs.
- Recorded prior live validation results against Gemini API: health check ok, missing credential error 503, and 3 Los Angeles test inputs (factual/opinion separation, location preservation, qualification preservation).

---

### Automated Test Suite (86 passing — all fixture-based or mocked)

| Suite | Tests | What it covers | Status |
|---|---|---|---|
| `test_extraction.py` | 14 | Claim extraction, validation, error handling, unique IDs | PASSED |
| `test_frontend_ordering.py` | 1 (35 assertions) | Headless Chrome browser test: request ordering, stale discard, Try Again | PASSED |
| `test_search_contract.py` | 9 | `SearchProvider` Protocol, `SearchResultHit` snippet immutability, date/dependence defaults, query generation | PASSED |
| `test_safe_fetcher.py` | 62 | IP ranges, IPv4-mapped IPv6, CGNAT, scheme/port/credential validation, public success, private/loopback rejection, public-to-private redirect block, DNS rebinding block, 3-hop redirect limit, MIME rejection, 1MB size limit, timeout deadline, connection enforcement | PASSED |
| **Total** | **86** | Full regression and new capability suite | **ALL PASSED (29.32s)** |

---

### Remaining Integration Limitations
1. **No Live External Search Integration**: `SearchProvider` interface and mock test support are verified; live Serper API key and live external queries have not yet been hooked to the pipeline.
2. **No Live Web Fetching**: `SafeFetcher` has been tested against controlled transports, SSRF fixtures, and redirect matrices; live external URL fetching is not yet wired into the user workflow.
3. **No Passage Extraction from HTML**: `SafeFetcher` returns decoded page text; DOM/readability passage extraction (converting HTML into structured `EvidencePassage` records) is deferred to Milestone 2C.
4. **No LLM Evidence Evaluation**: Findings and verdicts based on retrieved passages have not yet been implemented.

---

## Proposed Next Bounded Task: Milestone 2C

**Task Title:** Connect Real Search Provider, Bounded Page Retrieval, and Inspectable Passages to Backend & UI

**Bounded Scope:**
1. **Serper Search Provider Implementation**:
   - Implement `SerperSearchProvider` conforming to `SearchProvider` protocol in `backend/app/search/serper_provider.py`.
   - Read `SERPER_API_KEY` from `.env` (git-ignored).
   - Strict budget per user request: max 2 search queries per claim, max 5 hits per query.
2. **HTML Content Extractor**:
   - Implement basic HTML-to-text cleaning (extracting readable body text, stripping scripts/styles/nav).
   - Extract relevant candidate passages matching claim assertions.
3. **Investigation Endpoint & UI Cards**:
   - Expose `/api/investigate` or extend `/api/extract` to run search + safe retrieval for extracted claims.
   - Update UI to show inspectable candidate sources with explicit states: `snippet_only` (unverified hit), `retrieved` (safely fetched), and `inaccessible` (blocked/failed).
   - Add toggle to view examined source passage vs. unexamined search snippet.
4. **Credentials Required**:
   - `SERPER_API_KEY` (free tier from [serper.dev](https://serper.dev) provides 2,500 free queries).
   - Existing `GEMINI_API_KEY` for claim extraction.
5. **Bounded External Usage**:
   - Total budget per investigation run: max 2 Serper queries, max 2 page fetches (via `SafeFetcher`), strictly bounded to prevent cost overruns.
