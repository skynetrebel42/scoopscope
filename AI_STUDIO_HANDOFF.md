# ScoopScope — Google AI Studio Migration & Architecture Handoff

**Document Version**: 1.0  
**Baseline Git Commit**: `52e4722` (Milestone 5A Close-Out)  
**Target Transfer Branch**: `transfer/ai-studio-handoff`  
**Repository Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope`  
**Repository URL**: `https://github.com/skynetrebel42/scoopscope`  

---

## 1. Executive Summary & Purpose

This handoff document prepares the **ScoopScope** project for trial in **Google AI Studio** as the primary build and development environment.

ScoopScope is an evidence-first claim investigation tool designed to bring journalistic rigor, strict provenance, and cryptographic verifiability to fact checking. It adheres to a non-negotiable core tenet:
> **A search engine snippet is never verified evidence.**  
> Findings must reference examined verbatim passages extracted from real, safely retrieved web pages. If evidence is inaccessible or insufficient, the claim status is strictly **`unresolved`**, never false. Automated truth scores, simulated verdicts, and hallucinated citations are forbidden by design.

This document outlines the current working implementation, architecture, runtime requirements, API schemas, testing status, security boundaries, and compatibility considerations for Google AI Studio.

---

## 2. Current Implemented Behavior vs. Planned Features

### Currently Implemented & Verified (Milestones 1–5A, Decisions 001–020)

| Feature Area | Implemented Capabilities |
|---|---|
| **Intake & Scope Clarification** | • Accepts inquiry statements up to 10,000 characters and optional source URLs.<br>• Runs up to 2 clarification rounds offering exactly 3 coherent choices + free-text input.<br>• Produces an in-place editable **Confirmed Inquiry Scope** card.<br>• Editing scope immediately invalidates in-flight or completed research to prevent drift.<br>• Flags Los Angeles civic ambiguity between LA City (`lacity.gov`), LA County (`lacounty.gov`), and independent municipalities. |
| **Claim Decomposition** | • Decomposes compound assertions into discrete, checkable subclaims while preserving original author wording, caveats, and causal logic.<br>• Classifies claims into `factual`, `opinion`, `prediction`, or `causal`. |
| **Targeted Search & Network Sandboxing** | • Exactly 1 claim investigated per user action.<br>• Generates targeted queries with `-filetype:pdf` to avoid binary PDF parsing.<br>• Caps queries at max 2 requests to Serper Google Search API, max 5 hits per query.<br>• Hardened HTTP fetcher fetches max 3 candidate web pages per claim.<br>• Pre-connection DNS check and socket-level destination IP pinning before TLS handshake, blocking loopback, RFC 1918, link-local, CGNAT, and multicast IPs (defeats TOCTOU DNS rebinding SSRF).<br>• Enforces 1 MB decompressed size ceiling, max 3 redirects with re-validation, 10s connect / 30s fetch timeouts, and an overall 90-second monotonic research deadline.<br>• Prioritizes official municipal/state domains matching identified civic jurisdictions. |
| **Verbatim Passage Extraction & Provenance** | • Strips scripts, ads, and HTML chrome to clean plain text.<br>• Extracts 1 to 5 verbatim quotes per claim.<br>• Verifies character-offset math (`extracted_text[start:end] == exact_passage`), guaranteeing zero AI quote hallucination.<br>• Defensive date provenance: extracts publication/update dates strictly from JSON-LD, `<meta>` tags, `<time>` tags, or visible bylines (never HTTP headers or URL digits).<br>• Generates W3C `#:~:text=` text fragment deep links for Chromium browsers to highlight exact sentences on the live publisher site. |
| **Cornell Notes Evidence Workspace** | • Two-column paired layout: claim assertion on the left, verbatim quotes with dates, relevance notes, and jurisdiction badges on the right.<br>• Per-quote checkbox to add/remove quotes from active Evidence Bank.<br>• One-click **"Copy Quote + Citation"** button formatting quote + citation deterministically with clipboard copy and visual feedback.<br>• Technical Audit Drawer (`<details>`) collapsed by default, containing raw Serper hits, HTTP network metadata, and full plain text viewers.<br>• Claim results accordion: auto-collapses prior claim results when initiating discovery on another claim. |
| **Multi-Tab Workspace & Persistence** | • Multi-tab session management (`+ New Session` button) allowing concurrent investigations without interference.<br>• Request-ordering tokens (`currentSubmissionSeq`) and promise binding (`originSessionId`) preventing cross-tab pollution from async network returns.<br>• Automatic `localStorage` persistence under key `scoopscope_workspace_v1` across browser refreshes.<br>• One-click instant `#btn-clear-workspace` reset with zero blocking popups.<br>• Empty-tab layout hiding `#custom-report-section` until evidence exists. |
| **Custom Report Studio & Export** | • Synthesizes executive briefings across 4 vibes: **Objective Brief**, **Cornell Study**, **Fact Check**, **Deep Dive**.<br>• Deterministic Citation Style Selector: Standard Numbered, APA 7th ed (`(n.d.)` on absent dates), MLA 9th ed (`Accessed <date>` on absent dates) with zero author/date fabrication.<br>• Deduplicated Works Cited bibliography by source URL.<br>• One-click export actions: Copy Markdown, Copy Plain Text, Download `.md` report. |

### Planned / Backlog Features (NOT Yet Implemented)

- **Evidence & Jurisdiction Filtering**: Filter pills and dropdown selectors above the Cornell Notes evidence board (by jurisdiction badge, date range, or domain classification).
- **Portable Workspace JSON Export/Import**: Exporting the entire multi-tab workspace state to a downloadable `.json` file and importing/restoring it on another machine or browser.
- **Contradiction & Material Qualification Callouts**: Side-by-side visual contrast cards highlighting contradictory evidence across retrieved sources.
- **Truth Scores / Verdict Simulation**: **EXPLICITLY REJECTED BY DESIGN**. ScoopScope will never calculate truth percentages or simulated verdicts; findings are presented for human audit and inspection.

---

## 3. Technology Stack & Run Commands

### Stack Overview
- **Backend**:
  - Python 3.11+ (verified on 3.11–3.14)
  - FastAPI 0.143+ & Uvicorn 0.54+ (ASGI HTTP server)
  - `google-genai` 2.30+ (Google GenAI Python SDK)
  - `pydantic` 2.14+ (data validation and structured schema contracts)
  - `httpx` 0.28+ (asynchronous HTTP client)
  - Custom socket networking using Python standard library `socket` for SSRF IP-pinning
  - Static file hosting via FastAPI `StaticFiles` mounted at `/`
- **Frontend**:
  - Vanilla HTML5, CSS3, modern Vanilla JavaScript (ES2022+)
  - Zero build tooling required: no Node.js build step, no Webpack, no Vite, no Babel, no Tailwind CLI
  - Single-page application architecture with multi-tab state engine
  - Strict DOM immutability and inert rendering (`textContent`, `document.createTextNode()`)
  - Client-side storage via browser `localStorage`

### Exact Local Run Commands

#### 1. Backend API & Static Web Server
Run from the repository root in PowerShell:
```powershell
cd c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
*(On macOS / Linux)*:
```bash
cd backend
python3 -m uvicorn app.main:app --reload --port 8000
```
- Web Application: `http://localhost:8000/`
- Interactive OpenAPI / Swagger Documentation: `http://localhost:8000/docs`
- OpenAPI Specification JSON: `http://localhost:8000/openapi.json`

#### 2. Automated Python Test Suite (Offline)
Run all 11 test suites from the repository root:
```powershell
cd c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

#### 3. In-Browser Test Suite
Open `frontend/test_runner.html` directly in Google Chrome, Microsoft Edge, or any modern web browser.

---

## 4. Required Services & Environment Variable Names

### Required Services
1. **Google Gemini API**:
   - Used for: inquiry clarification (`/api/clarify`), claim extraction (`/api/extract`), passage relevance evaluation & research synthesis (`/api/research`), and report generation (`/api/report`).
   - Default Model: `gemini-flash-lite-latest`
   - Provider: Google AI Studio (`https://aistudio.google.dev/apikey`)
2. **Serper Google Search API**:
   - Used for: external web search queries (`https://google.serper.dev/search`).
   - Provider: Serper (`https://serper.dev`)

### Environment Variable Names
Configure these in `backend/.env` (or root `.env`):

| Variable Name | Required? | Default Value | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | *None* | Google AI Studio API key. |
| `SERPER_API_KEY` | **Yes** (for live search) | *None* | Serper.dev Google Search API key. |
| `GEMINI_MODEL` | No | `gemini-flash-lite-latest` | Target Gemini model identifier. |
| `MAX_INPUT_CHARS` | No | `10000` | Maximum length of input text. |
| `LLM_TIMEOUT_SECONDS` | No | `90` | Monotonic timeout for individual Gemini API calls. |
| `LLM_MAX_RETRIES` | No | `2` | Maximum retry attempts for transient Gemini errors (3 total attempts). |
| `RESEARCH_TIMEOUT_SECONDS` | No | `90` | Overall monotonic research deadline across search, fetch, and extraction. |

*(Reference files: [backend/.env.example](file:///c:/Users/minhb/OneDrive/Desktop/Projects/ScoopScope/backend/.env.example) and [.env.example](file:///c:/Users/minhb/OneDrive/Desktop/Projects/ScoopScope/.env.example))*.

---

## 5. API Endpoints & Request/Response Structures

### 1. `GET /api/health`
Checks backend status and credential readiness.
- **Request**: No parameters or body.
- **Response `200 OK`**:
  ```json
  {
    "status": "ok",
    "credentials_configured": true,
    "search_credentials_configured": true,
    "model": "gemini-flash-lite-latest"
  }
  ```

---

### 2. `POST /api/clarify`
Interactive inquiry clarification, scope confirmation, and claim decomposition.
- **Request Body (`ClarificationRequest`)**:
  ```json
  {
    "text": "Did the City of Los Angeles ban gas stoves in new buildings?",
    "source_url": "https://example.com/article",
    "round_index": 1,
    "exchanges": [],
    "explicit_broad": false
  }
  ```
- **Response Body (`ClarificationResponse`)**:
  ```json
  {
    "submission_id": "a1b2c3d4e5f6",
    "submitted_text": "Did the City of Los Angeles ban gas stoves in new buildings?",
    "source_url": "https://example.com/article",
    "purpose": "check_claim",
    "is_clear": true,
    "clarification_needed": false,
    "round_index": 1,
    "max_rounds_reached": false,
    "question": null,
    "choices": null,
    "interpreted_question": "Did the Los Angeles City Council pass an ordinance prohibiting natural gas infrastructure in new residential and commercial construction?",
    "material_uncertainties": [],
    "subclaims": [
      {
        "id": "claim_01",
        "original_wording": "ban gas stoves in new buildings",
        "normalized_assertion": "The City of Los Angeles enacted an ordinance prohibiting gas appliances in new buildings.",
        "claim_type": "factual",
        "explicit_date": null,
        "explicit_location": "City of Los Angeles",
        "explicit_quantity": null,
        "qualifications": null
      }
    ],
    "limitation_note": null,
    "status_message": "Inquiry scope confirmed.",
    "clarified_at": "2026-10-22T22:00:00Z"
  }
  ```
- **Status Codes**: `200 OK`, `400 Bad Request` (empty or oversized input), `503 Service Unavailable` (missing API keys or adapter failure).

---

### 3. `POST /api/extract` *(Legacy Direct Extraction)*
Direct structured extraction of claims without clarification rounds.
- **Request Body (`ExtractionRequest`)**:
  ```json
  {
    "text": "The European Union banned imports of hormone-treated American beef in 1989.",
    "source_url": "https://example.com/news"
  }
  ```
- **Response Body (`ExtractionResponse`)**:
  ```json
  {
    "submission_id": "sub_12345",
    "submitted_text": "The European Union banned imports of hormone-treated American beef in 1989.",
    "source_url": "https://example.com/news",
    "claims": [
      {
        "id": "claim_8f9a2",
        "original_wording": "The European Union banned imports of hormone-treated American beef in 1989.",
        "normalized_assertion": "The EU instituted an import ban on hormone-treated beef originating from the United States in 1989.",
        "claim_type": "factual",
        "explicit_date": "1989",
        "explicit_location": "European Union",
        "explicit_quantity": null,
        "qualifications": null
      }
    ],
    "extracted_at": "2026-10-22T22:00:00Z",
    "status_message": "Claims extracted. Evidence research not yet performed."
  }
  ```

---

### 4. `POST /api/research`
Executes bounded search, SSRF-pinned page fetching, verbatim passage extraction, and synthesis for a single claim.
- **Request Body (`ResearchRequest`)**:
  ```json
  {
    "submission_id": "a1b2c3d4e5f6",
    "claim_id": "claim_01",
    "claim_text": "The City of Los Angeles enacted an ordinance prohibiting gas appliances in new buildings.",
    "claim_type": "factual",
    "explicit_location": "City of Los Angeles",
    "explicit_date": null,
    "source_url": null,
    "override_query": null,
    "confirmed_scope_question": "Did the Los Angeles City Council pass an ordinance prohibiting natural gas infrastructure in new residential and commercial construction?"
  }
  ```
- **Response Body (`ResearchResponse`)**:
  ```json
  {
    "submission_id": "a1b2c3d4e5f6",
    "claim_id": "claim_01",
    "queries_used": [
      {
        "query": "City of Los Angeles gas appliances new buildings ordinance -filetype:pdf",
        "purpose": "primary_factual_check"
      }
    ],
    "search_hits": [
      {
        "title": "LA City Council approves mandate for all-electric new buildings",
        "url": "https://lacity.gov/news/all-electric-ordinance",
        "snippet": "In December 2022, the Los Angeles City Council voted to require all-electric construction...",
        "is_snippet_only": true,
        "position": 1
      }
    ],
    "retrieved_sources": [
      {
        "url": "https://lacity.gov/news/all-electric-ordinance",
        "domain": "lacity.gov",
        "title": "LA City Council approves mandate for all-electric new buildings",
        "publication_date": "2022-12-07",
        "retrieval_status": "retrieved",
        "jurisdiction_tag": "LA City Official",
        "jurisdiction_code": "la_city"
      }
    ],
    "candidate_passages": [
      {
        "passage_id": "pass_01",
        "source_url": "https://lacity.gov/news/all-electric-ordinance",
        "source_title": "LA City Council approves mandate for all-electric new buildings",
        "exact_passage": "The Los Angeles City Council voted unanimously on Wednesday to require new buildings in the city to be all-electric, phasing out natural gas hookups.",
        "context_surrounding": "...climate initiatives. The Los Angeles City Council voted unanimously on Wednesday to require new buildings in the city to be all-electric, phasing out natural gas hookups. The ordinance takes effect...",
        "start_offset": 1240,
        "end_offset": 1391,
        "publication_date": "2022-12-07",
        "relevance_explanation": "Directly confirms that the City Council enacted a mandate requiring all-electric construction in new buildings.",
        "jurisdiction_tag": "LA City Official",
        "jurisdiction_code": "la_city"
      }
    ],
    "researched_at": "2026-10-22T22:01:15Z",
    "status_message": "Research complete. 1 source examined.",
    "completed_in_seconds": 3.82,
    "search_failure_message": null,
    "inquiry_synthesis": "Retrieved records from official Los Angeles municipal sources confirm that in December 2022, the City Council enacted an ordinance requiring all-electric construction in newly built structures.",
    "suggested_next_queries": [
      "Los Angeles all-electric building ordinance effective date exemptions"
    ]
  }
  ```
- **Status Codes**: `200 OK`, `400 Bad Request`, `502 Bad Gateway` (search provider upstream error), `503 Service Unavailable` (missing API keys).

---

### 5. `POST /api/report`
Synthesizes a structured briefing from user-selected Evidence Bank quotes.
- **Request Body (`ReportRequest`)**:
  ```json
  {
    "inquiry_title": "City of Los Angeles Gas Appliance Mandates",
    "report_vibe": "objective_brief",
    "citation_style": "apa",
    "include_summary": true,
    "include_evidence_bank": true,
    "include_works_cited": true,
    "include_open_questions": true,
    "custom_focus": null,
    "selected_passages": [
      {
        "passage_id": "pass_01",
        "exact_passage": "The Los Angeles City Council voted unanimously on Wednesday to require new buildings in the city to be all-electric, phasing out natural gas hookups.",
        "source_url": "https://lacity.gov/news/all-electric-ordinance",
        "source_title": "LA City Council approves mandate for all-electric new buildings",
        "publication_date": "2022-12-07",
        "jurisdiction_tag": "LA City Official",
        "jurisdiction_code": "la_city"
      }
    ],
    "sources": [
      {
        "url": "https://lacity.gov/news/all-electric-ordinance",
        "domain": "lacity.gov",
        "title": "LA City Council approves mandate for all-electric new buildings",
        "publication_date": "2022-12-07",
        "jurisdiction_tag": "LA City Official",
        "jurisdiction_code": "la_city"
      }
    ]
  }
  ```
- **Response Body (`ReportResponse`)**:
  ```json
  {
    "report_title": "City of Los Angeles Gas Appliance Mandates — Objective Brief",
    "vibe_used": "objective_brief",
    "markdown_content": "# Executive Briefing: City of Los Angeles Gas Appliance Mandates\n\n## 1. Summary of Evidence\n...",
    "selected_quote_count": 1,
    "source_count": 1,
    "generated_at": "2026-10-22T22:02:00Z",
    "is_fallback": false
  }
  ```

---

## 6. Existing Tests & Known Results

### Test Suite Inventory
The test suite consists of **11 test modules** in `backend/tests/` and **1 in-browser HTML suite**:

1. `test_clarification.py`: 2-round clarification, 3 choices + free text, intake bounds, jurisdiction ambiguity.
2. `test_extraction.py`: Claim decomposition, schema adherence, input validation, error handling.
3. `test_la_jurisdiction.py`: 92 unit and integration tests verifying official domain classification (`lacity.gov`, `lacounty.gov`, California state, regional agencies, and 11 independent municipal cities like Long Beach, Santa Monica, Pasadena).
4. `test_milestone_3b.py`: Sticky inquiry bar, Cornell notes paired model, defensible date extraction, and Custom Report synthesis.
5. `test_passage_extractor.py`: Mathematical character-offset verification (`extracted_text[start:end] == exact_passage`), date extraction from JSON-LD / HTML meta / time tags, and text normalization.
6. `test_report_and_extraction.py`: Citation formatting (Standard Numbered, APA 7th ed with `(n.d.)`, MLA 9th ed with `Accessed <date>`), zero author/date fabrication, and Markdown report export.
7. `test_research_endpoint.py`: Bounded search execution, Serper failure preservation, credential check, and 502/503 status code handling.
8. `test_safe_fetcher.py`: Socket-level destination IP pinning, loopback/RFC 1918/CGNAT/multicast blocking, 1 MB ceiling, redirect limits, and connection timeouts.
9. `test_search_contract.py`: `SearchProvider` protocol contracts, frozen snippet semantics, query bounds.
10. `test_serper_provider.py`: Serper integration, rate-limiting, credential redaction from logs and exceptions, retry logic.
11. `test_frontend_ordering.py`: Request-ordering sequence tokens (`currentSubmissionSeq`), selector inventory AST/regex integrity test (`test_selector_inventory`), multi-tab async search isolation, and live headless Chrome smoke tests.
12. `frontend/test_runner.html`: In-browser client test runner verifying UI states, storage persistence, and Cornell Notes interactivity.

### Latest Test Results
- **Pure Offline Python Tests**: **276 passed** (100% passing across 10 backend suites + `test_selector_inventory`).
- **Normal Host Execution (Outside Sandboxed Terminal)**: **285 passed** (100% passing across all 11 test suites).
- **In-Browser HTML Runner**: **100% passing** with zero assertion errors.

### Known Environmental Nuances & Warnings
1. **Sandboxed Terminal Browser Launch Boundary**:
   - In sandboxed developer shells (such as Antigravity IDE terminal sandbox), Windows IPC pipes and named pipes required by Chromium are restricted, causing `test_frontend_ordering.py` headless browser tests to fail with process spawn errors or temp directory access denials (`C:\Users\minhb\AppData\Local\Temp\pytest-of-minhb`).
   - This is an environment sandbox boundary, not a code defect. When executed in standard host PowerShell outside the sandbox, all 285 tests pass without failure.
2. **Upstream Deprecation Warnings** (Documented in `KNOWN_ISSUES.md`):
   - `google.genai.types._UnionGenericAlias`: Slated for removal in Python 3.17; zero impact on Python 3.11–3.14.
   - `fastapi.testclient`: Starlette notice regarding `httpx` vs `httpx2`; zero impact on test correctness.

---

## 7. Evidence & Citation Requirements That Must Survive Migration

All future developers, agents, and build environments operating on ScoopScope must uphold these non-negotiable rules:

1. **Zero Hallucination / Fabrication**:
   - Never invent sources, quotes, citations, fallback choices, synthetic subclaims, or truth scores.
   - If evidence cannot be retrieved, the finding is strictly **`unresolved`**, never false.
   - Preserves contradictory evidence and material qualifications; never smooths over disagreements.
2. **Defensible Date Provenance Only**:
   - Extract publication/update dates strictly from JSON-LD metadata, HTML `<meta>` tags, HTML `<time>` tags, or visible bylines.
   - Never infer dates from HTTP `Date` headers or URL path digits.
   - When a source has no declared publication date, citations must strictly output `(n.d.)` in APA style or omit the date and use `Accessed <date>` in MLA style. Never invent today's date as the publication date.
3. **Verbatim Character-Offset Invariant**:
   - Every candidate passage must satisfy `extracted_text[start:end] == exact_passage` against the downloaded page text. Paraphrasing or rewrites by LLMs are forbidden.
4. **Socket-Level SSRF Hardening**:
   - Resolve destination DNS before connecting, validate against private/loopback/link-local/CGNAT/multicast IP ranges, and pin the socket directly to the validated IP before the TLS handshake.
   - Enforce 1 MB maximum response size, max 3 redirects with re-validation on every hop, and 10s connect / 30s fetch limits.
5. **Inert DOM Rendering**:
   - All external titles, URLs, snippets, passages, and citations must be inserted into the DOM strictly via `textContent` or `document.createTextNode()`. Zero raw `innerHTML` injection of untrusted strings.
6. **Strict Retrieval Budgets**:
   - Exactly 1 claim investigated per user action.
   - Max 2 Serper queries per action (capped at 5 hits per query).
   - Append `-filetype:pdf` to all queries.
   - Max 3 candidate pages fetched per research action.
   - Monotonic 90-second overall research deadline.

---

## 8. Compatibility Analysis: Google AI Studio Node.js Web Runtime vs. Python/FastAPI

### The Architectural Mismatch
Google AI Studio's prompt-to-app web builder and preview environment is designed around **Node.js client/server environments** (such as WebContainers, Vite, Next.js, or Express) running in the user's browser or containerized runners.

In contrast, ScoopScope's backend is implemented in **Python 3.11+ using FastAPI, Uvicorn, and low-level Python networking**.

### Specific Compatibility Concerns
1. **Low-Level Socket SSRF IP-Pinning (`safe_fetcher.py`)**:
   - ScoopScope prevents Server-Side Request Forgery and TOCTOU DNS rebinding by intercepting socket creation (`socket.socket`) and binding TCP handshakes directly to pre-validated IP addresses.
   - Standard browser WebContainers and serverless Node.js edge functions do not provide raw TCP socket-pinning primitives or support custom DNS-pinned socket layers.
2. **Python `google-genai` SDK & Pydantic Validation**:
   - The backend uses the official Google GenAI Python SDK (`google-genai`) with Pydantic v2 structured output schemas (`response_schema=...`).
   - Translating this to Node.js requires switching to `@google/genai` or `@google/generative-ai` with Zod or TypeBox schemas, risking subtle serialization mismatches and breaking existing contracts.
3. **API Key Security in Client-Side Environments**:
   - If AI Studio attempts to run ScoopScope purely in the client browser (SPA without a private server), `GEMINI_API_KEY` and `SERPER_API_KEY` would be exposed in client network requests, violating security guardrails.
4. **285 Passing Tests**:
   - The repository contains 285 battle-tested Python unit and integration tests. A rewrite would discard this verified test harness.

### Why the Backend Must NOT Be Rewritten
Per Owner instructions: **"Do not rewrite it."**  
Rewriting the backend into Node.js would introduce security vulnerabilities (compromising SSRF IP-pinning), invalidate the verbatim character-offset provenance math, discard 285 passing tests, and delay evaluation.

### Recommended Deployment Architectures for AI Studio

| Approach | Architecture | Feasibility & Pros | Notes |
|---|---|---|---|
| **Option A: Hosted FastAPI + AI Studio Frontend (Recommended)** | Deploy the existing Python FastAPI backend to Google Cloud Run, Cloud Shell, or a local server. Connect the AI Studio web frontend to this backend via `http://localhost:8000` or a Cloud Run URL. | **High**: Zero code changes. Preserves 100% of Python security, socket pinning, and test coverage. Frontend remains vanilla JS. | Requires setting `CORSMiddleware` (already configured to `allow_origins=["*"]` in dev) and configuring API base URL. |
| **Option B: Dual-Process Container (Project IDX / Cloud Workstation)** | In Google Project IDX or Cloud Shell environments where both Python 3.11+ and Node.js exist, launch Uvicorn as a background service (`python -m uvicorn app.main:app --port 8000`). | **High**: Runs natively. Uvicorn serves both the API and the static files directly on port 8000, or a Node process reverse-proxies requests. | Ideal if AI Studio provides Linux VM or container shell access. |
| **Option C: Node Reverse-Proxy Shim** | If AI Studio strictly expects a `package.json` and Node server to start the project, add a lightweight `server.js` (Express or Vite) that serves static assets from `frontend/` and reverse-proxies `/api/*` to the Python backend process. | **Medium**: Meets Node-first builder requirements while keeping Python backend untouched. | Python runtime must still be available in the container. |

---

## 9. Smallest Next Task to Run One Complete Investigation

To verify that ScoopScope is fully operational in the new environment, execute this single end-to-end smoke test:

1. **Configure Environment**:
   Ensure `GEMINI_API_KEY` and `SERPER_API_KEY` are set in `backend/.env`.
2. **Start Backend**:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```
3. **Open Application**:
   Navigate to `http://localhost:8000/`.
4. **Input Test Statement**:
   Paste the following into `#input-text`:
   > *"The City of Los Angeles passed an ordinance banning natural gas hookups in new buildings in December 2022."*
5. **Confirm Scope**:
   Click **"Start Investigation"**. If prompted with clarification options, confirm the checkable question on the Confirmed Inquiry Scope card.
6. **Execute Research**:
   Click **"Find sources"** on Claim 1. Wait for the loading banner to complete (under 10 seconds).
7. **Verify Cornell Notes**:
   - Check that verbatim quotes appear with green official badges (`[LA City Official]`).
   - Click **"Find exact line in source ↗"** to test W3C text fragment link generation.
   - Click **"Copy Quote + Citation"** and verify clipboard confirmation.
8. **Synthesize Report**:
   Select the quote checkbox into the Evidence Bank, choose **"Objective Brief"**, and click **"Synthesize Custom Report"**. Verify that the executive brief is generated with a clean Works Cited bibliography.
