# Milestone 4G Specification — Playtest Bugfixes: Multi-Tab Async Isolation, Single Collapsible Report Studio & Compact Layout

- **Document Version**: 1.0  
- **Milestone**: 4G  
- **Decision Logged**: Decision 017  
- **Baseline Commit**: `a872d7c` (after Milestone 4F close-out)  
- **Test Baseline**: 280 passed offline tests across 11 test suites  

---

## 1. Problem Statement & Playtest Bug Audit

During live playtesting at `http://127.0.0.1:8000`, four UX and state coordination bugs were identified:

1. **Bug 1 — In-Flight Search Bleeding Across Tabs**:
   - Starting a clarify or research request in Tab 1 and opening/switching to Tab 2 (`+ New`) while the network request is still pending causes Tab 1's response to render into Tab 2's active DOM and overwrite Tab 2's session state.
2. **Bug 2 — Duplicate Report Studios & Excessive Page Stretch**:
   - Milestone 4F added `#custom-report-section` into `index.html` while `app.js` also built `#report-studio-section` inside `#results-section`. Both rendered simultaneously on the page, and `#custom-report-section` remained visible even on fresh tabs with 0 selected quotes.
3. **Bug 3 — Stale Scope / Claims Visible on Empty or Switched Tabs**:
   - Switching tabs or clearing/reloading left `#confirmed-scope-banner`, `#claims-section`, or `#results-section` visible even when the session was fresh or had not reached extraction/research. Top cards remained expanded, pushing research results far down the page.
4. **Bug 4 — `1. 1. 1.` Numbering & Duplicate Sources in Works Cited**:
   - In report output, ordered lists rendered repeated `1.` markers instead of sequential `1, 2, 3...`, and Works Cited repeated entries for every selected quote from the same source URL instead of deduplicating citations by URL.

---

## 2. Technical Requirements (Decision 017)

### 2.1 Async Request Session Binding (Tab Isolation)
- In `frontend/app.js`, every asynchronous network call (`executeSubmission`, `executeClarificationChoice`, `executeResearch`, and report generation) must capture `const originSessionId = activeSessionId;`.
- When the asynchronous call completes (or catches an error):
  - The results (`data`, `claims`, `clarificationExchanges`, `claimResearchTabs`, `activeClaimTabId`) must be saved strictly to the origin session object in `sessionInquiries`.
  - The transient flags `isClarifying = false` and `isResearching = false` must be set on the origin session object.
  - `saveWorkspaceToStorage()` must be called to persist the background update.
  - DOM mutation (`renderResults`, `renderClarification`, `renderClaimResearchTabsWorkspace`) must execute **only if** `activeSessionId === originSessionId`.
  - If the active session has changed, update only `renderSessionTabs()` so the origin tab's title reflects completed research in the background without disturbing the user's active screen.

### 2.2 Unified Collapsible Report Studio
- Consolidate to a single canonical Report Studio in `frontend/index.html` and `frontend/app.js`. Ensure elements `#custom-report-section` and `#report-studio-section` do not produce duplicate visible panels.
- Hide Report Studio completely when `selectedQuotes` has 0 checked quotes or when the active session has no research results.
- When quotes are selected, display a compact collapsible bar showing evidence statistics (`X quotes from Y sources selected across tabs`) and a toggle button (`Customize & Generate Report ▾`). The controls and output body start collapsed or toggleable to keep vertical height tight.

### 2.3 Compact Page Layout & Scope Invalidation
- When research results are active, compact `#input-section` / `#claims-section` behind `#sticky-inquiry-bar`. Clicking `Edit ↑` on `#sticky-inquiry-bar` re-expands them.
- In `switchSession()`, `startNewSession()`, `loadWorkspaceFromStorage()`, and `clearWorkspace()`, explicitly enforce hidden status for `#confirmed-scope-card`, `#claims-outdated-banner`, `#clarification-section`, `#results-section`, `#sticky-inquiry-bar`, and the Report Studio when the active session has no data for them.

### 2.4 Sequential Numbering & Works Cited Deduplication
- In `renderMarkdown()`, ensure ordered list items generate valid `<ol>` structures with standard incremental list numbering (`1.`, `2.`, `3.`) without CSS counter resets resetting every `<li>`.
- In `formatWorksCitedList()`, deduplicate citation entries by normalized `source_url` (or domain + title) so multiple quotes from the same article cite that source once.

---

## 3. Strict Scope & Guardrails
- **Backend Frozen**: Zero changes to `backend/app/**`.
- **Allowed Files**:
  - `docs/specs/milestone-4g-playtest-ux-and-tab-isolation.md`
  - `frontend/index.html`
  - `frontend/style.css`
  - `frontend/app.js`
  - `backend/tests/test_frontend_ordering.py`
- **Verification**: All 280 existing tests pass plus new tab isolation and collapsible Report Studio tests (282+ passing offline).
