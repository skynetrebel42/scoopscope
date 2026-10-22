# Milestone 5A — One-Click "Copy Quote + Citation" & KNOWN_ISSUES.md Refresh

- **Goal**: Let users copy any individual verbatim quote in the Cornell Notes evidence board together with its formatted citation (honoring the active Standard, APA 7th ed., or MLA 9th ed. style) in a single click, and update `KNOWN_ISSUES.md` so its baseline and backlog match the post-4H repository state.
- **Decision Logged**: Decision 020

## 1. What the User Sees
Inside each quote item in the Cornell Notes evidence board (next to the existing "Find exact line in source ↗" link):

"The City of Norwalk enacted an urgency ordinance extending the moratorium..."
[Find exact line in source ↗]  [Copy Quote + Citation]

- **Default state**: A compact action button labeled `Copy Quote + Citation`.
- **On click**:
  1. Formats the sanitized verbatim quote (single-line, no raw `\n` sequences) paired with its deterministic source citation using the currently active citation style (`standard`, `apa`, or `mla`) and jurisdiction tag (if applicable).
  2. Copies `"Verbatim quote text" — Formatted Citation` to the clipboard (using browser clipboard API with a hidden textarea fallback).
  3. Updates the button text to `Copied! ✓` for 1.5 seconds, then restores `Copy Quote + Citation`.
- **`KNOWN_ISSUES.md` Refresh**:
  - Updates the header baseline commit and test count (284+ offline tests passing).
  - Removes the already-shipped Milestone 4C and Milestone 4D sections from the open backlog and replaces them with post-Phase-4 backlog candidates (Evidence/Jurisdiction Filtering, Portable Workspace JSON Export/Import, Contradiction Callouts).

## 2. Out of Scope
- Zero changes to backend Python application routes or schemas.
- No automated truth scores, no invented author names, and no fabricated publication dates (`(n.d.)` for APA and `Accessed <date>` for MLA when dates are absent).
- No dummy hidden elements or unreferenced IDs.

## 3. How "Done" Is Tested
1. Rendering a researched claim with verbatim quotes displays a `Copy Quote + Citation` button on each quote card.
2. Clicking the button when Standard, APA, or MLA style is selected produces a clean `"quote" — citation` string matching the selected style (including `[LA City Official]` / `[LA Local City Official]` bracketed tags where applicable and `(n.d.)` or `Accessed` fallbacks when dates are missing) and sets the button label to `Copied! ✓`.
3. Quote text copied via the button has raw `\n` escape sequences sanitized into clean spaces.
4. `test_selector_inventory` passes with zero missing or duplicate IDs.
5. `KNOWN_ISSUES.md` no longer lists Milestones 4C and 4D as unbuilt work.
