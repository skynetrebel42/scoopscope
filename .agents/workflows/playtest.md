---
description: Test ScoopScope in the local browser for tab isolation, report visibility, duplicate panels, and layout problems.
---

# /playtest

Start the server (`.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`). With the browser agent at http://127.0.0.1:8000, screenshot each step:
1. Fresh load. 2. "+ New" tab. 3. Start a search in tab 1, immediately click "+ New", wait — results must land in tab 1 only.
4. Prompt mentioning Santa Monica, Norwalk, LA County and City of LA; research 2 claims. 5. Check quotes, open the report studio. 6. Clear Workspace.
Report anything duplicated, visible when it shouldn't be, a horizontal scrollbar, results in the wrong tab, or a page that keeps growing.
