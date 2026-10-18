# ScoopScope — Project Handoff & Architecture Baseline

**Document Version**: 1.0  
**Current Milestone**: Milestone 4A Complete (Decisions 008 & 009)  
**Baseline Commit**: `857c410`  
**Workspace Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope`  
**Test Suite Status**: 164 passed offline (100% passing)  

---

## Section 1: Project Context & Vision

### Vision: "Perplexity Plus for Everyday Fact Investigation"

ScoopScope is an evidence-first claim investigation tool designed to bring journalistic rigor, strict provenance, and cryptographic verifiability to fact checking. Unlike conventional AI search engines that synthesize answers from unverified summaries or hallucinate citations, ScoopScope adheres to a strict principle:

> **A search engine snippet is never verified evidence.**  
> Findings must reference examined verbatim passages extracted from real, safely retrieved web pages. If evidence is inaccessible or insufficient, the claim status is strictly **`unresolved`**, never false.

### Core User Journey
1. **Intake & Clarification**: The user enters a statement or inquiry. If ambiguous, ScoopScope engages in at most 2 rounds of clarification (offering exactly 3 coherent choices + free text) to produce an agreed, editable **Confirmed Scope Question**.
2. **Claim Decomposition**: Compound assertions are decomposed into discrete, checkable subclaims while preserving original wording and causal relationships.
3. **Bounded & Safe Retrieval**: For an investigated claim, targeted search queries are generated with `-filetype:pdf`. Up to 5 hits are gathered from Serper, and up to 3 candidate pages are fetched via socket-level SSRF IP-pinned connections (1 MB ceiling, 3 redirects, 90s deadline).
4. **Verbatim Passage Extraction & Date Provenance**: HTML is cleaned into plain text. Passages are extracted with exact character offsets (`extracted_text[start:end] == exact_passage`), publication dates are extracted defensively (JSON-LD, `<meta>`, `<time>`, bylines only), and W3C `#:~:text=` text fragment deep links are formed.
5. **Cornell Notes & Custom Report Studio**: Evidence is presented in a two-column Cornell Notes workspace. Users can pin their active inquiry, toggle surrounding context, select quotes into an Evidence Bank, and synthesize tailored reports (Objective Brief, Cornell Study, Fact Check, Deep Dive) with full citations.

Crucially: **Zero automated truth scores, probability percentages, or simulated verdicts are generated.** Evidence is presented for human audit and inspection.

---

## Section 2: 3G Trifecta Roles & Commands

The project operates under the **3G Trifecta** collaborative development model:

| Role | Entity | Responsibilities |
|---|---|---|
| **Owner** | **Minh** | Vision, priorities, milestone approval, repository ownership, push gatekeeper. |
| **Planner** | **Gemini Chat** | System architecture, specs, milestone reviews, decision logging, prompt design. |
| **Builder** | **Antigravity** | Workspace execution, implementation, test suite maintenance, offline verification, git hygiene. |

### Local Launch Commands

#### 1. Backend API & Static Frontend
Run from PowerShell:
```powershell
cd c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
- Access the web application at `http://localhost:8000/`
- API documentation available at `http://localhost:8000/docs`

#### 2. Automated Test Suite (Offline)
Run the full pytest suite from the project root:
```powershell
cd c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

#### 3. Frontend Headless & Visual Tests
- In-browser suite: Open `frontend/test_runner.html` directly in any modern browser.
- Headless Chrome browser runner: Executed as part of pytest via `backend/tests/test_frontend_ordering.py`.

---

## Section 3: Playbook & Evidence/Security Guardrails

All contributors and agents must uphold these non-negotiable rules:

1. **Zero Hallucination / Fabrication**:
   - Never invent sources, quotes, citations, verification outcomes, fallback choices, synthetic subclaims, or truth scores.
   - If an LLM call fails or returns unexpected schemas, raise an explicit error rather than silently fabricating fallback content.
2. **Strict Retrieval & Execution Budgets**:
   - Exactly 1 claim investigated per user action.
   - Maximum 2 outbound search API requests per action (including retries).
   - Maximum 5 hits returned per search query.
   - Maximum 3 candidate pages fetched per research action.
   - Strict 90-second monotonic research deadline across search, fetch, and extraction.
3. **SSRF & Ingestion Security**:
   - Block all private, link-local, loopback, CGNAT, and documentation IP addresses.
   - Defeat DNS rebinding via socket-level destination IP pinning before TLS handshake.
   - Re-check resolved IPs on every redirect hop (max 3 redirects).
   - Response size capped at 1 MB decompressed.
   - Timeouts: 10s connect, 30s total per page fetch.
   - Reject non-text content types before reading body; append `-filetype:pdf` to search queries.
   - Enclose all fetched content in `<untrusted_source_content>` boundaries in LLM prompts.
4. **Defensible Date Provenance**:
   - Publication and modified dates must originate strictly from JSON-LD (`datePublished`, `dateCreated`, `dateModified`), HTML `<meta>` tags (`article:published_time`, `og:published_time`, etc.), HTML `<time datetime="...">` tags, or explicit article bylines.
   - Never infer dates from HTTP `Date` headers or URL year digits.
5. **Inert DOM Rendering**:
   - All external titles, URLs, snippets, and passages must be rendered via `textContent` or `document.createTextNode()`. Zero unescaped `innerHTML` injection of untrusted content.
6. **Exact-Path Git Staging & Push Gate**:
   - Stage files only by exact path: `git add <path>`. Never use `git add .`, `git add -A`, or `git commit -a`.
   - Never run `git push` without explicit Owner review and approval.

---

## Section 4: Numbered Decision Log

- **Decision 001 (Milestone 1)**: Structured Claim Extraction via Pydantic & Gemini Structured Output
  - Established initial extraction pipeline separating checkable factual assertions from opinions, predictions, and causal interpretations.
- **Decision 002 (Milestone 2A)**: Request-Ordering Sequence Protection & Worst-Case Timeout Bounding
  - Introduced frontend sequence tokens (`currentSubmissionSeq`) to discard out-of-order asynchronous responses and reconciled total timeout math to 312s.
- **Decision 003 (Milestone 2B)**: Replaceable `SearchProvider` Protocol & Safe HTTP Fetcher Foundation
  - Created decoupled search abstraction and hardened fetcher with socket-level SSRF IP-pinning, 1 MB streaming ceiling, and 3-hop redirect gates.
- **Decision 004 (Milestone 2C)**: Serper Google Search Integration & Verbatim Character-Offset Slicing
  - Integrated live Serper search behind budget caps (2 queries, 5 hits, 3 pages, 90s deadline) and enforced exact substring character offset verification (`extracted_text[start:end] == exact_passage`).
- **Decision 005 (Milestone 2C Review Fixes)**: Search Failure Preservation (F1), Multi-Claim Ownership (F2), and Cooperative Extraction Deadlines (F3)
  - Prevented silent zero-hit masking on search failures, isolated claim button loading states during switching, and added tag-level cooperative deadline checks during HTML parsing.
- **Decision 006 (Milestone 3A)**: Bounded 2-Round Inquiry Intake Clarification & Confirmed Scope Invalidation
  - Replaced raw extraction with an interactive clarification card offering exactly 3 coherent choices + free text, bounded to max 2 rounds, and invalidated existing research when inquiry scope is edited.
- **Decision 007 (Milestone 3B / 4B)**: Sticky Inquiry Bar, Cornell Notes Layout, Defensible Dates, PDF Filtering, and Custom Report Studio
  - Added floating inquiry banner, paired 2-column Cornell notes layout, W3C text fragment deep links, JSON-LD date extraction, `-filetype:pdf` query filtering, multi-tab workspace, and the `/api/report` synthesis endpoint. Verified read-only in Milestone 4B.
- **Decision 008 (Milestone 4A)**: Playbook Repo Standardization & `.gitignore` Hygiene Fix
  - Standardized repository documentation (`PROJECT_HANDOFF.md`, `ARCHITECTURE.md`, `KNOWN_ISSUES.md`, `docs/HOW_IT_WORKS.md`), streamlined `AGENTS.md`, and fixed `.gitignore` gaps (`.pytest_cache/`, `*.patch`, `manifest.txt`).
- **Decision 009 (Milestone 4A Post-Ship Cleanup)**: Spec Archival & Legacy Status Migration
  - Archived completed 4A spec and legacy `STATUS.md` to `docs/archive/`, deleted untracked root scratch files, and affirmed `PROJECT_HANDOFF.md` as sole source of truth.

---

## Section 5: Shipped Milestones

1. **Milestone 001 (Milestone 1 Baseline)**: Claim Extraction Vertical Slice
   - Structured schema extraction via Gemini API.
   - Separation of factual claims from opinions and causal statements.
2. **Milestone 002 (Milestone 2A)**: Request Ordering & Timeout Reconciliation
   - Frontend request-ordering sequence guardrails.
   - Reconciled retry bounds and worst-case timeout budgets.
3. **Milestone 003 (Milestone 2B)**: Search Provider Protocol & Safe Fetcher Foundation
   - `SearchProvider` Python protocol and `SearchResultHit` immutable schema.
   - Socket destination IP-pinning, RFC 1918 / CGNAT / loopback SSRF blocking, 1 MB ceiling.
4. **Milestone 004 (Milestone 2C)**: Serper Search Provider & Verbatim Passage Extraction
   - Real Serper Google search integration with credential redaction.
   - Verbatim character-offset slicing with mathematical provenance guarantee.
5. **Milestone 005 (Milestone 2C Review Fixes)**: F1–F3 Robustness Polish
   - Distinguishing search provider failure from legitimate zero-hit queries.
   - Independent claim button loading ownership during asynchronous switching.
   - Cooperative tag-level deadline checks in HTML parsing.
6. **Milestone 006 (Milestone 3A)**: Inquiry Clarification & Confirmed Scope
   - Max 2 rounds of intake clarification with exactly 3 coherent choices.
   - In-place editable confirmed scope question with material uncertainty tracking.
   - Automatic research snapshot invalidation on draft or scope modification.
7. **Milestone 007 (Milestone 3B)**: Sticky Inquiry Bar, Cornell Notes, Date Provenance, & Custom Report Studio
   - Pinned floating inquiry bar with live progress indicator.
   - Two-column paired Cornell Notes layout with 1–5 verbatim quotes and context toggles.
   - W3C `#:~:text=` text fragment deep links for Chromium browsers.
   - Multi-source defensible date extraction (JSON-LD, `<meta>`, `<time>`, bylines).
   - Social shell domain deprioritization and `-filetype:pdf` search query filtering.
   - Multi-tab session and claim workspace with custom report generation (`/api/report`).
8. **Milestone 008 (Milestone 4A)**: Playbook Repo Standardization & Workspace Hygiene
   - Canonical playbook documentation aligned, root files streamlined, untracked scratch purged, and test suite 100% passing.

