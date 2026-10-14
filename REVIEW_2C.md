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

### Live Smoke Status (Awaiting User API Key)
- `SERPER_API_KEY` is currently **absent** from `backend/.env`.
- As mandated by the milestone specification:
  - ScoopScope **never silently substitutes mock results** in production.
  - The live backend returns `503 Service Unavailable` with diagnostic message: `"SERPER_API_KEY is not configured in backend/.env. Search provider is unavailable."`
  - No external queries have been dispatched and no billing has been activated.
- **Single Live Smoke Investigation Ready**:
  Once you configure `SERPER_API_KEY` in `backend/.env` and confirm unused free credits, we will execute the single authorized live smoke investigation within the 2-query, 3-page, 90-second limit.
