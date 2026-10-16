# Milestone 3A Review & Verification Report

Last updated: 2026-10-15  
Milestone: 3A — Clarify and Confirm the Inquiry

---

## 1. Environment & Git Status

- **Canonical Workspace & Git Root**: `c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\`
- **Milestone 2C Baseline Commit**: `566639720a109b7b82e561d87066ea18d0be911b` (branch `master`)
- **Working Tree Status**: Verified and tested clean.
- **Secret Protection**: `.env` and `backend/.env` remain strictly git-ignored and excluded from tracking. No API keys, credentials, or secrets are committed or displayed.

---

## 2. Test Execution & Final Results

### Full Automated Test Suite Command
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

### Full Automated Results
- **Outcome**: **132 passed**, 0 failed, 0 skipped, 2 deprecation warnings in external libraries (`google.genai.types` and `starlette.testclient`).
- **Duration**: ~31.2 seconds across all unit, integration, SSRF security, and clarification checks.

### Headless Chrome Browser Ordering & Intake Suite Command
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_frontend_ordering.py -v -s
```

### Browser Test Results
- **Outcome**: **1 passed** (108 assertions passed across 10 test suites in 1.40s).
- **Browser Binary**: `C:\Program Files\Google\Chrome\Application\chrome.exe` (`--headless=new`).

### Complete Test Suite Breakdown

| Test File | Tests / Asserts | Focus Area | Status |
|---|---|---|---|
| `backend/tests/test_clarification.py` | 10 tests | Milestone 3A intake clarification, 5 acceptance checks, DACA/beef/Obama samples, temporal distinction, 3 coherent choices, 2-round bound, direct confirmation for clear claims, context/origin limitation notes | PASSED |
| `backend/tests/test_frontend_ordering.py` | 1 test (108 browser asserts) | Headless Chrome browser test: 10 test suites covering request ordering, stale discard, Try Again, research action, snippet rendering, passage rendering, draft edit invalidation, inert text XSS protection, claim switching A->B (F2), and Milestone 3A clarification, 3 option buttons, scope question editing, and invalidation | PASSED |
| `backend/tests/test_safe_fetcher.py` | 65 tests | IP ranges, IPv4-mapped IPv6, CGNAT, scheme/standard & bad port/credential validation (R3), public success, private/loopback rejection, public-to-private redirect block, DNS rebinding block, 3-hop redirect limit, MIME rejection, 1MB size limit, cancellable deadline and slow DNS enforcement with elapsed bounds (R2), socket connection enforcement | PASSED |
| `backend/tests/test_extraction.py` | 14 tests | Claim extraction, validation, error mapping, unique ID generation | PASSED |
| `backend/tests/test_serper_provider.py` | 12 tests | Serper API contract, 401/403/429 status mapping, bounded 5xx retries, outbound attempt accounting, secret redaction | PASSED |
| `backend/tests/test_search_contract.py` | 9 tests | `SearchProvider` Protocol, `SearchResultHit` snippet immutability, date/dependence defaults, query generation | PASSED |
| `backend/tests/test_passage_extractor.py` | 9 tests | Script/style stripping, entity decoding (single decode R1), exact substring offsets, provenance verification, URL deduplication, void element handling (<embed> R1), table cell number separation (R1), plain-text MIME preservation (<exception> R1) | PASSED |
| `backend/tests/test_research_endpoint.py` | 12 tests | Orchestrator flow with mock provider & fetcher (injected DNS R5), candidate page budget cap (3), partial fetch failures, 503 on missing credentials, cancellable orchestrator deadline enforcement (R2), malformed port error isolation (R3), search provider failure propagation on 401/403/429/500 (F1), partial evidence preservation on search failure with source URL (F1), legitimate 0-hit search distinguishability (F1), cooperative synchronous extraction deadline enforcement on large documents (F3) | PASSED |
| **Total** | **132 passed** | **Zero failures across all 8 modules** | **ALL PASSED** |

---

## 3. Verification of the Five Acceptance Checks

### Acceptance Check 1: Intent & Scope Fidelity
- Verified across real user samples (DACA, beef, Obama, clear dated claims, ambiguous claims).
- The selected option or user free text directly shapes the confirmed inquiry question without drift.
- Temporal distinction is strictly preserved: a current-status inquiry (e.g. active DACA court injunctions) never silently converts into a historical investigation (e.g. 2012 enactment), and vice versa.

### Acceptance Check 2: No Invented Particulars
- The beef example retains unspecified chemical substances as unknown. It never invents hormones or antibiotics without evidence or confirmation.
- Preserves "Europe" as a geographic designation without silently converting to "EU" unless confirmed or explicitly noted in unresolved scope.
- Compound claims are decomposed into linked checkable subclaims while preserving original wording verbatim and causal linkages (`claim_type=ClaimType.CAUSAL`).

### Acceptance Check 3: Bounded Clarification
- When clarification is needed, exactly three mutually exclusive choices answering the same question dimension appear alongside a free-text input.
- Second-round clarification correctly synthesizes round 1 choices into the confirmed scope.
- **Third automatic round is impossible**: Hard ceiling after round 2 (`max_rounds_reached=True`, `clarification_needed=False`, `is_clear=True`), surfacing remaining uncertainties for user review.
- Clear, concrete statements (e.g. Karen Bass mayoral swearing-in) proceed directly through scope confirmation without redundant clarifying questions.

### Acceptance Check 4: State & Spending
- Clarification requests issue **zero** outbound search requests, **zero** page fetches, and consume **zero** search budget before explicit scope confirmation.
- One selected claim triggers exactly one bounded research action adhering to existing limits (max 2 Serper queries, 5 hits, 3 candidate pages, 90s deadline).
- Editing draft text or source URL immediately invalidates pending clarification, clears in-flight research (`activeResearchSeq++`), and disables buttons on outdated snapshots.

### Acceptance Check 5: Honest UI & Limitation Transparency
- Displays "We will investigate: [editable question]" with Material Unresolved Assumptions listed as distinct inspectable items.
- Inquiries identified as `understand_context` or `trace_origin` honestly disclose that dedicated context and origin pipelines are future milestones, while offering an editable factual research question for current evidence retrieval.
- Factual claims are labeled **"Checkable claim"** with explanatory tooltips clarifying that this is an assertion classification, not a verified finding.
- Stale "claim extraction only" and "research not yet performed" notices have been replaced with live per-stage status indicators.
- Provider and credential failures return sanitized HTTP 503 errors with clear user feedback; no simulated clarification or fabricated findings are returned on failure.

---

## 4. Remaining Integration Limitations

1. **No External Live Search Key Configured by Default**: Requires the user to add `SERPER_API_KEY` to `backend/.env` for live queries.
2. **Context and Origin Tracing Workflows**: Stored honestly and surfaced with clear limitation notices; dedicated graph/origin tracing pipelines remain planned for later slices.
3. **No Automated Verdicts or Truth Scores**: Verbatim passages and search snippets are surfaced for human audit only; no automated truth scores, confidence percentages, or supported/contradicted verdicts are generated.
4. **Dates and Source Dependence Unknown**: Publication dates and source independence remain explicitly unknown unless verifiable metadata is extracted in future milestones (3B).
