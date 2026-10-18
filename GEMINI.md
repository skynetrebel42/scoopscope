# ScoopScope — Agent Guidance

You are the **Builder agent** operating under `WORKFLOW_PLAYBOOK.md` in the 3G Trifecta model (Owner: Minh, Planner: Gemini Chat / Argon, Builder: Antigravity / Argon).

## Startup Read Order for Fresh Sessions
Before proposing plans, executing tasks, or modifying files, read context strictly in this order:
1. **[AGENTS.md](./AGENTS.md)**: Hard evidence rules, security boundaries, and core operating principles.
2. **[.handoff-builder.md](./.handoff-builder.md)**: Active baseline state, latest commit hash, test suite count, and next active spec.
3. **[PROJECT_HANDOFF.md](./PROJECT_HANDOFF.md)**: Full project context, 3G roles, launch/test commands, decision log, and shipped milestone history.
4. **Active Spec in `docs/specs/`**: The single active milestone spec referenced by `.handoff-builder.md`.

> [!CAUTION]
> **Never read `docs/archive/`**. Files in that directory are historical references and completed milestone records. Loading them wastes context and risks outdated assumptions.
