# ScoopScope — Project Handoff & Architecture Baseline

**Document Version**: 1.6  
**Current Milestone**: Milestone 5A Close-Out (Decision 020)  
**Baseline Commit**: `setup/workflow` (`a3775fa`)  
**Workspace Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope`  
**Test Suite Status**: 285 passed (100% passing) across 11 test suites  

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
| **Planner** | **Argon in Gemini App** | System architecture, specs, milestone reviews, decision logging, prompt design. |
| **Builder** | **Flash 3.8 in Antigravity** | Workspace execution, implementation, test suite maintenance, offline verification, git hygiene. |

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
- **Decision 010 (Milestone 4C)**: Los Angeles City vs. County Jurisdiction Guardrails
  - Implemented deterministic official domain classification in `backend/app/jurisdiction.py` recognizing LA City (`lacity.gov`), LA County (`lacounty.gov`), State of California (`ca.gov`), and regional transit/utility agencies.
  - Added heuristic civic ambiguity detection in `/api/claims/clarify`, presenting users with clear jurisdiction clarification cards and options.
  - Boosted research search ranking in `backend/app/research.py` for verified official jurisdiction domains matching confirmed scope.
  - Displayed visual jurisdiction badges in Cornell Notes evidence cards and Works Cited table.
  - Added 92 exhaustive offline unit and integration tests in `backend/tests/test_la_jurisdiction.py`, elevating the test suite to 256 passing tests across 11 test suites.
- **Decision 011 (Milestone 4C Close-Out & Cumulative Handoff Initialization)**: Cumulative Handoff System & Milestone 4D Spec
  - Established two cumulative handoff files: `.handoff-builder.md` (active baseline commit, test counts, high-caution rules, next active spec, bootstrap command) and `.handoff-planner.md` (cumulative system summary and roadmap for Gemini/Argon chat prompt priming).
  - Enforced the Mandatory Milestone Close-Out Rule in `AGENTS.md` and updated `GEMINI.md` startup read sequence.
  - Archived completed 4C spec to `docs/archive/milestone-4c-la-jurisdiction-guardrails.md` and staged Milestone 4D spec (`docs/specs/milestone-4d-report-export-and-citations.md`).
- **Decision 012**: 3G Trifecta Model Specialization (Argon in Gemini App = Planner, Flash 3.8 in Antigravity = Builder)
  - Formalized agent roles: Planner operates via Argon in Gemini web chat for architectural design, user alignment, and spec generation; Builder operates via Flash 3.8 in Antigravity IDE for autonomous, test-driven implementation, strict offline verification, and git hygiene.
- **Decision 013 (Milestone 4D)**: Report Studio Export, Deterministic Citation Formatter, and Municipal Jurisdiction Ranking
  - Added one-click export actions to Custom Report Studio (Copy Markdown, Copy Plain Text, Download `.md` Report with dynamic timestamping and clipboard fallback).
  - Implemented deterministic Citation Style Selector offering Standard Numbered, APA (7th ed, strict `(n.d.)` on absent dates), and MLA (9th ed, strict `Accessed <date>` on absent dates) with zero author/date fabrication and automatic bracketed jurisdiction tags (`[LA City Official]`, etc.).
  - Enforced deterministic works cited replacement in `gemini_adapter.py` to prevent LLM hallucination of publisher names or unstandardized citation formats.
  - Expanded `classify_source_jurisdiction` in `backend/app/jurisdiction.py` to recognize 11 independent LA County incorporated municipalities (`la_local_city`) including Norwalk, Long Beach, Pasadena, Santa Monica, Glendale, Culver City, Beverly Hills, Torrance, Inglewood, Burbank, and Pomona.
  - Boosted matching official municipal domains ahead in `backend/app/research.py` candidate search results.
  - Elevated test suite to 276 passing tests offline across 11 test suites; committed at `0f5dddf`.
- **Decision 014 (Milestone 4E)**: Advance to Milestone 4E: Multi-Tab Workspace `localStorage` Auto-Save & Restore + Clear Workspace Reset
  - Implemented automatic JSON serialization and restoration of multi-tab workspace state across page refreshes under `localStorage` key `scoopscope_workspace_v1`.
  - Preserved session tabs, active tab selection, confirmed inquiry scopes, clarification rounds, claims, Cornell Notes evidence cards, Evidence Bank selected quotes, and synthesized report drafts without data loss.
- **Decision 015 (Milestone 4E Implementation Polish)**: One-Click Instant Workspace Reset, Map Serialization, and Transient Spinner Guardrails
  - Enforced one-click instant reset on `#btn-clear-workspace` with zero blocking `window.confirm()` popups per UX requirements.
  - Bidirectional `Map` <-> `[[key, quote], ...]` JSON array serialization for `selectedQuotes` ensuring full fidelity across persistence cycles.
  - Reset transient loading state spinners (`isClarifying = false`, `isResearching = false`) on restore to prevent permanently frozen spinner states after interrupting active network calls.
  - Implemented quota-exceeded and disabled-storage defensive error handling without crashing UI interactions.
  - Shipped at `e054d1e` with 278 passing tests offline across 11 test suites.
- **Decision 016 (Milestone 4F)**: Execute Milestone 4F (`milestone-4f-live-smoke-and-ui-polish.md`) — full Phase 4 end-to-end headless Chrome & FastAPI live smoke verification plus DOM/CSS synchronization across `#input-text`, `#custom-report-section`, `#session-tabs-bar`, and `localStorage` restore; shipped at `b049fc0` with 280 passing tests.
- **Decision 017 (Milestone 4G)**: Multi-Tab Async Search Isolation, Single Collapsible Report Studio, Compact Layout, & Works Cited Deduplication
  - Bound async search/clarification network promises to `originSessionId` in `frontend/app.js`, isolating background updates from switched tabs and saving data strictly to the originating session.
  - Consolidated duplicate Report Studio panels into a single collapsible bar in `#custom-report-section` with cross-tab evidence counters.
  - Auto-compacted inquiry and claims sections behind `#sticky-inquiry-bar` upon research completion.
  - Enforced sequential list numbering in generated reports and deduplicated Works Cited bibliography entries by normalized source URL.
  - Shipped at commit `f75e8ee` with 282 passing tests across 11 test suites.
- **Decision 018 (Milestone 4H)**: Empty-Tab Report Studio Hiding, Tab Bar Scrollbar Removal, Claim Results Accordion & Single Works Cited
  - Enforced `.hidden { display: none !important; }` in `frontend/style.css` and suppressed `#custom-report-section` on empty tabs and immediately following workspace reset.
  - Removed the horizontal Windows scrollbar from `#session-tabs-list` by enabling flex wrapping (`flex-wrap: wrap; overflow-x: visible; scrollbar-width: none;`).
  - Added `.btn-toggle-evidence` claim results accordion, auto-collapsed prior claim results when initiating source discovery on another claim, and defaulted `.technical-audit-drawer` to closed (`!open`).
  - Stripped redundant LLM trailing Works Cited sections to ensure exactly one bibliography appears, and sanitized literal `\n` backslash sequences in extracted quotes.
  - Shipped at commit `83e03bb` with 282 passing tests across 11 test suites.
- **Decision 019 (4G/4H Close-Out & Workflow Baseline Sync)**: Mandatory Milestone Close-Out, Selector Inventory Integrity, & Workflow Automation Sync
  - Completed Mandatory Milestone Close-Out for Milestones 4G and 4H, archiving `milestone-4h-empty-tab-and-claim-accordion.md` to `docs/archive/`.
  - Established frontend selector inventory integrity rules in `.agents/rules/frontend.md` and added automated Python AST/regex validation (`test_selector_inventory` in `test_frontend_ordering.py`), eliminating phantom/ghost element IDs from `frontend/app.js` and tests.
  - Added automated build loop workflows (`/build`, `/review`, `/playtest`) and single-file Gemini planner pack generator (`scripts/pack.py`).
  - Synced all cumulative handoff files (`PROJECT_HANDOFF.md`, `docs/HOW_IT_WORKS.md`, `.handoff-builder.md`, `.handoff-planner.md`) to the unified baseline with 284 passing offline tests across 11 test suites.
- **Decision 020 (Milestone 5A)**: One-Click "Copy Quote + Citation" Button & KNOWN_ISSUES.md Refresh
  - Added one-click `.btn-copy-quote-citation` action button to each verbatim quote card in the Cornell Notes evidence board.
  - Deterministically formats verbatim quotes paired with full source citation honoring the currently active citation style (Standard, APA 7th ed with `(n.d.)`, MLA 9th ed with `Accessed <date>`) and bracketed official jurisdiction tags (`[LA City Official]`, `[LA Local City Official]`, etc.).
  - Added clipboard API support with fallback to hidden textarea copy execution, plus 1.5-second `Copied! ✓` temporary feedback (`Copy Failed` on rejection).
  - Enforced zero date fabrication across `frontend/app.js`: eliminated fallback today's date in `primaryReportSources` and scoped test assertions to prevent date invention.
  - Refreshed `KNOWN_ISSUES.md`: updated header baseline to commit `a3775fa` and 284+ passing tests, and replaced shipped 4C/4D items with post-Phase-4 backlog candidates (Evidence/Jurisdiction Filtering, Portable Workspace JSON Export/Import, Contradiction & Material Qualification Callouts).
  - Shipped with 285 passing tests across 11 test suites.

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
9. **Milestone 010 (Milestone 4C)**: Los Angeles City vs. County Jurisdiction Guardrails
   - Deterministic official domain classification (`backend/app/jurisdiction.py`) separating City (`lacity.gov`), County (`lacounty.gov`), State (`ca.gov`), and Regional agencies.
   - Ambiguity detection and civic clarification cards in `/api/claims/clarify`.
   - Domain-boosted search ranking in `backend/app/research.py`.
   - Visual jurisdiction badges in Cornell Notes UI and Works Cited table.
   - Commit `94baeb2`, 256 tests passing across 11 test suites.
10. **Milestone 011 (Milestone 4C Close-Out & Handoff Initialization)**: Cumulative Handoff System & Milestone 4D Spec
    - Cumulative handoff artifacts (`.handoff-builder.md` and `.handoff-planner.md`) guaranteeing seamless context handoff between fresh Argon/Antigravity sessions.
    - Mandatory milestone close-out rule in `AGENTS.md` and updated startup read sequence.
    - Archived 4C spec to `docs/archive/` and staged Milestone 4D active spec (`docs/specs/milestone-4d-report-export-and-citations.md`).
11. **Milestone 012 (Milestone 4D)**: Report Studio Export, Citation Styles, & Municipal Jurisdiction Ranking
    - One-click report export actions (Copy Markdown, Copy Plain Text, Download `.md` Report with dynamic timestamping).
    - Deterministic citation formatting (Standard Numbered, APA 7th ed with strict `(n.d.)`, MLA 9th ed with strict `Accessed <date>`) with zero fabrication and bracketed jurisdiction tags.
    - LA County independent municipal domain classification (`la_local_city`) and research search candidate prioritization.
    - Commit `0f5dddf`, 276 tests passing across 11 test suites.
12. **Milestone 013 (Milestone 4E)**: Multi-Tab Workspace `localStorage` Auto-Save & Restore + Clear Workspace Reset
    - Automatic JSON serialization and restoration of multi-tab workspace state across reloads under `scoopscope_workspace_v1`.
    - Bidirectional `Map` <-> `[[key, quote], ...]` serialization for `selectedQuotes` Evidence Bank items.
    - One-click instant `#btn-clear-workspace` reset button with zero blocking confirmation dialogs.
    - Transient loading state reset (`isClarifying = false`, `isResearching = false`) on restore to eliminate stuck spinners.
    - Shipped at commit `e054d1e` with 278 tests passing offline across 11 test suites.
13. **Milestone 014 (Milestone 4F)**: Live End-to-End Smoke Verification & UI Polish Pass
    - Full Phase 4 (4C + 4D + 4E) end-to-end headless Chrome browser smoke tests and live FastAPI static/index serving contract tests.
    - Synchronized visible `#input-text` and `#claim-input` two-way bindings, `#custom-report-section` visibility, and live citation style switching.
    - Verified multi-tab session restore, selected quote rehydration, official LA local city badges, and instant `#btn-clear-workspace` reset.
    - Shipped at commit `b049fc0` with 280 tests passing offline across 11 test suites.
14. **Milestone 015 (Milestone 4G)**: Playtest UX Polish & Multi-Tab Async Search Isolation
    - Isolated async search and clarification execution across session tabs via `originSessionId` binding.
    - Single collapsible Report Studio bar in `#custom-report-section` with multi-tab quote selection counters.
    - Sequential ordered list rendering and URL-based Works Cited deduplication.
    - Shipped at commit `f75e8ee` with 282 tests passing offline across 11 test suites.
15. **Milestone 016 (Milestone 4H)**: Empty-Tab Report Studio Hiding, Tab Bar Wrapping, Claim Accordion & Single Works Cited
    - Hidden Report Studio on fresh tabs and post-clear workspace.
    - Tab bar flex wrapping eliminating Windows horizontal scrollbar.
    - Claim evidence accordion with auto-collapse on new research and closed-by-default technical audit drawer.
    - Single Works Cited deduplication and quote string newline escape sanitization.
    - Shipped at commit `83e03bb` with 282 tests passing offline across 11 test suites.
16. **Milestone 017 (Milestone 4G/4H Close-Out & Workflow Baseline Sync)**: Workflow Tooling, Selector Inventory Integrity & Full Baseline Sync
    - Archived 4H spec to `docs/archive/milestone-4h-empty-tab-and-claim-accordion.md`.
    - Added `test_selector_inventory` ensuring exact 1:1 parity between `index.html` and `app.js` element IDs.
    - Integrated build loop workflows and `scripts/pack.py` planner pack generator.
    - Verified full 284 offline test suite passes (100% passing).
17. **Milestone 018 (Milestone 5A)**: One-Click "Copy Quote + Citation" & KNOWN_ISSUES.md Refresh
    - Added one-click `Copy Quote + Citation` action button next to text fragment links in Cornell Notes evidence cards.
    - Deterministic quote + citation pairing honoring Standard, APA, and MLA styles with zero date/author invention.
    - Clipboard API integration with hidden textarea fallback and temporary `Copied! ✓` feedback.
    - Updated `KNOWN_ISSUES.md` baseline and roadmap backlog.
    - Shipped with 285 passing tests across 11 test suites.



