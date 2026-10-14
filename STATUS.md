# ScoopScope — Project Status

Last updated: 2026-10-13

## Milestone 1 — Claim Extraction Vertical Slice (COMPLETE)

### Implementation (complete)

- **Backend** (Python/FastAPI):
  - `app/config.py` — Settings from `.env` with safe defaults (`gemini-flash-lite-latest`, 90s timeout, 3 retries)
  - `app/models.py` — Pydantic schemas for LLM output, API request/response
  - `app/gemini_adapter.py` — Gemini client with structured output, timeout,
    adaptive backoff retries for 429/503 spikes, and Pydantic validation
  - `app/main.py` — FastAPI app serving API + static frontend

- **Frontend** (HTML/CSS/JS):
  - Dark theme with teal accent, responsive layout
  - Textarea for statement input, optional source URL
  - Claim cards with color-coded type tags (factual/opinion/prediction/causal)
  - Stale-response prevention via monotonic submission counter
  - Input preserved on errors

- **Documentation**:
  - `AGENTS.md` — Evidence rules, security boundaries, future SSRF protections
  - `GEMINI.md` — Pointer to AGENTS.md (Antigravity loads both)
  - `README.md` — Setup, run, API docs

---

### Automated tests (14 passing — all fixture-based, no live API)

All 14 tests use **mocked/fixture Gemini responses**. No test calls the real
Gemini API. The mock is explicit in every test — no silent fallback.

| # | Test | What it covers | Status |
|---|------|----------------|--------|
| 1 | `test_empty_input_returns_400` | Empty text rejected | PASSED |
| 2 | `test_whitespace_only_input_returns_400` | Whitespace-only text rejected | PASSED |
| 3 | `test_oversized_input_returns_400` | Input exceeding 10,000 chars rejected | PASSED |
| 4 | `test_missing_text_field_returns_422` | Missing `text` field produces Pydantic error | PASSED |
| 5 | `test_missing_credentials_returns_503` | No API key produces clear 503 error | PASSED |
| 6 | `test_health_endpoint` | `/api/health` returns status, model, credential flag | PASSED |
| 7 | `test_fixture_based_malformed_not_json` | Non-JSON model output produces 503 | PASSED |
| 8 | `test_fixture_based_malformed_missing_claims_key` | Missing `claims` key produces 503 | PASSED |
| 9 | `test_fixture_based_malformed_wrong_claim_type` | Invalid enum produces 503 | PASSED |
| 10 | `test_fixture_based_malformed_missing_required_field` | Missing field produces 503 | PASSED |
| 11 | `test_fixture_based_successful_extraction` | Well-formed response produces 200 with correct structure | PASSED |
| 12 | `test_fixture_based_empty_claims` | No-claims input produces empty list with 200 | PASSED |
| 13 | `test_input_preserved_on_provider_error` | User input echoed back on 503 | PASSED |
| 14 | `test_fixture_based_submission_ids_are_unique` | Three responses produce three distinct IDs | PASSED |

---

### Live validation (complete — 100% passed on live Gemini API)

The live validation script (`tests/live_validation.py`) ran against the real Google Gemini API with the user's free-tier key. **All checks passed.**

| Step | Test Input / Scenario | Live Results & Checks | Status |
|------|-----------------------|-----------------------|--------|
| **1** | Health check | Status: `ok`, Credentials configured: `True`, Model: `gemini-flash-lite-latest` | **PASS** |
| **2** | Missing-credentials error (simulated) | Status code: `503`, Error message clearly mentions missing credentials | **PASS** |
| **3.1** | **Input 1: Mixed factual assertions and opinion**<br>_LA size, population, cultural opinion_ | - Claims extracted: 2 (1 factual, 1 opinion)<br>- Quantity preserved: 469 sq mi, 3.9M people<br>- Location preserved: Los Angeles<br>- No invented details | **PASS** (6/6 checks) |
| **3.2** | **Input 2: Ambiguous "Los Angeles" reference**<br>_Transit expansion, 3 new rail lines by 2035_ | - Claims extracted: 2 (1 factual, 1 prediction)<br>- Preserved "Los Angeles" as-is (did NOT fabricate City/County)<br>- Extracted date: 2035<br>- Extracted quantity: "three" | **PASS** (5/5 checks) |
| **3.3** | **Input 3: Compound claim with qualification**<br>_Mayor Bass 14% reduction + critic methodology objection_ | - Claims extracted: 2 (1 assertion, 1 criticism)<br>- Date extracted: March 2025<br>- Quantity extracted: approximately 14%<br>- Qualifications preserved ("According to Mayor Bass", "critics argue")<br>- Source URL echoed back<br>- Zero invented sources, scores, or confidence metrics | **PASS** (6/6 checks) |

**Overall live validation outcome:** `[SUCCESS] ALL LIVE VALIDATION CHECKS PASSED`

---

### Model configuration

| Setting | Value |
|---------|-------|
| Default model | `gemini-flash-lite-latest` |
| Fallbacks/Alternatives | `gemini-3.8-flash`, `gemini-3.5-flash` |
| Free tier | Yes — via AI Studio API key, $0 usage |
| Free tier rate limit | 5 RPM (requests per minute) |
| Structured output | Yes — `response_schema` with Pydantic model (`ClaimExtractionResultLLM`) |
| Timeout | 90s (`LLM_TIMEOUT_SECONDS`) — avoids cancellation during free-tier gateway queues |
| Max retries & backoff | 3 retries (`LLM_MAX_RETRIES`), adaptive backoff (12-30s) on 429/503 |
| Configurable | Override via `GEMINI_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` in `.env` |

---

### Credential setup

| Item | Value |
|------|-------|
| Environment variable | `GEMINI_API_KEY` |
| File path | `c:\Users\minhb\Projects\ScoopScope\backend\.env` |
| Template | `backend/.env.example` |
| Git-ignored | Yes — `.gitignore` covers `.env` and `backend/.env` |

**Consistency audit:** `GEMINI_API_KEY` is verified consistent in `app/config.py`, `app/gemini_adapter.py`, `backend/.env.example`, `backend/.env`, `README.md`, `STATUS.md`, and all test suites. No occurrences of `LLM_API_KEY` exist anywhere in the repository.

---

## Blockers

**None.** Milestone 1 is completely implemented, verified through automated unit tests, and live-validated against the Google Gemini API.

---

## Known limitations & observations

- **Free-tier rate limits**: Google enforces a 5 RPM ceiling on free-tier Flash models. The backend adapter handles this gracefully via adaptive backoff, and `live_validation.py` incorporates 25s pacing cooldowns between test requests.
- **Transitory demand spikes (503 UNAVAILABLE)**: Google's free-tier endpoints occasionally return 503 during high demand. The adapter's 3-retry backoff schedule (18s, 24s, 30s) automatically recovers from these without crashing the client request.
- **Frontend stale-response protection**: Uses a monotonic counter verified at the HTTP test level (#14). Browser-level manual stress testing is deferred to Milestone 2.

---

## Architecture decisions log

| Decision | Rationale |
|----------|-----------|
| Separate LLM schema from API schema | Prevents leaking raw model output on validation failure; adds unique submission and claim IDs |
| Schema via `response_schema`, not in prompt | Per google-genai SDK docs, duplicating schema in prompt degrades quality |
| Monotonic counter for stale prevention | Simpler than UUID comparison; frontend-only, no server state needed |
| Default model `gemini-flash-lite-latest` | `gemini-2.0-flash` shut down June 2026; `gemini-2.5-flash` deprecated for new users; `gemini-flash-lite-latest` provides reliable free-tier structured output |
| 90s timeout + adaptive backoff | Accommodates Google free-tier queue delays and demand spikes without burning retries |
| Test fixtures labelled explicitly | No silent fixture fallback; every mock is visible in test code |

---

## Next milestone: Milestone 2

**Scope (bounded):**
1. Add a "Try Again" button on error states in the frontend
2. Move shared test fixtures to `conftest.py`
3. Design the `SearchProvider` protocol and evidence retrieval schema
4. Write fixture-based tests for the search interface
5. No live search integration until the interface design is reviewed
