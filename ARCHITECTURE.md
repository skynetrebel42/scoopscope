# ScoopScope — Architecture & Codebase Map

**Document Version**: 1.0  
**Baseline Commit**: `582272c`  
**Workspace**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope`  

---

## 1. System Architecture Overview

ScoopScope is organized as a lightweight FastAPI backend serving both REST endpoints and static frontend assets:

```
[ User Browser / Frontend (HTML5/CSS3/Vanilla JS) ]
     │
     │  REST JSON Requests
     ▼
[ FastAPI App (backend/app/main.py) ]
     ├── /api/clarify   ──> GeminiAdapter (Inquiry clarification & scope confirmation)
     ├── /api/extract   ──> GeminiAdapter (Legacy structured claim extraction)
     ├── /api/research  ──> ResearchOrchestrator
     │                          ├── SerperSearchProvider (Google Search API via Serper)
     │                          ├── SafeFetcher (SSRF IP-pinned socket fetcher)
     │                          ├── PassageExtractor (Verbatim character-offset slicing)
     │                          └── GeminiAdapter (Relevance evaluation & synthesis)
     └── /api/report    ──> GeminiAdapter (Custom Report & Evidence Bank synthesis)
```

---

## 2. Codebase Map & "Safe to Edit?" Classification

Before modifying any file in this repository, check its safety tier and follow the corresponding modification protocol.

| Safety Tier | Definition & Protocol |
|---|---|
| **HIGH CAUTION** | Security boundaries, network sandboxing, cryptographic/provenance invariants. **Requires dedicated written specification and security review before any edits.** |
| **MODERATE CAUTION** | Core API contracts, data models, orchestrator workflows, and parsing heuristics. **Requires test-first development and running the full pytest suite.** |
| **SAFE TO EDIT** | User interface markup, styling, client-side interactions, and documentation. **Requires running pytest and the headless Chrome ordering test suite.** |

---

### Tier 1: HIGH CAUTION (Requires Dedicated Spec & Security Review)

Do **NOT** edit these files without an explicit specification, architectural review, and end-to-end regression testing.

1. **`backend/app/retrieval/safe_fetcher.py`**
   - **Role**: Socket-level SSRF-hardened HTTP client.
   - **Critical Invariants**:
     - Pre-connection DNS resolution and validation against private/loopback/link-local/CGNAT/multicast IP ranges.
     - Socket-level destination IP pinning before TLS handshake to prevent TOCTOU DNS rebinding attacks.
     - Strict 1 MB decompressed response size cap.
     - Maximum 3 redirect hops with IP re-validation on every hop.
     - Strict timeouts (10s connect, 30s total per page fetch).
     - MIME-type gate rejecting binary payloads before reading the response body.
   - **Risk**: Tampering can expose internal services to SSRF, open denial-of-service vulnerabilities, or bypass response limits.

2. **`backend/app/search/serper_provider.py`**
   - **Role**: Concrete `SearchProvider` implementation connecting to Serper.
   - **Critical Invariants**:
     - Strict query caps (max 2 outbound requests per research action, max 5 hits per query).
     - Frozen snippet semantics (`is_snippet_only: Literal[True] = True`).
     - Unconditional redaction of `SERPER_API_KEY` from logs, exceptions, and diagnostics.
     - Error classification (401 invalid key, 403 quota exhausted, 429 rate limit, 5xx retry bounded).
   - **Risk**: Exposing API credentials, exceeding rate limits, or leaking unexamined snippets as examined evidence.

3. **`backend/app/retrieval/passage_extractor.py` (Character-Offset Slicing Core)**
   - **Role**: Verbatim character-offset slice verification (`verify_passage_provenance`).
   - **Critical Invariants**:
     - Mathematical substring guarantee: `extracted_text[start_offset:end_offset] == exact_passage`.
     - Zero LLM rewriting or hallucination of quoted excerpts.
     - Clean entity decoding without double-decoding or corruption.
   - **Risk**: Invalidating provenance guarantees or allowing hallucinated quotes into the evidence chain.

---

### Tier 2: MODERATE CAUTION (Test-First Required)

Requires unit tests written first, followed by running `pytest backend/tests -v` to ensure zero regressions.

1. **`backend/app/main.py`**
   - **Role**: FastAPI application lifecycle, route handlers (`/api/clarify`, `/api/extract`, `/api/research`, `/api/report`), and static file mounting.
   - **Cautions**: Ensure error status codes (400, 422, 500, 502, 503) match existing client expectations.

2. **`backend/app/models.py`**
   - **Role**: Pydantic schemas for all API payloads, database models, and Gemini structured outputs.
   - **Cautions**: Changes here impact frontend deserialization and Gemini structured output schemas. Always verify backward compatibility.

3. **`backend/app/research.py`**
   - **Role**: `ResearchOrchestrator` managing the research lifecycle.
   - **Cautions**: Enforces monotonic 90-second research deadline, URL deduplication, social domain deprioritization, query generation (`-filetype:pdf`), and candidate page limits (max 3).

4. **`backend/app/gemini_adapter.py`**
   - **Role**: LLM prompt formatting, structured schema enforcement, retry logic (max 2 retries), and report synthesis.
   - **Cautions**: Must strictly enforce untrusted data boundaries (`<untrusted_source_content>`) and avoid generating fallback choices or simulated truth scores.

5. **`backend/app/retrieval/passage_extractor.py` (Date & Stem Heuristics)**
   - **Role**: Defensible date extraction (`extract_dates_from_html`), stem normalization (`stem_word`), and candidate passage scoring.
   - **Cautions**: Must strictly adhere to date provenance rules (JSON-LD, `<meta>`, `<time>`, bylines; never HTTP headers or URL digits).

---

### Tier 3: SAFE TO EDIT (Run Pytest + Headless Chrome Suite)

Safe for iterative UI design and documentation enhancements. Always run tests after making modifications.

1. **`frontend/index.html`**
   - Main page HTML structure: Sticky Inquiry Bar, Session Tabs, Clarification Card, Confirmed Scope Card, Claim Cards, Cornell Notes Grid, and Custom Report modal.
2. **`frontend/style.css`**
   - Application styling: modern responsive design, dark-mode elements, Cornell layout grid, typography, and status badges.
3. **`frontend/app.js`**
   - Client application logic: request sequencing (`currentSubmissionSeq`), inert rendering (`textContent`), multi-tab session management, evidence counters, and report generation triggers.
4. **`frontend/test_runner.html`**
   - In-browser automated test runner covering all client states and ordering protections.
5. **`docs/**`**
   - Specifications (`docs/specs/`), architectural notes, and owner guides (`docs/HOW_IT_WORKS.md`). (Note: `docs/archive/` is reserved for historical items and should not be consulted by agents).

---

## 3. Verification Commands for Safe Edits

After modifying any file in Tier 3 (or completing work in Tier 2):

```powershell
# 1. Verify all 164 Python unit & integration tests (including headless Chrome ordering test)
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v

# 2. Check git status to ensure zero untracked noise
git status -s
```
