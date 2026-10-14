# Milestone 2C Review & Verification Report

Last updated: 2026-10-14
Milestone: 2C — Real Search Provider, Bounded Retrieval, and Inspectable Candidate Passages

---

## 1. Environment & Git Status

- **Canonical Workspace & Git Root**: `C:/Users/minhb/OneDrive/Desktop/Projects/ScoopScope`
- **Current HEAD**: `b1809557a5367839ad74e98f7e2c918ecaa3aa9e` (branch `master`)
- **Milestone Baseline**: `713a134` (Milestone 2B checkpoint)
- **Working Tree Status**: Clean (no uncommitted or untracked changes, excluding git-ignored files).
- **Secret Protection**: `.env` and `backend/.env` are git-ignored and strictly excluded from git tracking. No API keys or tokens are committed or displayed.

---

## 2. Test Execution & Final Results

### Full Automated Test Suite Command
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

### Final Results
- **Outcome**: **106 passed**, 0 failed, 0 skipped, 2 deprecation warnings in dependencies (`google.genai.types` and `starlette.testclient`).
- **Duration**: ~29.2 seconds across all unit, integration, and security checks.

### Headless Browser Ordering & State Test Command
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_ordering.py -v -s
```

### Browser Test Results
- **Outcome**: **1 passed** (50 assertions passed, 0 failures in 0.55s).
- **Browser Executable**: `C:\Program Files\Google\Chrome\Application\chrome.exe` (`--headless=new`).

### Test Suite Breakdown

| Test File | Tests | Focus Area | Status |
|---|---|---|---|
| `backend/tests/test_safe_fetcher.py` | 62 | IP validation (SSRF, CGNAT, IPv4-mapped IPv6), socket destination pinning, DNS rebinding prevention, 3-hop redirect limit, 1MB size limit, MIME whitelist | PASSED |
| `backend/tests/test_extraction.py` | 14 | Claim extraction, validation, error mapping, unique ID generation | PASSED |
| `backend/tests/test_serper_provider.py` | 12 | Serper API contract, 401/403/429 status mapping, bounded 5xx retries, outbound attempt accounting, secret redaction | PASSED |
| `backend/tests/test_search_contract.py` | 9 | `SearchProvider` Protocol, `SearchResultHit` snippet immutability, date/dependence defaults, query generation | PASSED |
| `backend/tests/test_passage_extractor.py` | 5 | Script/style stripping, entity decoding, exact substring offsets, provenance verification, URL deduplication | PASSED |
| `backend/tests/test_research_endpoint.py` | 3 | End-to-end orchestrator flow, candidate page budget cap (3), partial fetch failures, 503 on missing credentials | PASSED |
| `backend/tests/test_frontend_ordering.py` | 1 (50 asserts) | In-browser state ownership, sequence protection, stale result discard, Try Again recovery, research action, inert rendering | PASSED |
| **Total** | **106 passed** | **Zero failures** | **ALL PASSED** |

---

## 3. Skipped Tests & Assertion Audit

- **Skipped Tests**: **0** (No tests were skipped).
- **Weakened or Removed Assertions**: **0** (No existing assertions were weakened or deleted).
- **New Assertions Added in Milestone 2C**:
  - 15 new assertions in `test_frontend_ordering.py` verifying:
    1. "Find sources" button initialization and state transitions.
    2. Snippet badge rendering and separation from retrieved body text.
    3. Programmatic candidate passage rendering with exact verbatim matching.
    4. Destination IP audit metadata display.
    5. Invalidation and discard of stale research jobs on user input changes.
    6. Inert text rendering preventing XSS execution (`<script>` payloads).
  - 12 new tests in `test_serper_provider.py`.
  - 5 new tests in `test_passage_extractor.py`.
  - 3 new tests in `test_research_endpoint.py`.

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

### Fixture-Based Verification (Completed & Passing)
- Serper response parsing, rank preservation, and 5-hit cap verified with mock JSON payloads.
- Status code mappings (401, 403, 429, 500) and retry boundaries verified via `httpx.MockTransport`.
- SSRF defenses (CGNAT, loopback, private ranges, IPv4-mapped IPv6, DNS rebinding, redirect hops) verified via socket-level mock transports.
- Verbatim character offset slicing and HTML tag stripping verified on HTML fixtures.

## 6. Live Validation Status (Separated from Fixture Results)

### Fixture-Based Verification (Completed & Passing)
- Serper response parsing, rank preservation, and 5-hit cap verified with mock JSON payloads.
- Status code mappings (401, 403, 429, 500) and retry boundaries verified via `httpx.MockTransport`.
- SSRF defenses (CGNAT, loopback, private ranges, IPv4-mapped IPv6, DNS rebinding, redirect hops) verified via socket-level mock transports.
- Verbatim character offset slicing and HTML tag stripping verified on HTML fixtures.

### Live Smoke Investigation (COMPLETED & VERIFIED)
Executed with user-confirmed free credits within all mandated limits:
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
