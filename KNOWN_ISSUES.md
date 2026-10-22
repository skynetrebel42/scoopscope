# ScoopScope — Known Issues & Active Backlog

**Document Version**: 1.1  
**Baseline Commit**: `a3775fa`  
**Last Verified**: Milestone 5A (284+ offline tests passing)  

---

## 1. Active Warnings & Upstream Deprecations

These warnings were detected during test execution and code inspection. They do not block operations or break functionality, but are documented here for future cleanup.

### 1. `google.genai.types._UnionGenericAlias` Deprecation Warning
- **Trigger**: Occurs during import of `google.genai.types` when initializing Gemini adapters.
- **Log Message**: `DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17`
- **Impact**: Zero runtime impact on Python 3.11–3.14. Upstream Google GenAI SDK will update its internal type unions before Python 3.17 release.
- **Action**: Track upstream SDK releases and update when a patch is published.

### 2. `fastapi.testclient` Starlette Deprecation Warning
- **Trigger**: Occurs when running `pytest` via `TestClient` in `backend/tests/test_extraction.py`.
- **Log Message**: `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.`
- **Impact**: Zero impact on test correctness. All 284+ offline tests pass.
- **Action**: Evaluate upgrading `httpx`/`starlette` or migrating to `httpx.AsyncClient` when FastAPI updates its recommended test harness.

### 3. W3C `#:~:text=` Deep-Link Anchor Compatibility
- **Feature**: Verbatim quotes provide a direct "Find exact line on website ↗" link using W3C Text Fragments (`#:~:text=start,end`).
- **Behavior**:
  - In Chromium-based browsers (Google Chrome, Microsoft Edge, Brave, Opera), the browser automatically scrolls directly to the quote and highlights it in yellow.
  - In non-Chromium browsers (Apple Safari, Mozilla Firefox), browsers that do not yet support text fragments gracefully ignore the fragment and load the source page at the top.
- **Impact**: Graceful degradation without broken links or script errors.

---

## 2. Active Backlog Candidates

These features represent the immediate forward roadmap following Phase 4 completion:

### 1. Evidence & Jurisdiction Filtering
- **Objective**: Enable investigative filtering across Cornell Notes evidence items by jurisdiction badge (e.g., City Official, LA County Official, Independent Municipal), publication date ranges, or domain classification.
- **Scope**:
  - Filter pills and dropdown selectors above the evidence board.
  - Client-side filtering preserving DOM immutability and multi-tab isolation.
  - Works Cited list synchronized with currently filtered/visible evidence quotes.

### 2. Portable Workspace JSON Export & Import
- **Objective**: Allow investigators to export the entire multi-tab workspace (all sessions, inquiries, extracted claims, verbatim quotes, and selected report notes) as a portable JSON file and restore it into another browser or device.
- **Scope**:
  - Strict schema validation and XSS/prototype pollution sanitization on imported JSON.
  - One-click "Export Workspace (.json)" and drag-and-drop / file-input "Import Workspace".
  - Seamless merging or clean replacement into `localStorage` under `scoopscope_workspace_v1`.

### 3. Contradiction & Material Qualification Callouts
- **Objective**: Visually highlight contradictions and material qualifications across retrieved sources directly within the Cornell Notes evidence board.
- **Scope**:
  - Side-by-side contrast cards displaying contradictory passages with full source provenance.
  - Preserves factual divergence without synthetic harmonization or truth-score smoothing.
  - Directly exports flagged contradictions into the Custom Report Studio synthesis section.
