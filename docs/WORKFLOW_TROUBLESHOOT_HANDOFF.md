# Handoff: ScoopScope AI Workflow Troubleshooting (Gemini app + Antigravity)

Paste this into a new chat. You are helping a **non-technical owner** (Minh) run and troubleshoot a free AI build workflow.
You cannot see the repo. If you need repo state, ask Minh to attach `Downloads\scoopscope_pack.md` (made by `python scripts/pack.py`).
Lead with the answer, keep it short, give step-by-step clicks, and end every reply with **"In plain terms:"** (1–2 jargon-free sentences).
Minh will not pay for anything extra. Don't recommend paid tools or API keys.

---

## 1. The project
**ScoopScope** is a claim and source investigation web app: FastAPI backend, zero-build vanilla HTML/CSS/JS frontend (`frontend/app.js` ~3,000 lines), ~283 pytest tests including headless-Chrome browser tests.
Local app: `http://127.0.0.1:8000`. Repo: `github.com/skynetrebel42/scoopscope`. Windows 11, project folder in OneDrive.
Hard rules live in `AGENTS.md`: stage files by exact path only (never `git add .` / `-A` / `commit -a`), stop at a **Push Gate** for owner approval before `git push`, and end every report with "In plain terms:".

## 2. Tools and limits (verified Oct 19–20, 2026)
| Tool | What Minh has | Limits |
|---|---|---|
| **Gemini app** (gemini.google.com) | Google AI Pro **student trial**, model "Gemini 4 Argon" | Can't write to GitHub. "Import code" is a **read-only snapshot** taken at import time (1 repo, ≤5,000 files, ≤100 MB) and only sees **pushed** commits. Big attachments plus long chats → freezes on "Stopped thinking". **Gems were replaced by Skills** (rollout began Oct 13, 2026). **Task mode** (formerly "Spark") is for background/scheduled jobs. Use **Chat** for planning. |
| **Antigravity IDE** (Google's agent IDE) | Pro trial | Models on trial: **Gemini 3.8 Flash**, plus **Claude Opus 4.6 / Sonnet 4.6 (Thinking)** and GPT-OSS-120b **until Nov 2, 2026** (then removed). Gemini 4 Argon and Claude 5.5 are **non-trial only**, and Argon isn't in the IDE anyway. |
| Gemini CLI / Gemini Code Assist | Dead end | Stopped serving free and Pro individual accounts **June 18, 2026**. Users were moved to Antigravity. |
| Argon via paid API | Rejected | Owner won't pay. |

## 3. Why we changed the workflow (root causes found in the audit)
Old loop: Argon (Gemini app) planned **without seeing code**, and Minh copy-pasted briefs to Flash (Antigravity). Bugs in milestones 4E–4H:
1. The brief invented element IDs. Flash added hidden **dummy elements** to pass tests, which led to **two Report Studios** on screen.
2. An async search in tab 1 rendered into tab 2 (race condition). Tests ran sequentially, so they never caught it.
3. There was no global `.hidden` CSS rule (12 per-component rules), so a hidden panel stayed visible.
4. Multi-claim results made the page grow without limit.
Tests passed because the browser tests ran a rebuilt copy of the page under simulated time and checked classes, not what was actually visible.

## 4. The new loop (documented in `docs/BUILD_LOOP.md`)
**One trip each way per milestone:**
1. **Gemini app, Chat, new chat:** type `/scoopscope-planner` (custom Skill uploaded from `docs/planner/SKILL.md`), attach **one file** `Downloads\scoopscope_pack.md`, say "go". Argon reviews the last build's diff (if any), offers 2–4 options, Minh picks a letter, and Argon outputs a spec that **describes behavior, never invented IDs**.
2. **Antigravity, new chat, Flash:** paste the spec → `/build` (branch, test-first, checks that names exist, commit by path, runs `pack.py`) → `/playtest` (browser agent clicks through the app at 127.0.0.1).
3. **Minh:** 2-minute click-through. Next Gemini trip with the new pack, where Argon approves or lists fixes. Then "push approved".
Until Nov 2, Opus 4.6 can be used in Antigravity for `/review` (fresh chat reads `git diff master...HEAD`).

**Mechanical guards now in the repo:** global `.hidden { display:none !important }`, `test_selector_inventory` (every ID `app.js` uses exists exactly once), a `.git/hooks/pre-commit` that runs pytest, and `.agents/rules/frontend.md` (no dummy elements; stop on a selector mismatch).

## 5. Antigravity settings applied
- Security mode: **Full access** (Sandboxed may block Chrome tests, `pack.py` writing to Downloads, and the playtest server). Terminal auto-execution: **Request Review**.
- Allow list (**one entry each**): `python -m pytest`, `python scripts/pack.py`, `git status`, `git diff`, `git log`, `git branch`, `git fetch`.
- Deny list (= always ask): `git push`, `git add`, `git commit`, `git reset`, `git rebase`, `git clean`, `git stash`, `Remove-Item`, `rm`, `del`.
- Review Policy **Agent Decides**; Conversation History **Off**; Knowledge **Off**; Auto-Fix Lints On; Non-workspace access Off; Sounds On; Auto-Expand Changes On; URL allow `127.0.0.1` and `localhost`.
- Google Plugins: turn off unused ones. "Failed to load MCP servers": no MCP servers are used. Fix by setting the MCP config to `{ "mcpServers": {} }`.

## 6. Current state (Oct 21, 2026)
- **Branch**: `milestone/5a-copy-quote-citation` (local branch, paused; do not switch branch or push).
- **Modified files**:
  - `backend/tests/test_la_jurisdiction.py`
  - `frontend/app.js`
  - `frontend/style.css`
  - `frontend/test_runner.html`
  - `backend/tests/test_frontend_ordering.py`
  - `.agents/workflows/build.md`
  - `.agents/workflows/plan.md`
  - `.agents/workflows/playtest.md`
  - `.agents/workflows/review.md`
  - `AGENTS.md`
  - `docs/BUILD_LOOP.md`
  - `docs/specs/milestone-5a-copy-quote-citation-and-known-issues.md`
  - `docs/WORKFLOW_TROUBLESHOOT_HANDOFF.md`

### Completed Repairs & Actual Verification Results
1. **Clarification endpoint offline mock repair (`backend/tests/test_la_jurisdiction.py`)**:
   - `test_clarify_endpoint_surfaces_la_disambiguation` previously attempted a live Gemini API request without an API key in offline tests.
   - Repaired by mocking `app.main.gemini.clarify_inquiry` using `unittest.mock.AsyncMock` returning `ClarificationResponse`.
   - **Verification**: PASSED offline via `.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_la_jurisdiction.py -k "test_clarify_endpoint_surfaces_la_disambiguation"` (1 passed in 0.36s).
2. **`matchedSource` scope repair (`frontend/app.js`)**:
   - Fixed `ReferenceError: matchedSource is not defined` inside `renderResearchResults` passage loop (app.js:1901) by properly resolving `matchedSource` from `data.retrieved_sources` and `matchedHit` from `data.search_hits`.
   - **Verification**: Eliminated render crash; browser test run progressed to assertions.
3. **Latest Manual Browser Test Run (`test_frontend_request_ordering_in_browser`)**:
   - Executed in ordinary PowerShell terminal outside sandbox: **8 passed, 1 failed in 13.04s**.
   - 8 Passing: Initial empty load, inquiry dispatch, request sequence tokens, Cornell notes 2-column rendering, tab session isolation, evidence accordion toggle, Report Studio visibility, and full journey.
   - 1 Failing: Suite 11 — "Button text updates to 'Copied!' on click".

### Pending Deferred Product Issues
The following Milestone 5A product repairs are strictly **paused and deferred**:
1. **Copy button failure (Suite 11)**:
   - Root cause: In headless Chrome, `navigator.clipboard.writeText` rejects asynchronously due to lack of window focus/permissions. The test's timer raced before the rejection, and the button lacked honest rejection handling.
2. **Source-ID matching prioritization**:
   - Exact `p.source_id === s.source_id` matching must be verified strictly before URL fallback.
3. **Unsupported retrieval-date fallback**:
   - Removal of `new Date().toISOString().split("T")[0]` fallback from citation records when no timestamp exists on passage or source.

### Work Completed Since 8 Passed / 1 Failed Result (Verified vs Unverified)
- `frontend/app.js`: Prioritized `source_id` matching before URL fallback; removed `new Date()` fallback from `quoteSourceRecord`; updated `copyTextToClipboard` to return boolean; updated button click handler to show `"Copied! ✓"` on success and `"Copy Failed"` on rejection. (**UNVERIFIED in browser** — deferred).
- `frontend/style.css`: Added `.btn-copy-quote-citation.copy-failed` styling. (**UNVERIFIED in browser** — deferred).
- `frontend/test_runner.html`: Replaced timer with deterministic mock for `copyTextToClipboard`; added verification for standard/APA/MLA copied text, honest rejection feedback, source-ID priority, and no date invention. (**UNVERIFIED in browser** — deferred).
- `backend/tests/test_frontend_ordering.py`: Added `test_quote_attribution_source_id_priority_and_no_date_invention`. (**UNVERIFIED / FAILING** due to whole-file date check — deferred).

---

## 7. Antigravity Workflow & Execution Rules

### What Minh Must Configure in the Antigravity IDE UI (Cannot Be Changed by Files)
1. **Command Review Prompts**: The IDE sandbox controls prompt policies. To prevent repeated prompt pauses on safe commands, click "Always Allow" or add `python` and `git` to the IDE allow-list in the UI.
2. **Sandbox Restrictions**: The IDE enforces sandbox boundaries (preventing Windows pipes/IPC needed by Chrome). Project rules cannot override these boundaries or grant pipe access.

### What Is Configured in Project Rules (`AGENTS.md`, `.agents/workflows/`)
1. **Python Virtual Environment**: All commands strictly invoke `.\backend\.venv\Scripts\python.exe` (never system `python`).
2. **No Sandbox Troubleshooting Loops**: When browser tests hit sandbox pipe restrictions, the agent will NOT retry or troubleshoot permissions. It will immediately output one ordinary-PowerShell rerun command:
   ```powershell
   Set-Location "c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope"; .\backend\.venv\Scripts\python.exe -m pytest <test-path> --basetemp=<fresh-disposable-path> --tb=short -v
   ```
3. **Autonomous Routine Progress**: The agent proceeds through routine file edits, checks, and offline tests within the authorized task without pausing for reconfirmation.
4. **Scoped Reporting**: Failures are reported honestly and repaired ONLY when in the user's explicit scope.
5. **Git Push Gate**: Staging strictly by exact path (`git add <exact-path>`); stops at Push Gate for owner approval.

## 8. Key files
`AGENTS.md` (rules) · `docs/BUILD_LOOP.md` (loop, setup, workflow texts) · `docs/planner/SKILL.md` (Gemini Skill) · `scripts/pack.py` (makes the pack) · `.agents/rules/frontend.md` · `.agents/workflows/{build,review,playtest}.md` · `.handoff-builder.md` / `.handoff-planner.md` / `PROJECT_HANDOFF.md` (state and decision log).
