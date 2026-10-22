---
description: Implement the approved ScoopScope milestone and verify it before the Push Gate.
---

# /build

1. Read AGENTS.md, .handoff-builder.md, and the one active spec in docs/specs/.
2. Before editing, list every file, element id and CSS class the spec names, and grep to confirm each exists. If any is missing or unclear, STOP and report.
3. Create branch milestone/<spec-name> from master.
4. Authorized routine work proceeds autonomously without conversational reconfirmation. Write the failing test first, then minimal code. Run: `.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q`
5. If browser tests encounter the known sandbox restriction, do not retry or troubleshoot permissions; hand off one ordinary-PowerShell command with `Set-Location` and a fresh disposable `--basetemp`.
6. Commit by exact path, then run `.\backend\.venv\Scripts\python.exe scripts/pack.py` (writes Downloads\scoopscope_pack.md for the Gemini review).
7. Report: git diff --stat, every new id= or class= added (grep the diff), real pytest output, "In plain terms:". Stop at the Push Gate.
