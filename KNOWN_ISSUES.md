# ScoopScope — Known Issues & Active Backlog

**Document Version**: 1.0  
**Baseline Commit**: `582272c`  
**Last Verified**: Milestone 4B Read-Only Pass  

---

## 1. Active Warnings & Upstream Deprecations

These warnings were detected during test execution and code inspection in Milestone 4B. They do not block operations or break functionality, but are documented here for future cleanup.

### 1. `google.genai.types._UnionGenericAlias` Deprecation Warning
- **Trigger**: Occurs during import of `google.genai.types` when initializing Gemini adapters.
- **Log Message**: `DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17`
- **Impact**: Zero runtime impact on Python 3.11–3.14. Upstream Google GenAI SDK will update its internal type unions before Python 3.17 release.
- **Action**: Track upstream SDK releases and update when a patch is published.

### 2. `fastapi.testclient` Starlette Deprecation Warning
- **Trigger**: Occurs when running `pytest` via `TestClient` in `backend/tests/test_extraction.py`.
- **Log Message**: `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.`
- **Impact**: Zero impact on test correctness. All 164 tests pass.
- **Action**: Evaluate upgrading `httpx`/`starlette` or migrating to `httpx.AsyncClient` when FastAPI updates its recommended test harness.

### 3. W3C `#:~:text=` Deep-Link Anchor Compatibility
- **Feature**: Verbatim quotes provide a direct "Find exact line in source ↗" link using W3C Text Fragments (`#:~:text=start,end`).
- **Behavior**:
  - In Chromium-based browsers (Google Chrome, Microsoft Edge, Brave, Opera), the browser automatically scrolls directly to the quote and highlights it in yellow.
  - In non-Chromium browsers (Apple Safari, Mozilla Firefox), browsers that do not yet support text fragments gracefully ignore the fragment and load the source page at the top.
- **Impact**: Graceful degradation without broken links or script errors.

---

## 2. Active Backlog Candidates

These features represent the immediate forward roadmap following Milestone 4A:

### Milestone 4C: Los Angeles City vs. LA County Jurisdiction Detection
- **Objective**: Accurately detect and distinguish claims concerning the **City of Los Angeles** (Mayor, LAPD, City Council) from claims concerning **Los Angeles County** (Board of Supervisors, Sheriff's Department / LASD, 88 incorporated cities, and unincorporated territories).
- **Scope**:
  - Add jurisdiction classification flags to inquiry clarification and extraction schemas.
  - Attach visual jurisdiction badges in the UI (e.g., "City of LA Jurisdiction" vs. "LA County Jurisdiction").
  - Flag jurisdictional mismatches (e.g., attributing county jail policies to the city mayor).

### Milestone 4D: Report Studio One-Click Export & Citation Polish
- **Objective**: Enhance the Custom Report Studio with seamless export capabilities.
- **Scope**:
  - Add one-click "Download as Markdown (`.md`)" and "Download as Plain Text (`.txt`)" buttons to the generated report view.
  - Add "Copy Formatted Citation" for individual quotes and full Works Cited bibliographies.
  - Polish Markdown rendering for nested lists and blockquotes.
