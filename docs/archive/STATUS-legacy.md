# ScoopScope — Project Status

Last updated: 2026-10-15

## Current Status: Milestone 3A Complete

---

## Workspace & Repository Confirmation
- **Canonical Workspace & Git Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\`
- **Milestone 3A Scope**: Clarify and Confirm the Inquiry
- **Milestone 2C Baseline Commit**: `5666397` (Review package: `ScoopScope_2C_Review.zip`)
- **Resolved Path**: Clean environment. Zero secrets committed or exposed.

---

## Milestone 3A — Clarify and Confirm the Inquiry (COMPLETE)

### 1. Inquiry Intake & Clarification Endpoint (`backend/app/main.py`, `backend/app/models.py`)
- **Endpoint**: `POST /api/clarify`
- **Pydantic Schemas**:
  - `InvestigationPurpose`: `check_claim`, `understand_context`, `trace_origin`.
  - `ClarificationExchange`: Tracks round index (1 or 2), question, selected choice, and free text.
  - `ClarificationRequest`: Accepts text, source_url, round_index (ge=1, le=3), history exchanges, and explicit_broad flag. Max 10,000 characters.
  - `ClarificationResponse`: Returns structured analysis, `is_clear`, `clarification_needed`, `round_index`, `max_rounds_reached`, `question`, `choices` (normalized to exactly 3 choices), `interpreted_question`, `material_uncertainties`, `subclaims` (with UUIDs), `limitation_note`, and `status_message`.
- **Legacy Compatibility**: `POST /api/extract` remains fully functional for prior integrations.

### 2. Gemini Clarification Adapter (`backend/app/gemini_adapter.py`)
- **Structured Schema Enforced**: Uses `response_schema=ClarificationAnalysisLLM` with `CLARIFICATION_SYSTEM_INSTRUCTION`.
- **Bounded Rounds Enforcement**:
  - Unclear input at Round 1 (0 exchanges): prompts single highest-value question with exactly 3 coherent choices answering the same dimension + free text.
  - Round 2 (1 exchange): allows returning a 2nd clarifying question (`clarification_needed=True, max_rounds_reached=False`) when `is_clear=False`.
  - **Third Round Impossible**: Hard ceiling enforced when `len(exchanges) >= 2`, `round_index >= 3`, or `explicit_broad=True` (`max_rounds_reached=True`, `clarification_needed=False`, `is_clear=True`). Any lingering ambiguity is documented in `material_uncertainties`.
  - Clear input: immediately sets `is_clear=True`, `clarification_needed=False`, returning editable interpreted question and checkable subclaims without redundant questions.
- **Strict Validation & No Invented Particulars**:
  - When clarification is needed, requires valid question and at least 3 distinct choices; raises `GeminiAdapterError` instead of fabricating generic fallback choices.
  - Subclaims remain `[]` if no checkable claims are extracted (no fabricated fallback factual subclaim).
  - Leaves unstated details as unknown (e.g. unspecified chemicals in beef remain unknown; never guesses hormones without evidence).
  - Preserves geographic designations (keeps "Europe" without silently assuming "EU" without a visible scope note).
  - Compound assertions: decomposes into linked subclaims while preserving original wording and causal relationships.
  - Temporal fidelity: current-status inquiries are never converted into historical investigations, or vice versa.

### 3. Frontend Intake Flow & Confirmed Scope UI (`frontend/index.html`, `frontend/style.css`, `frontend/app.js`)
- **Interactive Clarification Stage**:
  - Renders clarification card for unclear inputs with round badge ("Round 1 of 2", "Round 2 of 2"), prominent question, exactly 3 distinct choice buttons, and a free-text input with "Continue" button.
  - Disables broad inquiry button and free-text input during clarification loading to prevent duplicate requests.
  - "Investigate broad inquiry across all aspects" option available to proceed directly.
- **Confirmed Scope Card & Subclaim Research Selection**:
  - Prominently displays: `"We will investigate: [editable question]"`.
  - Allows in-place editing of the inquiry question with "Update" action.
  - Tracks `scopeQuestionManuallyEdited`: when multiple subclaims exist and scope has not been manually edited, researching a claim uses that claim's specific normalized assertion. When `scopeQuestionManuallyEdited` is true (or single claim), research targets the confirmed scope question.
  - Invalidation on scope edit: editing the scope question or clicking Update increments `activeResearchSeq`, resets `activeResearchClaimId`, and clears all rendered research panels and loading states on claim cards.
  - Displays Material Unresolved Assumptions as an inspectable bullet list.
  - Displays honest limitation banner when purpose is `understand_context` or `trace_origin`:
    *"Dedicated context and origin tracing pipelines are planned for future milestones. You can investigate this as an editable factual research question below."*
- **Honest Claim Classification**:
  - Renamed displayed `factual` badge to **"Checkable claim"** with tooltip:
    *"Checkable claim: A statement asserting a verifiable fact. This is a classification, not a verified finding."*
- **Replaced Stale Copy**:
  - Eliminated stale "claim extraction only" and "research not yet performed" notices in favor of live per-stage status indicators.
- **Rigorous Sequence & Invalidation Protection**:
  - Modifying draft statement or source URL immediately increments `currentSubmissionSeq`, invalidates active clarification, hides clarification cards, clears in-flight research (`activeResearchSeq++`), and marks existing rendered claims as outdated with disabled research buttons.

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
  - **F1 Search Failure Preservation**: Distinguishes upstream search failure (401/403 credit exhaustion, 429 rate limit, 500 retry exhaustion) from legitimate zero-hit searches. When no supplied `source_url` exists, propagates `SearchProviderError` to return HTTP 502/503 with sanitized diagnostics. When a supplied `source_url` exists, safely extracts evidence from the supplied source while setting `search_failure_message` on `ResearchResponse`, surfacing an explicit alert banner in the UI.
  - **F3 Cooperative Extraction Deadline**: Synchronous cleaning and passage extraction accept a monotonic `deadline: float`. `HTMLTextExtractor` verifies the deadline every 25 tags, `clean_html_to_text` feeds in 16KB chunks checking deadline, and `extract_candidate_passages` checks deadline before paragraph splitting, scoring, and passage assembly. A post-execution monotonic check ensures over-budget runs can never return ordinary success, marking `status_message` with `TIMEOUT` while preserving completed evidence.

### 6. Frontend UI & State Ownership (`frontend/app.js`, `frontend/style.css`)
- **Target User Experience**:
  - Claim cards render a dedicated "Find sources" button.
  - Clicking "Find sources" transitions button to loading state ("Researching…") with a spinner and 90s notice.
  - Double-clicks and concurrent research actions on the same claim are blocked.
  - **F2 Switching Claims Ownership**: When switching between claims (e.g. starting A then B), each card's `finally` block removes its loading indicator and restores its button to "Find sources" (or disabled with tooltip if an input edit invalidated the snapshot). Shared active research claim state is guarded by request sequence identity (`researchSeq === activeResearchSeq && activeResearchClaimId === claim.id`), so completing an earlier superseded request never resets newer in-flight work. Stale responses from superseded requests are discarded.
  - Modifying input text or submitting a new text immediately increments `activeResearchSeq` and invalidates any in-flight research, preventing stale results or error states from taking ownership.
  - External search snippets and retrieved pages are presented in distinctly labeled sections:
    - Search Hits: Marked with prominent "Snippet Only #N" badges and disclaimers stating that snippets only indicate index presence and never count as examined evidence. If search failed, a distinct notice indicates search unavailability rather than an empty index.
    - Retrieved Sources: Display source URL, HTTP status, resolved IP, size in KB, redirect count, and audit status (`Retrieved (200)`, `SSRF Blocked`, or `Inaccessible`).
    - Verbatim Passages: Render exact quoted excerpts with character offsets and a "Show surrounding context" toggle.
    - Truncated Raw Audit Sample: `raw_text` stores only the first 5,000 characters of raw downloaded content as an API debug/audit sample; it is not complete original-source provenance and does not validate passages occurring beyond that prefix.
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

## Automated Test Suite (132 passing — all fixture-based or mocked)

| Suite | Tests / Assertions | What it covers | Status |
|---|---|---|---|
| `test_clarification.py` | 10 tests | Milestone 3A intake clarification, 5 acceptance checks, DACA/beef/Obama samples, temporal distinction, 3 coherent choices, 2-round bound, direct confirmation for clear claims, context/origin limitation notes | PASSED |
| `test_frontend_ordering.py` | 1 test (108 browser assertions) | Headless Chrome browser test: 10 test suites covering request ordering, stale discard, Try Again, research action, snippet rendering, passage rendering, draft edit invalidation, inert text XSS protection, claim switching A->B (F2), and Milestone 3A clarification, 3 option buttons, scope question editing, and invalidation | PASSED |
| `test_extraction.py` | 14 tests | Claim extraction, validation, error handling, unique IDs | PASSED |
| `test_search_contract.py` | 9 tests | `SearchProvider` Protocol, `SearchResultHit` snippet immutability, date/dependence defaults, query generation | PASSED |
| `test_safe_fetcher.py` | 65 tests | IP ranges, IPv4-mapped IPv6, CGNAT, scheme/standard & bad port/credential validation (R3), public success, private/loopback rejection, public-to-private redirect block, DNS rebinding block, 3-hop redirect limit, MIME rejection, 1MB size limit, cancellable deadline and slow DNS enforcement with elapsed bounds (R2), socket connection enforcement | PASSED |
| `test_serper_provider.py` | 12 tests | Serper contract adherence, missing key handling, search response parsing, 5-hit cap, 401/403/429 status mapping, bounded 5xx retries, outbound attempt accounting, secret redaction | PASSED |
| `test_passage_extractor.py` | 9 tests | Script/style stripping, entity decoding (single decode R1), exact substring offsets, provenance verification, URL deduplication, void element handling (<embed> R1), table cell number separation (R1), plain-text MIME preservation (<exception> R1) | PASSED |
| `test_research_endpoint.py` | 12 tests | Orchestrator flow with mock provider & fetcher (injected DNS R5), candidate page budget cap (3), partial fetch failures, 503 on missing credentials, cancellable orchestrator deadline enforcement (R2), malformed port error isolation (R3), search provider failure propagation on 401/403/429/500 (F1), partial evidence preservation on search failure with source URL (F1), legitimate 0-hit search distinguishability (F1), cooperative synchronous extraction deadline enforcement on large documents (F3) | PASSED |
| **Total** | **132 passed** | Full regression and Milestone 3A capabilities | **ALL PASSED (31.24s)** |

---

## Live vs. Mocked Results Summary

### 1. Mocked & Local Integration Verification (Repaired Snapshot)
- Full orchestrator execution verified offline with mock search provider and mock HTTP network backend.
- DNS resolution injected in offline tests to prevent reliance on host system resolver.
- Candidate budgets (max 2 queries, max 5 hits/query, max 3 fetched pages) verified.
- Programmatic character offsets verified (`extracted_text[start:end] == exact_passage`).
- Headless Chrome browser suite verified with 88 assertions across 9 test suites (stale response discard, edit-during-extraction, URL-only edits, edit-during-research, Try Again recovery, research action, inert rendering, claim switching A then B in both resolution orders with button restoration).

### 2. Prior Live Smoke Results (Historical Builder Evidence)
- The live smoke run against live Gemini and Serper APIs was conducted during the initial Milestone 2C verification pass:
  - Input: `"Mayor Karen Bass took office in December 2022 as the 43rd Mayor of Los Angeles."`
  - Factual claim extracted and researched in 6.26s.
  - Queries: 1 query sent to Serper (1 of 2 allowed search requests).
  - Outbound attempts: `total_requests_made` instrumented and verified <= 2.
  - Search hits: 5 hits returned (capped at 5), all marked `is_snippet_only: True`.
  - Candidate pages fetched: 3 pages attempted (limit 3):
    * `https://lacity.gov/news/karen-bass-sworn-43rd-mayor-los-angeles`: **Retrieved** (HTTP 200, IP: `23.48.203.178`, 31,545 bytes).
    * `https://en.wikipedia.org/wiki/Karen_Bass`: **Retrieved** (HTTP 200, IP: `198.35.26.224`, 757,252 bytes).
    * `https://www.nytimes.com/2022/12/12/us/karen-bass-los-angeles-mayor.html`: **Inaccessible** (HTTP 403 Forbidden, IP: `151.101.73.164`, 0 bytes).
  - Verbatim candidate passages: 4 passages extracted. Programmatic character offset check verified 100% exact substring match (`extracted_text[start:end] == exact_passage`).
  - Browser presentation verified via headless Chrome browser subagent with distinct search hit and candidate source groups, collapsible text inspectors, and inert text rendering.
  - Zero verdicts, truth scores, or confidence ratings generated. Zero secrets leaked.
  - Note: In this repair pass, live smoke assertions in `live_smoke_investigation.py` were updated to explicitly assert elapsed time <= 90s, at least 1 retrieved source, at least 1 extracted passage, and `total_requests_made <= 2`. Per instructions, live external API calls were not re-executed during this offline repair pass.

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

