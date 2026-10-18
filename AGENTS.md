# ScoopScope — Agent Operating Instructions

You are operating on **ScoopScope** at `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope`.

---

## 1. Primary Documentation & Orientation Order

Before proposing plans or editing code, read the core playbook files in this order:

1. **[PROJECT_HANDOFF.md](file:///c:/Users/minhb/OneDrive/Desktop/Projects/ScoopScope/PROJECT_HANDOFF.md)**: Project context, vision, 3G trifecta roles, launch/test commands, decision log, and shipped milestones.
2. **[ARCHITECTURE.md](file:///c:/Users/minhb/OneDrive/Desktop/Projects/ScoopScope/ARCHITECTURE.md)**: Codebase map and safety levels (HIGH CAUTION, MODERATE CAUTION, SAFE TO EDIT). Check safety protocols before touching any file.
3. **[KNOWN_ISSUES.md](file:///c:/Users/minhb/OneDrive/Desktop/Projects/ScoopScope/KNOWN_ISSUES.md)**: Active deprecations, open warnings, and backlog candidates.
4. **[docs/HOW_IT_WORKS.md](file:///c:/Users/minhb/OneDrive/Desktop/Projects/ScoopScope/docs/HOW_IT_WORKS.md)**: Plain-English architecture, claim lifecycle walkthrough, and glossary.

> [!CAUTION]
> **Never read `docs/archive/`**. Files in that directory are historical references and obsolete reviews. Loading them wastes context and risks outdated assumptions.

---

## 2. Hard Evidence & Safety Guardrails

These rules govern all phases of development. Never weaken, bypass, or compromise them:

1. **Zero Hallucination or Fabrication**:
   - Never invent sources, quotes, citations, fallback choices, synthetic subclaims, or truth scores.
   - If evidence cannot be retrieved, the finding is strictly **`unresolved`**, never false.
   - Preserves contradictory evidence and material qualifications. Never smooth over disagreements.
2. **Strict Retrieval & Execution Budgets**:
   - Exactly 1 claim investigated per user action.
   - Maximum 2 Serper queries per action (including retries), capped at 5 hits per query.
   - Append `-filetype:pdf` to all search queries.
   - Maximum 3 candidate pages fetched per research action.
   - Overall monotonic 90-second research deadline across search, fetch, and extraction.
3. **SSRF & Network Hardening**:
   - Enforce destination IP pinning by resolving DNS, checking against blocklists (loopback, RFC 1918, link-local, CGNAT, multicast), and binding sockets directly to validated IPs.
   - Max 3 redirects with IP re-validation on every hop.
   - Enforce 1 MB decompressed size limit and 10s connect / 30s total timeouts.
   - Enclose all fetched content in `<untrusted_source_content>` boundaries in LLM prompts.
4. **Defensible Date Provenance Only**:
   - Extract publication/update dates strictly from JSON-LD metadata, HTML `<meta>` tags, HTML `<time>` tags, or visible bylines.
   - Never infer dates from HTTP `Date` headers or URL path digits.
5. **Inert DOM Rendering**:
   - Set all external titles, snippets, URLs, and passages strictly via `textContent` or `document.createTextNode()`. Zero raw HTML injection.
6. **Git Staging & Push Gate**:
   - Stage files only by exact path: `git add <exact-path>`.
   - Never use bulk staging (`git add .`, `git add -A`, or `git commit -a`).
   - Stop at the **Push Gate** after committing locally: present the commit list and wait for Owner approval before running `git push`.
7. **Report Convention**:
   - Always end every report with a dedicated section headed `In plain terms:` (1–2 plain-English, jargon-free sentences explaining what the user will notice).
