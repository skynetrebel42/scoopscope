# Milestone 4D Spec: Report Export, Citation Styles, and Municipal Jurisdiction Ranking

**Milestone**: 4D  
**Status**: Ready for Execution  
**Baseline Commit**: `94baeb2`  
**Area**: Report Studio Export, Deterministic Citation Formatter, Municipal Jurisdiction Domain Ranking  

---

## 1. Goal & Context

ScoopScope provides an evidence-first, cryptographic approach to verifying claims: evidence is backed by verbatim, character-offset sliced passages from real web pages and presented in paired Cornell Notes. Through Milestone 4C, ScoopScope added deterministic jurisdiction classification and guardrails for the City of Los Angeles vs. Los Angeles County vs. California State.

In Milestone 4D, we upgrade the **Custom Report Studio & Works Cited** to enable seamless journalistic and academic workflows, while extending jurisdiction awareness to independent incorporated municipalities within Los Angeles County:
1. **One-Click Export Actions**: Add **Copy Markdown**, **Copy Plain Text**, and **Download `.md` Report** buttons to the synthesized report view.
2. **Deterministic Citation Style Selector**: Add style switching between **Standard Numbered**, **APA (7th ed)**, and **MLA (9th ed)** formats for the Works Cited evidence section. Citations are built deterministically from verified metadata (title, publisher/domain, defensible date, retrieval date, URL, and jurisdiction tag) with **zero fabrication** of absent dates or authors.
3. **Independent LA County Municipalities Classification & Research Ranking**: Expand `backend/app/jurisdiction.py` to recognize independent incorporated municipalities within LA County (e.g. Norwalk, Long Beach, Pasadena, Santa Monica, Glendale, Culver City, Beverly Hills, Torrance, Inglewood, Burbank, Pomona) as `{"code": "la_local_city", "label": "LA Local City Official"}` and rank matching municipal domains ahead in `backend/app/research.py` when confirmed inquiry scope identifies that municipality.

---

## 2. Detailed Technical Requirements

### A. One-Click Report Export (Frontend)
- In `frontend/index.html` and `frontend/app.js`, within `#reportOutput` / Custom Report Studio:
  - Add action buttons:
    - `btnCopyMarkdownReport`: Copies full markdown text of the report (including header, confirmed scope, synthesis vibe, claims, verbatim quotes, and Works Cited) to clipboard via `navigator.clipboard.writeText`. Displays brief visual feedback ("Copied Markdown!").
    - `btnCopyPlainTextReport`: Copies formatted plain-text representation (stripping markdown syntax like `#`, `**`, `[link](url)`) to clipboard. Displays brief visual feedback ("Copied Plain Text!").
    - `btnDownloadMarkdownReport`: Generates a downloadable `.md` file (e.g. `scoopscope-report-<timestamp>.md`) using a temporary object URL blob.
  - Export actions must work gracefully offline and fall back cleanly if `navigator.clipboard` is restricted.

### B. Deterministic Citation Style Selector
- In `frontend/index.html` and `frontend/app.js`:
  - Add a citation style selector control with options:
    - `standard`: **Standard Numbered** (`[1] Title — Domain (Date). URL [Jurisdiction]`)
    - `apa`: **APA (7th Edition)** format:
      - With author and date: `Author, A. A. (Year, Month Day). Title. Site Name. URL`
      - When date is absent: explicitly format publication date as `(n.d.)`.
      - When author is absent: use Site Name / Publisher or Page Title as lead entity.
      - Never fabricate names or dates.
    - `mla`: **MLA (9th Edition)** format:
      - `"Title of Article." Name of Site, defensible date or "n.d.", URL. Accessed retrieval date.`
      - Never fabricate dates or authors.
  - If a jurisdiction badge is present (`la_city`, `la_county`, `ca_state`, `la_regional`, `la_local_city`), append the verified jurisdiction label in brackets (e.g. `[LA City Official]`).
  - Switching the selector immediately updates the rendered Works Cited section in DOM and the active export text.
  - All rendering must strictly use `textContent` or `document.createTextNode()`. Zero raw `innerHTML` injection of source titles or URLs.

### C. Municipal Jurisdiction Expansion (`backend/app/jurisdiction.py`)
- Define `LA_LOCAL_CITY_DOMAINS` containing official domains of major independent incorporated cities in LA County:
  - `norwalk.org`, `norwalkca.gov`
  - `longbeach.gov`
  - `santamonica.gov`
  - `cityofpasadena.net`
  - `glendaleca.gov`
  - `culvercity.org`
  - `beverlyhills.org`
  - `torranceca.gov`
  - `inglewood.org`
  - `burbankca.gov`
  - `pomona.gov`
  - (and relevant subdomains via `_matches_domain_set`).
- Update `classify_source_jurisdiction(url)`:
  - If matches `LA_LOCAL_CITY_DOMAINS`, return `{"code": "la_local_city", "label": "LA Local City Official"}`.
- Update `backend/app/research.py`:
  - When candidate search results are evaluated, if the confirmed scope question specifies an LA local city (e.g. "Norwalk", "Long Beach", "Pasadena") or LA City / LA County, rank matching official municipal domains ahead of non-matching municipal domains.

---

## 3. High-Caution Guardrails & Out of Scope

1. **Frozen Modules (Do Not Modify)**:
   - `backend/app/safe_fetcher.py`: SSRF IP-pinning, 1 MB ceiling, redirect limits.
   - `backend/app/serper_provider.py`: Google Serper search provider protocol and budget limits.
   - Verbatim character-offset slicing in `backend/app/passage_extractor.py` (`extracted_text[start:end] == exact_passage`).
2. **Zero Fabrication**:
   - Never fabricate author names, publication dates, or verdicts in citation styles. If publication date is `None`, APA must render `(n.d.)` and MLA must omit publication date or render `n.d.` with retrieval date.
3. **Inert DOM Security**:
   - All citations, titles, snippets, and markdown exports rendered or manipulated in DOM must use `textContent` or `document.createTextNode()`.
4. **Git Hygiene**:
   - Stage files only by exact path: `git add <exact-path>`. Stop at the Push Gate.

---

## 4. How "Done" Is Tested (Test-Driven Discipline)

1. **Backend Tests**:
   - `backend/tests/test_la_jurisdiction.py`:
     - Test classification of all newly added local city domains (`norwalk.org`, `norwalkca.gov`, `longbeach.gov`, `cityofpasadena.net`, etc.) as `la_local_city`.
     - Test subdomain matching (e.g. `police.longbeach.gov`, `library.santamonica.gov`).
     - Test research scoring / ranking with municipal domain matching.
   - `backend/tests/test_report_and_extraction.py`:
     - Test citation formatting helpers if exposed via backend API, or test report synthesis schema integrity.
2. **Frontend Tests**:
   - `frontend/test_runner.html`:
     - Test citation style formatting functions (`formatStandardCitation`, `formatApaCitation`, `formatMlaCitation`) with:
       - Complete metadata (author, title, site, date, URL, jurisdiction).
       - Incomplete metadata (missing date -> `(n.d.)`, missing author, missing jurisdiction).
     - Test report export generation:
       - Markdown export contains title, claims, quotes, and chosen citation format.
       - Plain text export strips markdown symbols cleanly.
   - Run headless tests via `backend/tests/test_frontend_ordering.py`.
3. **Suite Integrity**:
   - All tests (256 existing + new tests) must pass offline with zero regressions.

---

## 5. Implementation Roadmap for Builder Agent

1. **Phase 1 (Tests First)**:
   - Add unit tests in `backend/tests/test_la_jurisdiction.py` for `la_local_city` domains and research prioritization.
   - Add unit tests in `frontend/test_runner.html` for citation formatting (Standard, APA, MLA) and text sanitization.
2. **Phase 2 (Jurisdiction Expansion)**:
   - Update `backend/app/jurisdiction.py` with `LA_LOCAL_CITY_DOMAINS` and `la_local_city` classification.
   - Wire municipal domain matching boost in `backend/app/research.py`.
3. **Phase 3 (Frontend Export & Citation Styles)**:
   - Implement citation formatters in `frontend/app.js`.
   - Add Citation Style Selector and Export buttons (Copy MD, Copy Text, Download MD) in `frontend/index.html` and `frontend/app.js`.
   - Wire event listeners and clipboard/download handlers.
4. **Phase 4 (Verification & Push Gate)**:
   - Run full pytest test suite offline.
   - Verify in browser / headless test runner.
   - Stage by exact path and commit locally. Stop at Push Gate.
