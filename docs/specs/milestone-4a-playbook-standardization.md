# Milestone 4A Specification: Playbook Repo Standardization & .gitignore Hygiene Fix

**Milestone Identifier**: 4A  
**Decision Reference**: Decision 008  
**Baseline Commit**: `582272c`  
**Date**: October 2026  
**Status**: In Progress  

---

## 1. Goal

Standardize the ScoopScope repository structure and workflow documentation to align strictly with `WORKFLOW_PLAYBOOK.md` Section 3, and resolve the `.gitignore` gaps discovered during the Milestone 4B read-only verification pass.

Specifically, this milestone establishes:
1. Complete Git and secret hygiene so local artifacts (`manifest.txt`, `*.patch`, `.pytest_cache/`) do not pollute `git status`.
2. A streamlined single-source-of-truth documentation suite:
   - `PROJECT_HANDOFF.md`: Project vision, 3G trifecta roles, launch & test commands, complete Decision Log (`001`–`008`), and shipped milestones (`001`–`007`).
   - `ARCHITECTURE.md`: Repository layout mapped by risk level (HIGH CAUTION, MODERATE CAUTION, SAFE TO EDIT).
   - `KNOWN_ISSUES.md`: Active warnings and backlog candidates (Milestone 4C, Milestone 4D).
   - `docs/HOW_IT_WORKS.md`: Plain-English owner guide for Minh explaining claim lifecycle, plain-English glossary, and 1-line-per-milestone shipped log.
   - `AGENTS.md`: Compact agent operating instructions pointing to the playbook files and preserving hard evidence, retrieval budget, and safety guardrails.
   - `docs/archive/.gitkeep`: Empty placeholder directory for archived artifacts and obsolete reviews.

---

## 2. Out of Scope

- **Runtime Code Modifications**: Zero modifications to backend Python code (`backend/app/**`), frontend assets (`frontend/**`), or existing test implementations (`backend/tests/**`).
- **Dependencies & Environments**: No changes to `requirements-lock.txt`, virtual environments, or package installations.
- **Git Push**: Antigravity Builder commits locally and stops at the Push Gate; no push to `origin/master` without explicit Owner approval.

---

## 3. Verification Criteria

1. **Git Exclusion Hygiene**:
   - `git check-ignore -v` cleanly matches all secret, environment, archive, patch, and cache patterns:
     - `.env`, `backend/.env`
     - `.venv/`, `backend/.venv/`
     - `test.zip` (`*.zip`)
     - `test.patch` (`*.patch`)
     - `manifest.txt`
     - `.pytest_cache/`, `backend/.pytest_cache/`
2. **Clean Working Tree**:
   - `git status -s` shows zero untracked files and no noise from local patches, manifests, or cache directories.
   - Only the specified 8 files are staged for commit:
     1. `.gitignore`
     2. `AGENTS.md`
     3. `PROJECT_HANDOFF.md`
     4. `ARCHITECTURE.md`
     5. `KNOWN_ISSUES.md`
     6. `docs/HOW_IT_WORKS.md`
     7. `docs/specs/milestone-4a-playbook-standardization.md`
     8. `docs/archive/.gitkeep`
3. **Automated Test Regression**:
   - Full automated test suite passes 100% offline via `.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v` (164/164 tests passing).
