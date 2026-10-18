# Milestone 4E Spec: Multi-Tab Workspace Persistence (`localStorage` Auto-Save & Restore + Clear Workspace Reset)

**Milestone**: 4E  
**Status**: In Progress  
**Baseline Commit**: `f8844c7`  
**Area**: Frontend State Persistence, `localStorage` Auto-Save/Restore, One-Click Clear Workspace  

---

## 1. Goal & Context

ScoopScope provides an evidence-first, cryptographic approach to verifying claims: claims are clarified, evidenced through verbatim, character-offset sliced passages from real web pages, and organized in paired Cornell Notes and a custom Report Studio with verified citations.

In Milestone 4E, we solve the friction of losing investigation tabs, Cornell Notes research, and custom report selections upon page reload or accidental browser closing:
1. **Multi-Tab Workspace Persistence**: Automatically persist the entire multi-tab `workspaceState` into browser `localStorage` under the key `scoopscope_workspace_v1`.
2. **Seamless Reload Restoration**: When reloading or re-opening the application, all open session tabs, active session selection, input drafts, clarification state, per-claim research tabs, Cornell Notes evidence cards, checked Evidence Bank quotes (`selectedQuotes`), and citation style (`activeCitationStyle` / `#citation-style-select`) are restored instantaneously without re-running backend searches or consuming API tokens.
3. **One-Click Workspace Reset**: Provide an instant, one-click `#btn-clear-workspace` button in `#session-tabs-bar` to wipe saved state from `localStorage`, reset `workspaceState` to a single clean `"Session 1"` tab, reset citation style to `"standard"`, and refresh the UI immediately without blocking modal dialogs.
4. **Resilient Failure Recovery**: Gracefully handle missing, corrupted, or schema-invalid JSON in `localStorage` by safely resetting to default Session 1 state without crashing or throwing unhandled JavaScript exceptions.

---

## 2. User Experience & What the User Sees

- **Session Tabs Bar (`#session-tabs-bar`)**:
  - Displays session tabs in `#session-tabs-list` with active tab highlighting, tab title, and an inline `×` close button (`.btn-close-tab`).
  - Includes `[ + New ]` (`#btn-new-session`) to start fresh inquiries.
  - Includes `[ Clear Workspace ]` (`#btn-clear-workspace`) positioned on the right of `#session-tabs-bar`.
- **Restoration Across Refresh**:
  - Refreshing (`F5` / `Ctrl+F5`) restores all session tabs, active tab focus, statement drafts, Cornell Notes results, checked quote checkboxes in the Evidence Bank, and selected citation style (`standard`, `apa`, or `mla`).
  - Restoring never leaves transient loading spinners stuck on screen: `isClarifying` and `isResearching` are guaranteed `false` on restore.
- **One-Click Clear Workspace**:
  - Clicking `#btn-clear-workspace` wipes `scoopscope_workspace_v1` from `localStorage`, resets the workspace to a single clean `"Session 1"` tab, resets the statement input, hides previous research results and report studio, sets citation style back to `"standard"`, and renders the clean tab immediately.

---

## 3. Architecture & Data Contracts

### Storage Key & Versioning
- **Key**: `scoopscope_workspace_v1`
- **Constant**: `WORKSPACE_STORAGE_KEY = "scoopscope_workspace_v1"`
- **Schema**:
  ```json
  {
    "version": 1,
    "activeSessionId": "sess_...",
    "citationStyle": "standard",
    "sessions": [
      {
        "id": "sess_...",
        "title": "Session 1: ...",
        "inputText": "...",
        "sourceUrl": "https://...",
        "scopeQuestion": "...",
        "scopeEdited": false,
        "claims": [...],
        "claimResearchTabs": { "...": [...] },
        "activeClaimTabId": { "...": "run_..." },
        "selectedQuotes": [ ["<quoteKey>", { "checked": true, "passage": {...}, "claimId": "..." }] ],
        "data": {...},
        "isClarification": false,
        "clarificationExchanges": [...],
        "isClarifying": false,
        "isResearching": false
      }
    ]
  }
  ```

### Decisions Enforced
- **Decision 014**: Persist multi-tab workspace state in browser `localStorage` (`scoopscope_workspace_v1`) with a one-click `#btn-clear-workspace` button.
- **Decision 015**:
  - One-click instant reset on `#btn-clear-workspace` with zero `window.confirm()` blocking popups.
  - `Map` <-> JSON array serialization for `selectedQuotes`: quotes are serialized as an array of `[key, value]` pairs in JSON so that `Map` objects serialize and deserialize losslessly.
  - Transient loading spinner reset: `isClarifying` and `isResearching` are forcibly reset to `false` on restore, hiding any in-flight progress banners.

---

## 4. Scope Boundaries & Out of Scope

- **In Scope**:
  - `docs/specs/milestone-4e-localstorage-persistence.md`
  - `frontend/index.html`
  - `frontend/style.css`
  - `frontend/app.js`
  - `backend/tests/test_frontend_ordering.py`
- **Out of Scope**:
  - Backend database models, cloud sync, or remote user accounts.
  - Any modifications to backend Python application files (`backend/app/**`).
  - Blocking `window.confirm()` or `window.alert()` dialogs on workspace reset.

---

## 5. Verification & Acceptance Criteria

1. **Static Contract**:
   - `frontend/index.html` contains `id="btn-clear-workspace"` inside `#session-tabs-bar`.
   - `frontend/app.js` defines `WORKSPACE_STORAGE_KEY = "scoopscope_workspace_v1"`, `saveWorkspaceToStorage()`, `loadWorkspaceFromStorage()`, and `clearWorkspace()`.
2. **Headless Chrome Persistence & Restore Across Reload**:
   - Researched claim cards, Cornell Notes, Evidence Bank quote selections, switched citation style (`"apa"`), and multi-session tabs are saved to `localStorage` as valid version 1 JSON.
   - Reload restores tabs, Cornell notes, checked quote state, and citation style without re-running backend requests.
   - Forced transient loading flags are sanitized to `false` and loading banners remain hidden.
3. **Corrupted JSON Recovery**:
   - Corrupted or invalid JSON in `scoopscope_workspace_v1` falls back gracefully to a clean `"Session 1"` without throwing unhandled exceptions.
4. **One-Click Clear Workspace**:
   - Clicking `#btn-clear-workspace` wipes/resets saved state, restores a clean `"Session 1"` tab, empties the statement input, and hides the report studio.
5. **Full Regression Guardrail**:
   - All 276 baseline offline tests continue to pass.
