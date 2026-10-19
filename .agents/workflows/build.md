# /build

1. Read AGENTS.md, .handoff-builder.md, and the one active spec in docs/specs/.
2. Before editing, list every file, element id and CSS class the spec names, and grep to confirm each exists. If any is missing or unclear, STOP and report.
3. Create branch milestone/<spec-name> from master.
4. Write the failing test first, then the minimal code. Run: python -m pytest backend/tests -q
5. Commit by exact path, then run `python scripts/pack.py` (writes Downloads\scoopscope_pack.md for the Gemini review).
6. Report: git diff --stat, every new id= or class= added (grep the diff), real pytest output, "In plain terms:".
