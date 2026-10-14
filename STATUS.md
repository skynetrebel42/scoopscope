# ScoopScope — Project Status

Last updated: 2026-10-13

## Current Status: Milestone 2A Complete

---

## Milestone 2A — Validation Reconciliation & Evidence Search Contract (COMPLETE)

### 1. State Reconciliation & Policy Alignment (complete)
- **Retry Policy Resolved**: Aligned backend configuration with `AGENTS.md` rule (max 2 retries).
  - Clarified distinction between retries and attempts: 1 initial attempt + 2 retries = **3 total attempts**.
  - Default `LLM_MAX_RETRIES` in `app/config.py` updated from 3 to 2.
  - Adapter logging and error messages now explicitly identify initial attempt vs retry 1 vs retry 2.
- **Timeout Scope Verified**: Confirmed `LLM_TIMEOUT_SECONDS` (90s) is strictly **per attempt** (enforced by `asyncio.wait_for` on each individual `generate_content` call).
  - Calculated and documented maximum overall duration:
    - 3 attempts * 90s = 270s attempt timeout
    - Max adaptive backoff delays: 18s (after attempt 1) + 24s (after attempt 2) = 42s
    - **Maximum overall elapsed duration: up to 312 seconds (~5.2 minutes)** in worst-case failure scenario.
- **Rate Limit Documentation Reconciled**: Removed conflicting blanket claims (previously 5 RPM in STATUS.md vs ~15 RPM in README.md).
  - Documented as dated observations: During October 2026 testing on Google AI Studio, Flash-lite models exhibited throughput ceilings around 5-15 RPM with occasional 429/503 queue throttling.
  - Quotas are per account/model in Google AI Studio and subject to upstream policy. Tests use mock fixtures to avoid consuming rate limits.
- **Prior Live Extraction Results Reconciled**: Replaced "100% validated" blanket claims with itemized checks completed and remaining limitations.

### 2. Frontend Request Ordering & State Ownership (complete & verified)
- **Problem addressed**: Unique backend submission IDs alone do not guarantee that the browser will not display stale responses when network responses resolve out-of-order.
- **Implementation**:
  - `frontend/app.js`: Wrapped submission in `executeSubmission()` guarded by monotonic sequence counter (`currentSubmissionSeq`).
  - Active submission owns loading state (`aria-busy`, spinner) without locking out subsequent user overrides.
  - Clean state ownership: Starting a new submission immediately hides stale previous results so obsolete claim cards never linger during loading or under error banners.
  - Stale guard verified at all checkpoints: after network fetch, after JSON parsing, and in error/catch handlers. Stale responses are discarded before touching DOM or loading state.
  - Added **Try Again** action (`#error-retry`) on `#error-banner` with dedicated CSS styling (`.btn-retry`). Routes through the identical sequence guard and request-ordering protection.
- **Browser Automation Verification**:
  - Created automated browser test runner (`frontend/test_runner.html`) and pytest suite (`backend/tests/test_frontend_ordering.py`).
  - Executed in real headless browser (Google Chrome) with controlled network resolution.
  - **35 of 35 assertions passed (100%)**:
    1. Submit A, then B; finish B first, then A: Only B's claims displayed; A discarded; loading state cleared; error banner hidden.
    2. Submit A, then B; B succeeds, A fails second: Only B's claims displayed; A's failure does not trigger error banner; loading remains false.
    3. Submit A, then B; B fails first, A finishes second: B's error banner displayed; A's claims discarded and never rendered; loading false.
    4. Try Again recovery: Clicking Try Again increments sequence, clears error banner, activates loading, and renders new claims on success.
    5. Concurrent loading ownership: Loading state is true while requests are pending, switches to false when active request B completes, and remains false when stale request A completes.

### 3. Evidence-Search Design Contract (complete)
- Created `docs/evidence-search-design.md` establishing the design for Milestone 2B:
  - **Cardinal Rule**: Search engine results and snippets NEVER count as verified evidence. Findings require safe retrieval and passage examination.
  - Replaceable `SearchProvider` Protocol for swapping Serper, Mock, or alternative search engines.
  - Four distinct records: `ClaimLinkedQuery`, `SearchResultHit`, `RetrievedSource`, `EvidencePassage`.
  - Explicit states: `snippet_only`, `retrieved`, `inaccessible`, `extraction_failed`, `ssrf_blocked`.
  - Source provenance fields: publication date vs event date, exact verbatim passages, and unknown source-dependence tracking (Rule #3: anti-circular reporting).
  - Explicit resource budgets: max 2 queries / 3 page fetches per claim, 6 queries / 6 page fetches per submission, 1MB size cap, 30s timeout per page.
  - Non-negotiable SSRF safe-fetch protections: private IP / RFC 1918 blocking, DNS rebinding resolution check, max 3 redirects with per-hop IP validation, MIME type gate, 1MB stream cap, untrusted data prompt isolation.

---

## Milestone 1 Baseline — Claim Extraction Vertical Slice (Prior Evidence)

### Implementation
- **Backend** (Python/FastAPI):
  - `app/config.py` — Settings from `.env` with safe defaults (`gemini-flash-lite-latest`, 90s timeout per attempt, max 2 retries = 3 total attempts)
  - `app/models.py` — Pydantic schemas for LLM output, API request/response
  - `app/gemini_adapter.py` — Gemini client with structured output, timeout, adaptive backoff, and Pydantic validation
  - `app/main.py` — FastAPI app serving API + static frontend
- **Frontend** (HTML/CSS/JS):
  - Responsive dark theme with teal accents
  - Textarea input, optional source URL, character counter
  - Structured claim cards with color-coded classification tags
  - Monotonic submission counter for stale-response protection
  - User input preserved on errors; Try Again button for recovery

---

### Automated Test Suite (15 passing — all fixture-based or browser-mocked)

All backend tests use mocked fixtures or mocked browser network calls. No test incurs live API costs.

| # | Suite | Test | What it covers | Status |
|---|---|---|----------------|--------|
| 1 | `test_extraction.py` | `test_empty_input_returns_400` | Empty text rejected | PASSED |
| 2 | `test_extraction.py` | `test_whitespace_only_input_returns_400` | Whitespace-only text rejected | PASSED |
| 3 | `test_extraction.py` | `test_oversized_input_returns_400` | Input exceeding 10,000 chars rejected | PASSED |
| 4 | `test_extraction.py` | `test_missing_text_field_returns_422` | Missing `text` field produces Pydantic error | PASSED |
| 5 | `test_extraction.py` | `test_missing_credentials_returns_503` | No API key produces clear 503 error | PASSED |
| 6 | `test_extraction.py` | `test_health_endpoint` | `/api/health` returns status, model, credential flag | PASSED |
| 7 | `test_extraction.py` | `test_fixture_based_malformed_not_json` | Non-JSON model output produces 503 (with retry backoff) | PASSED |
| 8 | `test_extraction.py` | `test_fixture_based_malformed_missing_claims_key` | Missing `claims` key produces 503 | PASSED |
| 9 | `test_extraction.py` | `test_fixture_based_malformed_wrong_claim_type` | Invalid enum produces 503 | PASSED |
| 10 | `test_extraction.py` | `test_fixture_based_malformed_missing_required_field` | Missing field produces 503 | PASSED |
| 11 | `test_extraction.py` | `test_fixture_based_successful_extraction` | Well-formed response produces 200 with correct structure | PASSED |
| 12 | `test_extraction.py` | `test_fixture_based_empty_claims` | No-claims input produces empty list with 200 | PASSED |
| 13 | `test_input_preserved_on_provider_error` | User input echoed back on 503 | PASSED |
| 14 | `test_extraction.py` | `test_fixture_based_submission_ids_are_unique` | Three responses produce three distinct IDs | PASSED |
| 15 | `test_frontend_ordering.py` | `test_frontend_request_ordering_in_browser` | Headless Chrome browser test (35 assertions) verifying out-of-order resolution, error dismissal, state ownership, and Try Again | PASSED |

---

### Prior Live Validation Results (Recorded October 2026)

The following live checks were previously executed against the Google Gemini API using `tests/live_validation.py`. These results serve as recorded prior evidence and are not re-executed routinely:

| Check | Scenario | Specific Checks Completed | Observed Result |
|---|---|---|---|
| 1 | Health check | Queried `/api/health` with active API key | Status `ok`, Model `gemini-flash-lite-latest`, Credentials configured `True` |
| 2 | Missing credentials | Simulated unset key | HTTP 503 with informative message directing to `.env.example` |
| 3.1 | LA size, population, cultural assertion | Checked extraction of factual vs opinion claims, numerical quantities, location preservation | 2 claims extracted (1 factual, 1 opinion); preserved 469 sq mi, 3.9M people; location Los Angeles; no invented data |
| 3.2 | Ambiguous LA transit claim | Checked preservation of "Los Angeles" without hallucinating City vs County; extracted date & quantity | 2 claims extracted (1 factual, 1 prediction); preserved "Los Angeles"; extracted date 2035 and quantity "three" |
| 3.3 | Compound claim with Mayor Bass qualification | Checked preservation of qualifications and hedging without hallucinating certainty scores | 2 claims extracted (1 assertion, 1 criticism); extracted March 2025 and 14%; preserved "According to Mayor Bass" and "critics argue"; zero invented scores |

#### Remaining Validation Limitations
1. **Sample Scope**: Live extraction was tested against 3 curated Los Angeles inputs; edge cases involving complex nested quotes, foreign languages, or non-LA jurisdictions have not been evaluated live.
2. **Adversarial / Injection Defense**: No live prompt injection resistance testing has been conducted yet.
3. **Evidence Retrieval Absence**: Live testing only verified claim extraction; live search and source verification are not yet implemented.
4. **Model Output Variability**: LLM outputs are inherently non-deterministic; prompt alterations or upstream model checkpoints may alter extracted wording.

---

### Configuration Reference

| Setting | Value | Source / Policy |
|---------|-------|-----------------|
| Default model | `gemini-flash-lite-latest` | `app/config.py` default |
| Fallbacks/Alternatives | `gemini-3.8-flash`, `gemini-3.5-flash` | Documented in `README.md` |
| Structured output | Enabled | Via `response_schema` with `ClaimExtractionResultLLM` |
| Timeout per attempt | 90s (`LLM_TIMEOUT_SECONDS`) | `asyncio.wait_for` in `gemini_adapter.py` |
| Max retries | 2 retries (`LLM_MAX_RETRIES`) | AGENTS.md rule (1 initial + 2 retries = 3 attempts total) |
| Max overall duration | Up to 312s | 3 attempts * 90s (270s) + up to 42s backoff |
| Rate limits | Account/model specific | Google AI Studio dashboard (5-15 RPM observed during Oct 2026 tests) |
| Max input length | 10,000 characters | Enforced at FastAPI validation and UI `maxlength` |

---

## Blockers

**None.** Milestone 2A validation reconciliation, frontend request-ordering verification, and evidence-search design contract are complete.

---

## Proposed Next Bounded Task: Milestone 2B

**Task Title:** Implement `SearchProvider` Interface, Mock Provider, and Safe URL Fetcher

**Bounded Scope:**
1. **SearchProvider Implementation**:
   - Implement `SearchProvider` Protocol and `MockSearchProvider` in `backend/app/search/` with deterministic fixtures.
   - Write fixture-based tests for query generation and provider swapping.
2. **Safe URL Fetcher Module**:
   - Implement safe HTTP client in `backend/app/retrieval/safe_fetcher.py`.
   - Implement SSRF blocker: resolve DNS, block RFC 1918, loopback, link-local, carrier-grade NAT.
   - Enforce max 3 redirects with per-hop IP re-verification.
   - Enforce 1 MB size ceiling and MIME type gating (reject non-text/html).
   - Write comprehensive unit tests in `backend/tests/test_safe_fetcher.py` using local mock servers to prove SSRF blocking, redirect loop protection, and 1MB truncation.
3. **Zero live external calls**: All tests in Milestone 2B must be fixture-based and local-only. Live search API key setup deferred to subsequent milestone.
