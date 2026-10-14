# Milestone 2C Review & Verification Report (Post-Review Repair Pass)

Last updated: 2026-10-14
Milestone: 2C — Real Search Provider, Bounded Retrieval, and Inspectable Candidate Passages

---

## 1. Environment & Git Status

- **Canonical Workspace & Git Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\`
- **Current HEAD**: `5eb71d910f48a031e41875ba89134a98f9f21b1c` (branch `master`)
- **Milestone Baseline**: `713a134` (Milestone 2B checkpoint)
- **Previous Review Snapshot**: `ae832bfe465f3e624a4a93706c1623e2fd85689c`
- **Working Tree Status**: Repaired and verified clean.
- **Secret Protection**: `.env` and `backend/.env` are git-ignored and strictly excluded from git tracking. No API keys or tokens are committed or displayed.

---

## 2. Test Execution & Final Results

### Full Automated Test Suite Command
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

### Final Results
- **Outcome**: **115 passed**, 0 failed, 0 skipped, 2 deprecation warnings in dependencies (`google.genai.types` and `starlette.testclient`).
- **Duration**: ~30.3 seconds across all unit, integration, and security checks.

### Headless Browser Ordering & State Test Command
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_ordering.py -v -s
```

### Browser Test Results
- **Outcome**: **1 passed** (65 browser assertions passed across 8 tests, 0 failures in 1.18s).
- **Browser Executable**: `C:\Program Files\Google\Chrome\Application\chrome.exe` (`--headless=new`).

### Test Suite Breakdown

| Test File | Tests | Focus Area | Status |
|---|---|---|---|
| `backend/tests/test_safe_fetcher.py` | 65 | IP ranges, IPv4-mapped IPv6, CGNAT, scheme/standard & bad port/credential validation (R3), public success, private/loopback rejection, public-to-private redirect block, DNS rebinding block, 3-hop redirect limit, MIME rejection, 1MB size limit, cancellable deadline and slow DNS enforcement with elapsed bounds (R2), socket connection enforcement | PASSED |
| `backend/tests/test_extraction.py` | 14 | Claim extraction, validation, error mapping, unique ID generation | PASSED |
| `backend/tests/test_serper_provider.py` | 12 | Serper API contract, 401/403/429 status mapping, bounded 5xx retries, outbound attempt accounting, secret redaction | PASSED |
| `backend/tests/test_search_contract.py` | 9 | `SearchProvider` Protocol, `SearchResultHit` snippet immutability, date/dependence defaults, query generation | PASSED |
| `backend/tests/test_passage_extractor.py` | 9 | Script/style stripping, entity decoding (single decode R1), exact substring offsets, provenance verification, URL deduplication, void element handling (<embed> R1), table cell number separation (R1), plain-text MIME preservation (<exception> R1) | PASSED |
| `backend/tests/test_research_endpoint.py` | 5 | Orchestrator flow with mock provider & fetcher (injected DNS R5), candidate page budget cap (3), partial fetch failures, 503 on missing credentials, cancellable orchestrator deadline enforcement (R2), malformed port error isolation (R3) | PASSED |
| `backend/tests/test_frontend_ordering.py` | 1 (65 asserts) | In-browser state ownership, sequence protection, stale result discard, Try Again recovery, research action, input/URL modification invalidation (R4), inert rendering | PASSED |
| **Total** | **115 passed** | **Zero failures** | **ALL PASSED** |

---

## 3. Summary of Code Review Repairs (R1–R5)

### R1. Source Cleaning and Fidelity Preserved
- **Void Element Handling**: Added `HTML5_VOID_TAGS` (`embed`, `hr`, `br`, `img`, `input`, etc.) to prevent void elements from altering `_ignore_depth`. Text following `<embed>` (e.g. corrections) is retained.
- **Table Cell Boundaries**: Added `TABLE_CELL_TAGS` (`td`, `th`) in `HTMLTextExtractor` to insert space delimiters so distinct numbers across table cells (e.g. `2022` and `43`) do not merge into `202243`.
- **Single Entity Decode**: Removed redundant second `html.unescape()` call in `get_text()`, allowing `HTMLParser(convert_charrefs=True)` to decode entities once and preserving literal text such as `&amp;lt;warning&amp;gt;` as `&lt;warning&gt;`.
- **MIME-Aware Cleaner**: Created `clean_text_content(content, content_type)`. For `text/plain`, angle-bracketed text like `Rule: <exception>` is preserved verbatim without stripping.
- **Inspectable Provenance**: Added `raw_text: str | None` (bounded to first 5,000 characters of raw downloaded content) and `extraction_note: str | None` to `RetrievedSource` for extraction auditability.

### R2. Cancellable Deadlines Enforced
- **SafeFetcher**: Wrapped `fetch()` in an overall cancellable `async with asyncio.timeout(...)`. When DNS or transport hangs, the operation is cancelled cleanly and returns a structured timeout result without extending the deadline. Added `test_safe_fetcher_enforces_deadline_on_slow_dns` asserting elapsed cancellation < 0.15s.
- **ResearchOrchestrator**: Wrapped `research_claim` execution in `async with asyncio.timeout(...)` and provider search in `asyncio.wait_for`. Removed `max(1.0, remaining)` fallback; now uses `min(30.0, remaining)`. Preserves partial results if deadline fires and marks `status_message` with timeout diagnostics. Tested via `test_research_orchestrator_enforces_cancellable_deadline` asserting elapsed time.

### R3. Malformed URL/Port Isolation and Request Bounds
- **Port Syntax Handling**: Wrapped `parsed.port` and `parsed.hostname` in `validate_url_syntax` with `try...except ValueError` to catch non-integer and out-of-range ports (`:bad`, `:99999`) and convert them into `SafeFetchError`.
- **Candidate Isolation**: Wrapped per-candidate fetches in try/except (preserving `asyncio.CancelledError`) so unexpected retrieval failures mark that individual source as `INACCESSIBLE` and do not abort the research request or return HTTP 500.
- **Request Bounds**: Added explicit length limits to `ResearchRequest` (`claim_text` max 5000 chars, `source_url` max 4096 chars, `submission_id` and `claim_id` max 200 chars).

### R4. Input and URL Edits Invalidate Stale Extraction and Research
- **Input Edit Handlers**: In `frontend/app.js`, both `inputText` and `sourceUrl` input events trigger `handleInputEdit()`, which:
  1. Increments `currentSubmissionSeq++` to discard in-flight extraction responses.
  2. Resets `setLoading(false)` on extraction button.
  3. Increments `activeResearchSeq++` and clears `activeResearchClaimId`.
  4. Marks any displayed claims snapshot outdated with an explicit notice banner and disables research buttons (`button.disabled = true; button.title = ...`).
  5. Cleans up in-flight research loading spinners.
- **Research Finally Cleanup**: `executeResearch` `finally` block verifies state ownership before restoring button state. If the research sequence was superseded or the snapshot is outdated, it does not re-enable the button.
- **Browser Validation**: Comprehensive Test 7 in `frontend/test_runner.html` tests edit-during-extraction, URL-only edits, and edit-during-research with delayed responses.

### R5. Test Harness and Fixture Repairs
- **HTTPX Response Fixtures**: Replaced `html=` with standard `text=` in `test_safe_fetcher.py`.
- **DNS Resolver Injection**: Injected mock DNS resolver into `test_research_endpoint.py` so offline orchestrator tests do not touch system DNS.
- **Elapsed Time Assertions**: Added monotonic timing checks to safe fetcher and orchestrator deadline tests.
- **Live Smoke Assertions**: Updated `live_smoke_investigation.py` to assert elapsed time <= 90s, at least 1 retrieved source, at least 1 extracted passage, and outbound search attempt bounds.

---

## 4. How the Browser Harness Loads Real Frontend Code

The browser test harness in `backend/tests/test_frontend_ordering.py` and `frontend/test_runner.html` tests the production frontend application directly:

1. **Production Code Loading**:
   - `frontend/test_runner.html` loads the actual production script via `<script src="app.js"></script>`.
   - It contains the exact HTML structure and DOM IDs present in `frontend/index.html` (`#extraction-form`, `#input-text`, `#source-url`, `#submit-btn`, `#error-banner`, `#results-section`, `#claims-list`).
2. **Mock Network Layer**:
   - The test harness intercepts `window.fetch` at the network boundary, routing `/api/extract` and `/api/research` to FIFO mock queues (`mockQueue` and `researchMockQueue`).
   - The entire production JavaScript pipeline inside `frontend/app.js` executes naturally: event listeners, DOM element creation, CSS class transitions, sequence tracking (`currentSubmissionSeq`, `activeResearchSeq`), and error/result rendering.
3. **Headless Execution**:
   - `test_frontend_ordering.py` launches Google Chrome in `--headless=new` mode with `--virtual-time-budget=5000` and `--dump-dom`.
   - The test script evaluates real user interactions (`click()`, `dispatchEvent(new Event("input"))`), waits for microtasks/timeouts, and records pass/fail logs into `#test-report`.
   - Pytest reads the dumped DOM, asserts `"ALL TESTS PASSED"` is present, and asserts `"FAIL:"` is not present.

---

## 5. Outbound Search Request Budget Accounting

**Question**: *Does the two-request search cap count every outbound attempt, including retries?*

**Answer**: **Yes, absolutely.**

1. **Provider-Level Accounting (`backend/app/search/serper_provider.py`)**:
   - `SerperSearchProvider` maintains an instance counter `self.total_requests_made`.
   - Every outbound HTTP POST to `https://google.serper.dev/search` increments `self.total_requests_made` before transmission.
   - The provider limits attempts to `MAX_SEARCH_ATTEMPTS = 2` (`while attempts < MAX_SEARCH_ATTEMPTS and self.total_requests_made < MAX_SEARCH_ATTEMPTS:`).
   - If an initial request encounters a 5xx server error or timeout, the retry counts as request #2.
2. **Orchestrator-Level Accounting (`backend/app/research.py`)**:
   - Before dispatching a second planned query (e.g., broad keyword fallback), `ResearchOrchestrator` inspects `getattr(provider, "total_requests_made", 0)`.
   - If the first query consumed 2 outbound requests (1 initial attempt + 1 retry), the orchestrator immediately halts the search phase.
   - Verified by unit test `test_outbound_requests_counted_including_retries` in `backend/tests/test_serper_provider.py`.

---

## 6. Live Validation Status (Separated from Fixture Results)

### Fixture-Based Verification (Completed & Passing on Repaired Code)
- Serper response parsing, rank preservation, and 5-hit cap verified with mock JSON payloads.
- Status code mappings (401, 403, 429, 500) and retry boundaries verified via `httpx.MockTransport`.
- SSRF defenses (CGNAT, loopback, private ranges, IPv4-mapped IPv6, DNS rebinding, redirect hops) verified via socket-level mock transports.
- Verbatim character offset slicing, void element preservation, table cell separation, entity decoding, and plain-text body preservation verified on HTML/text fixtures.
- Cancellable deadline enforcement verified under slow DNS and slow search provider simulations with elapsed time bounds.
- 115 pytest tests and 65 headless browser assertions passing with zero failures.

### Prior Live Smoke Investigation (Historical Builder Evidence)
Executed with user-confirmed free credits within all mandated limits prior to this repair pass:
- **Test Statement**: `"Mayor Karen Bass took office in December 2022 as the 43rd Mayor of Los Angeles."`
- **Extracted Claim**: `"Karen Bass took office as the 43rd Mayor of Los Angeles in December 2022."` (factual, Los Angeles, December 2022).
- **Search Query Executed**: Exactly **1** query sent to Serper (`primary_assertion`), consuming 1 of the 2 allowed outbound search requests.
- **Search Hits Returned**: Exactly **5** hits (capped at 5). Each hit carries immutable `is_snippet_only: True` and is prominently marked with a `Snippet Only #N` disclaimer badge.
- **Candidate Pages Attempted & Outcomes**:
  1. `https://lacity.gov/news/karen-bass-sworn-43rd-mayor-los-angeles`:
     - Outcome: **RETRIEVED** (HTTP 200, IP: `23.48.203.178`, size: 31,545 bytes).
  2. `https://en.wikipedia.org/wiki/Karen_Bass`:
     - Outcome: **RETRIEVED** (HTTP 200, IP: `198.35.26.224`, size: 757,252 bytes).
  3. `https://www.nytimes.com/2022/12/12/us/karen-bass-los-angeles-mayor.html`:
     - Outcome: **INACCESSIBLE** (HTTP 403 Forbidden, IP: `151.101.73.164`, size: 0 bytes). Accurately captures paywall/bot obstruction without crashing.
- **Displayed Verbatim Passage Checked Against Retained Extracted Text**:
  - Passage 1 from `lacity.gov`:
    `"Karen Bass was sworn in by Vice President Kamala Harris as Los Angeles' 43rd mayor in a historic inauguration ceremony on Sunday, December 11, 2022. Karen Bass is the 43rd Mayor of Los Angeles and the first woman and second African American to be elected as the city's chief executive. With an agenda focused on bringing urgency, accountability, and a new direction to Los Angeles, she will start her term with a focus on housing people immediately and increasing safety and opportunity in every part of Los Angeles."`
  - Offsets: `[313:829]`
  - Programmatic Check: `extracted_text[313:829] == exact_passage` -> **VERIFIED EXACT SUBSTRING MATCH** (516 characters).
- **Browser Presentation & Distinction**:
  - Live browser execution on `http://127.0.0.1:8000` verified via automated browser subagent.
  - Search hits group is visually and semantically distinct from retrieved candidate sources.
  - Collapsible drawers (`"Show surrounding context"` and `"Inspect full extracted page text"`) allow complete auditing of retained text.
  - All external text is rendered inertly via `textContent` without verdicts, truth meters, or confidence scores.
- **Elapsed Duration**: 6.26 seconds (well within the 90s deadline). Zero secret leakage.
