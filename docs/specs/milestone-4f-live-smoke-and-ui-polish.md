# Milestone 4F: Live End-to-End Smoke Verification & UI Polish Pass

## 1. Executive Summary & Goal
Phase 4 introduced major capabilities across three milestones:
- **Milestone 4C**: Los Angeles City vs. County & Municipal jurisdiction classification, search boosting, and Cornell Notes visual provenance badges.
- **Milestone 4D**: Custom Report Studio export actions (Markdown, Plain Text, downloadable `.md`) and deterministic Standard/APA/MLA Citation Style selector.
- **Milestone 4E**: Multi-tab workspace auto-save & reload restore via `localStorage` (`scoopscope_workspace_v1`) with one-click `#btn-clear-workspace` reset.

**Goal**: Execute a complete integration & live-smoke verification pass across all Phase 4 features on the real DOM, and reconcile/polish DOM and CSS rough edges between the visible `<textarea id="input-text">`, `#custom-report-section`, `#session-tabs-bar`, and `localStorage` persistence.

---

## 2. Decision Log
- **Decision 016**: Execute Milestone 4F — run a full Phase 4 (4C + 4D + 4E) end-to-end integration & live-smoke verification pass and reconcile/polish DOM & CSS rough edges between `#input-text`, `#custom-report-section`, `#session-tabs-bar`, and `localStorage` persistence.

---

## 3. What the User Sees
1. **Synchronized Text Input**:
   - The visible `<textarea id="input-text">` updates the active session snapshot and persists live drafts to `localStorage` on every keystroke.
   - Restoring a workspace session or clicking `#btn-clear-workspace` synchronizes both `#input-text` and `#claim-input`.
2. **Synchronized Custom Report Studio (`#custom-report-section`)**:
   - Selecting quotes in Cornell Notes immediately reveals `#custom-report-section` (and syncs `#report-studio-section`).
   - The Report Studio displays the live Evidence Bank counter, report vibe selector, and citation style selector (`#citation-style-select`).
   - Switching citation styles between Standard, APA, and MLA dynamically updates the Works Cited bibliography in real-time.
   - On page reload (`loadWorkspaceFromStorage()`), any active selected quotes, active citation style, and report studio visibility are immediately restored.
3. **Workspace Reset & Tab Management**:
   - Clicking `#btn-clear-workspace` resets `#input-text` to `""`, hides `#custom-report-section`, `#results-section`, and resets to a clean `"Session 1"` tab without blocking dialogs.
4. **Polished Responsive Layout**:
   - `#session-tabs-bar` wraps cleanly on narrow screens while keeping `#btn-clear-workspace` pinned right.
   - Cornell Notes Cue badges (`[LA Local City Official]`, publication dates) and Report Studio export buttons wrap fluidly without text clipping.

---

## 4. Scope & Guardrails
- **In Scope**:
  - `docs/specs/milestone-4f-live-smoke-and-ui-polish.md` (this specification).
  - `frontend/index.html` (mount `#custom-report-section` and static `#citation-style-select`).
  - `frontend/style.css` (responsive wrapping for session tabs, cue badges, export toolbar, and focus outlines).
  - `frontend/app.js` (DOM synchronization between `#input-text` and `#claim-input`, `#custom-report-section` visibility and rehydration).
  - `backend/tests/test_frontend_ordering.py` (live FastAPI static-serving and full Phase 4 browser smoke tests).
- **Out of Scope**:
  - Strictly DO NOT modify any backend application logic in `backend/app/**`.

---

## 5. Verification Criteria
1. `backend/tests/test_frontend_ordering.py` passes two new comprehensive end-to-end test cases:
   - `test_fastapi_live_static_and_index_serving`: Confirms `GET /` serves HTML containing `#session-tabs-bar`, `#btn-clear-workspace`, `#input-text`, and `#citation-style-select`, and static assets serve HTTP 200.
   - `test_phase4_full_journey_smoke_in_browser`: Headless browser test verifying real DOM input persistence, Cornell Notes jurisdiction badge rendering, quote selection into `#custom-report-section`, citation style switching, multi-tab reload restoration, and one-click workspace clear.
2. Full pytest test suite passes (280+ passed, 0 failures, 100% offline).
3. Zero uncaught JavaScript errors or unhandled promises in the browser test runner.
