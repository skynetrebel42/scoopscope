# Milestone 2C Review & Verification Report (Post-Review Repair Pass)

Last updated: 2026-10-14
Milestone: 2C — Real Search Provider, Bounded Retrieval, and Inspectable Candidate Passages

---

## 1. Environment & Git Status

- **Canonical Workspace & Git Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\`
- **Packaged Commit / HEAD**: `7e57aa9f3ff6bdcd4a7041b3f505cb81fc4771b4` (branch `master`)
- **Tested Commit**: `7e57aa9f3ff6bdcd4a7041b3f505cb81fc4771b4`
- **Prior Reviewed HEAD**: `3e47c49c5e16bd5a6df32a4fad4ad17bc884353e`
- **Milestone 2B Baseline Checkpoint**: `713a134`
- **Working Tree Status**: Repaired, verified, and committed clean.
- **Secret Protection**: `.env` and `backend/.env` are git-ignored and strictly excluded from git tracking. No API keys or tokens are committed or displayed.

---

## 2. Test Execution & Final Results

### Full Automated Test Suite Command
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

### Final Results
- **Outcome**: **122 passed**, 0 failed, 0 skipped, 2 deprecation warnings in dependencies (`google.genai.types` and `starlette.testclient`).
- **Duration**: ~30.3 seconds across all unit, integration, and security checks.

### Headless Browser Ordering & State Test Command
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_ordering.py -v -s
```

### Browser Test Results
- **Outcome**: **1 passed** (88 browser assertions passed across 9 test suites, 0 failures in 1.03s).
- **Browser Executable**: `C:\Program Files\Google\Chrome\Application\chrome.exe` (`--headless=new`).

### Test Suite Breakdown

| Test File | Tests | Focus Area | Status |
|---|---|---|---|
| `backend/tests/test_safe_fetcher.py` | 65 | IP ranges, IPv4-mapped IPv6, CGNAT, scheme/standard & bad port/credential validation (R3), public success, private/loopback rejection, public-to-private redirect block, DNS rebinding block, 3-hop redirect limit, MIME rejection, 1MB size limit, cancellable deadline and slow DNS enforcement with elapsed bounds (R2), socket connection enforcement | PASSED |
| `backend/tests/test_extraction.py` | 14 | Claim extraction, validation, error mapping, unique ID generation | PASSED |
| `backend/tests/test_serper_provider.py` | 12 | Serper API contract, 401/403/429 status mapping, bounded 5xx retries, outbound attempt accounting, secret redaction | PASSED |
| `backend/tests/test_search_contract.py` | 9 | `SearchProvider` Protocol, `SearchResultHit` snippet immutability, date/dependence defaults, query generation | PASSED |
| `backend/tests/test_passage_extractor.py` | 9 | Script/style stripping, entity decoding (single decode R1), exact substring offsets, provenance verification, URL deduplication, void element handling (<embed> R1), table cell number separation (R1), plain-text MIME preservation (<exception> R1) | PASSED |
| `backend/tests/test_research_endpoint.py` | 12 | Orchestrator flow with mock provider & fetcher (injected DNS R5), candidate page budget cap (3), partial fetch failures, 503 on missing credentials, cancellable orchestrator deadline enforcement (R2), malformed port error isolation (R3), search provider failure propagation on 401/403/429/500 (F1), partial evidence preservation on search failure with source URL (F1), legitimate 0-hit search distinguishability (F1), cooperative synchronous extraction deadline enforcement on large documents (F3) | PASSED |
| `backend/tests/test_frontend_ordering.py` | 1 (88 asserts) | In-browser state ownership, sequence protection, stale result discard, Try Again recovery, research action, input/URL modification invalidation (R4), inert rendering, claim switching A then B in both resolution orders with button restoration (F2) | PASSED |
| **Total** | **122 passed** | **Zero failures** | **ALL PASSED** |

---

## 3. Summary of Code Review Repairs

### Prior Repair Pass (R1–R5)
- **R1. Source Cleaning and Fidelity**: Added `HTML5_VOID_TAGS` (`embed`, etc.), `TABLE_CELL_TAGS` spacing, single entity decode, and MIME-aware text cleaner.
- **R2. Cancellable Deadlines**: Overall cancellable `asyncio.timeout` in `SafeFetcher` and `ResearchOrchestrator`.
- **R3. Port Syntax & Candidate Isolation**: `try...except ValueError` on port validation converting bad/overflow ports to `SafeFetchError`, with isolated candidate error records.
- **R4. Input/URL Edits**: Form input edits immediately invalidate pending extraction, cancel in-flight research ownership, and disable research buttons with warning banner.
- **R5. Test Harness**: Injected DNS resolver into offline tests and added monotonic timing assertions.

### Follow-Up Repair Pass (F1–F3 and Consistency Items)

#### F1. Search Failure State Preservation and Propagation
- **Problem**: Broad exception handling in search loop swallowed provider failures, logging them and returning an ordinary 200 response reporting 0 hits.
- **Fix**:
  - When no `source_url` is supplied: `SearchProviderError` (and unexpected search provider exceptions) re-raise directly, caught by FastAPI `/api/research` to return structured HTTP 502/503 errors (`"Search provider failure"`). All API keys and secrets are scrubbed via `_sanitize_error_message()`. The UI `showResearchError` displays an explicit error banner.
  - When a `source_url` is supplied: The orchestrator preserves partial evidence, extracting passages from the supplied URL while setting `search_failure_message` on `ResearchResponse`. The UI renders an alert banner ("Search provider unavailable: ...") in the research results panel.
  - Distinguishable from legitimate zero-hit searches: A normal 0-hit search returns 200 with `search_failure_message=None`, `search_hits=[]`, and `"Gathered 0 candidate search hit(s)"`.
- **Tests Added**: Parametrized tests for 401, 403, 429, and 500 retry-exhausted failures without `source_url`, partial evidence preservation with `source_url`, and legitimate zero-hit distinction in `test_research_endpoint.py`.

#### F2. Switching Claims Request Ownership and Button State Restoration
- **Problem**: When user clicked research on Claim A, then clicked Claim B before A finished, A's `finally` block did not restore A's button if it was superseded by B. As a result, Claim A's button remained stuck on `disabled = true` and `"Researching…"`.
- **Fix**:
  - In `frontend/app.js` `executeResearch` `finally`:
    1. Each card cleans up its own loading indicator (`.research-loading-state`).
    2. Shared global active research claim state (`activeResearchClaimId`) is cleared only if request sequence identity matches (`researchSeq === activeResearchSeq && activeResearchClaimId === claim.id`). Completing a superseded request never clears newer active work.
    3. Each card restores its button to `disabled = false` and `"Find sources"` (or remains disabled with tooltip if an input edit invalidated the snapshot).
    4. Stale responses from superseded requests are discarded and never render into the DOM.
- **Tests Added**: In-browser Test 9 in `frontend/test_runner.html` testing:
  - Start A then B, resolve A (error) then B (success): button A restored, error A discarded, button B restored, results B rendered.
  - Start C then D, resolve D (success) first then C (success) second: button D restored, results D rendered, button C restored, stale results C discarded.
  - Neither card remains loading after resolution.

#### F3. Cooperative Synchronous Extraction Deadline Enforcement
- **Problem**: Cleaners and passage extraction ran synchronously in the event loop thread, ignoring the remaining budget and allowing large documents to exceed the deadline and still report ordinary success.
- **Fix**:
  - `HTMLTextExtractor`, `clean_html_to_text`, `clean_text_content`, and `extract_candidate_passages` now accept a monotonic `deadline: float`.
  - `HTMLTextExtractor` checks `time.monotonic() > deadline` every 25 tags via `_check_deadline()`.
  - `clean_html_to_text` feeds in 16KB chunks, verifying deadline between chunks.
  - `extract_candidate_passages` checks deadline before splitting, keyword scoring, and passage assembly.
  - In `ResearchOrchestrator`, monotonic deadline checks before and after synchronous extraction guarantee that over-budget work sets `timed_out = True`, returning an explicit `TIMEOUT` status while preserving completed evidence.
- **Tests Added**: Regression test with a 670KB document under a 20ms research budget in `test_research_endpoint.py`, asserting explicit `TIMEOUT` status and non-success.

#### Consistency & Provenance Fixes
- **Python Runtime Requirement**: Updated `backend/pyproject.toml` and `README.md` to `requires-python = ">=3.11"` to match `asyncio.timeout` availability.
- **Live Request Counting**: `backend/tests/live_smoke_investigation.py` instruments and asserts `total_requests_made <= 2` directly on the search provider instance.
- **Truncated Raw Audit Sample Wording**: Clarified that `raw_text` stores only the first 5,000 characters of raw downloaded content as an API debug/audit sample; it is not complete user-inspectable original-source provenance and does not validate passages occurring beyond that prefix.
- **Snapshot Identity Reconciled**: Packaged commit and tested commit are explicitly synchronized.

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
