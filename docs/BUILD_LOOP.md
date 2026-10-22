# ScoopScope Build Loop (Antigravity only)

Owner types four commands per milestone. No copy-paste between apps.

One trip each way per milestone:

| Step | Where | Owner does |
|---|---|---|
| Gemini | Gemini app, new chat, `/scoopscope-planner` | Attach `Downloads\scoopscope_pack.md`, say "go". It reviews the last build (if any), then you pick a letter and copy the spec. |
| Build | Antigravity, new chat, Flash | Paste the spec (or Gemini's fix list), then `/build`, then `/playtest` |
| Ship | — | 2-minute click-through. If Gemini approved, say "push approved". Otherwise go back to Gemini with the new pack. |

`/build` ends by running `python scripts/pack.py`, which writes the pack (git state + diff + handoff docs, ~40 KB) for the next Gemini trip.
Gemini never sees code except the diff, so it can't freeze or guess IDs. It writes behavior; Flash finds the real code.

Rules: one small change per milestone. If a step goes sideways, close the chat and start that step again in a new one.

---

## One-time setup (Agent: do this when the Owner says "do the setup in docs/BUILD_LOOP.md")

Branch `setup/workflow` from master. No product features.

1. Delete `GEMINI.md` (duplicates AGENTS.md and says the Builder is Argon, which is wrong; Antigravity loads both every turn).
2. Create `.agents/rules/frontend.md` with exactly:
   ```
   ---
   trigger: glob
   globs: frontend/**
   ---
   - Never add an element, id, class or CSS rule only to satisfy a test or brief.
   - If a brief or test names a selector that doesn't exist in frontend/index.html or frontend/app.js, STOP and report the mismatch. Never create aliases or hidden dummies.
   - Show/hide only with the `.hidden` class. Never add per-component `.x.hidden` rules.
   - Async results are saved to the session tab they started in (by session id). Only the active tab is drawn on screen.
   ```
3. `frontend/style.css`: add `.hidden { display: none !important; }` once, then delete the per-component `.something.hidden` rules. Run tests.
4. Add `test_selector_inventory` to `backend/tests/test_frontend_ordering.py` (plain Python, no browser):
   - every id used in app.js via `getElementById("x")` or `querySelector("#x")` exists exactly once in index.html OR is assigned in app.js (`.id = "x"`);
   - no id appears twice in index.html.
   It should FAIL first on `#report-studio-section` and `#claim-input`. Then delete the dummy `<input id="claim-input">` in index.html, every `report-studio-section` lookup in app.js, and the inline report fallback near app.js:1790 until it passes.
5. Create `.git/hooks/pre-commit`:
   ```
   #!/bin/sh
   python -m pytest backend/tests -q || exit 1
   ```
6. Create three workspace workflows (Customizations → Workflows → Workspace) named `build`, `review`, `playtest`, using the text in the sections below. (No `plan` workflow: Antigravity has a built-in `/plan`, and Gemini does the planning.)
7. Report: changed files, real pytest output, "In plain terms:". Stop at the Push Gate.

---

## /build
1. Read AGENTS.md, .handoff-builder.md, and the one active spec in docs/specs/.
2. Before editing, list every file, element id and CSS class the spec names, and grep to confirm each exists. If any is missing or unclear, STOP and report.
3. Create branch milestone/<spec-name> from master.
4. Authorized routine work proceeds autonomously without conversational reconfirmation. Write the failing test first, then the minimal code. Run: `.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q`
5. If browser tests encounter the known sandbox restriction, do not retry or troubleshoot permissions; hand off one ordinary-PowerShell command with `Set-Location` and a fresh disposable `--basetemp`.
6. Commit by exact path, then run `.\backend\.venv\Scripts\python.exe scripts/pack.py` (writes Downloads\scoopscope_pack.md for the Gemini review).
7. Report: git diff --stat, every new id= or class= added (grep the diff), real pytest output, "In plain terms:". Stop at the Push Gate.

## /review
Read only the active spec and the output of `git diff master...HEAD`. Do not edit code.
Look for: elements/ids added only for tests; duplicate code paths that render the same panel; CSS that can override .hidden; async code writing to the active tab instead of its origin session; anything outside the spec's scope.
List findings as file:line + one sentence. If none, say "No findings."

## /playtest
Start the server (command in PROJECT_HANDOFF.md). With the browser agent at http://127.0.0.1:8000, screenshot each step:
1. Fresh load. 2. "+ New" tab. 3. Start a search in tab 1, immediately click "+ New", wait — results must land in tab 1 only.
4. Prompt mentioning Santa Monica, Norwalk, LA County and City of LA; research 2 claims. 5. Check quotes, open the report studio. 6. Clear Workspace.
Report anything duplicated, visible when it shouldn't be, a horizontal scrollbar, results in the wrong tab, or a page that keeps growing.

## Close-out (after "push approved")
Push, move the spec to docs/archive/, add one line to PROJECT_HANDOFF.md's shipped list and one line to docs/HOW_IT_WORKS.md, update .handoff-builder.md. Nothing else.
