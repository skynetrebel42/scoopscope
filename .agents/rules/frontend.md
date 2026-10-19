---
trigger: glob
globs: frontend/**
---
- Never add an element, id, class or CSS rule only to satisfy a test or brief.
- If a brief or test names a selector that doesn't exist in frontend/index.html or frontend/app.js, STOP and report the mismatch. Never create aliases or hidden dummies.
- Show/hide only with the `.hidden` class. Never add per-component `.x.hidden` rules.
- Async results must be saved to the session tab they started in, by session id. Only the active tab is drawn on screen.
