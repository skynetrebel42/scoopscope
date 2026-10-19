# Milestone 4H Specification — Empty-Tab Report Hide, Tab Scrollbar Removal, Claim Accordion & Single Works Cited

- **Document Version**: 1.0  
- **Milestone**: 4H  
- **Decision Logged**: Decision 018  
- **Baseline Commit**: `f75e8ee` (after Milestone 4G close-out & push)  
- **Test Baseline**: 282 passed offline tests across 11 test suites  

---

## 1. Problem Statement & Playtest Bug Audit

From the Owner's live playtest screenshots (`image_222adb.png`, `image_223221.png`, `ss2.pdf`, `scoopscpope1.pdf`), four UI and presentation issues were identified:

1. **Bug 1 — Report Studio Bar Still Visible on Empty Tabs (`image_222adb.png` & `image_223221.png`)**:
   - `#custom-report-section` is still visible at the bottom of empty tabs showing `0 quotes from 0 sources selected across tabs` because `.hidden` is not enforced in CSS and tab-switching/counter functions expose the bar on fresh/empty sessions.
2. **Bug 2 — White Horizontal Windows Scrollbar in `#session-tabs-list` (`image_223221.png`)**:
   - `#session-tabs-list` triggers a bright white horizontal scrollbar under the tabs when 2+ tabs have long titles due to `overflow-x: auto` without wrapping.
3. **Bug 3 — Multi-Claim Page Length: Claim Results Vertical Sprawl (`ss2.pdf`)**:
   - When an inquiry extracts multiple checkable claims (#1, #2, #3, #4), researching multiple claims leaves all full Cornell Notes boards and Technical Audit drawers expanded vertically, stretching the page to 11+ printed pages.
4. **Bug 4 — Duplicate "Works Cited" in Synthesized Reports & Literal `\n` in Quotes (`scoopscpope1.pdf` pages 8 & 10)**:
   - When `/api/report` returns markdown containing a `## Works Cited` or `### Works Cited / Bibliography` section, `app.js` also appends its own deterministic `Works Cited & Bibliography` section, resulting in two Works Cited lists stacked in the document.
   - Raw quotes scraped from web sources can contain literal `\n` or multi-newline escape sequences (`\n \n \n \n`) printing raw backslash sequences in the report.

---

## 2. Technical Requirements (Decision 018)

### 2.1 Enforce Empty-Tab Report Studio Hiding (Fix 1)
- In `frontend/style.css`, enforce global utility rules:
  ```css
  .hidden,
  [hidden] {
      display: none !important;
  }
  ```
- In `frontend/app.js`, ensure `updateAllEvidenceCounters()`, `renderReportBuilderPanel()`, `switchSession()`, and `clearWorkspace()` NEVER remove `.hidden` from `#custom-report-section` unless the active session has at least 1 researched claim result OR `totalSelectedQuotes > 0`.

### 2.2 Remove Session Tabs Horizontal Scrollbar (Fix 2)
- Update `.session-tabs-list` in `frontend/style.css`:
  ```css
  .session-tabs-list {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      overflow-x: visible;
      scrollbar-width: none;
      -ms-overflow-style: none;
      gap: 0.4rem;
      flex: 1;
  }

  .session-tabs-list::-webkit-scrollbar {
      display: none;
  }
  ```

### 2.3 Multi-Claim Page Length: Claim Results Accordion & Closed Technical Audit (Fix 3)
- Add a toggle button (`[Collapse Evidence ▴]` / `[Show Evidence (N quotes) ▾]`) with class `.btn-toggle-evidence` on each researched claim card.
- When the user clicks `Find sources` on a claim (e.g., Claim #2), automatically collapse any *other* claim cards' results containers in that session (`display = "none"`, `.hidden`), ensuring only the currently researched claim's Cornell Notes board is expanded by default.
- Clicking the toggle button on any claim card re-expands or collapses its `.claim-results-container`.
- Ensure the `Technical Audit & Raw Search Data` `<details>` element (`.technical-audit-drawer`) is closed by default (`open` attribute NOT set) when results render.

### 2.4 Single Works Cited & Clean Quote Strings in Reports (Fix 4)
- Strip any LLM-generated `Works Cited` / `Bibliography` trailing section (`/(?:^|\n)#{1,4}\s+(?:Works\s+Cited|Bibliography)[\s\S]*$/i`) before appending the deterministic `Works Cited & Bibliography` section so only ONE Works Cited section appears.
- Sanitize quote strings with `quote.replace(/\\n|\r?\n+/g, " ").replace(/\s{2,}/g, " ").trim()` in Cornell notes, report synthesis, and export formats so quotes never display raw `\n \n \n \n` sequences.

---

## 3. Strict Scope & Guardrails
- **Backend Frozen**: Zero changes to `backend/app/**`.
- **Allowed Files**:
  1. `docs/specs/milestone-4h-empty-tab-and-claim-accordion.md`
  2. `frontend/index.html`
  3. `frontend/style.css`
  4. `frontend/app.js`
  5. `backend/tests/test_frontend_ordering.py`
- **Verification**: All 282 existing tests pass plus new 4H regression tests.
