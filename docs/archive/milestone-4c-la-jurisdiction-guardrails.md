# Milestone 4C Spec: Los Angeles City vs. County Jurisdiction Guardrails

**Milestone**: 4C (Decision 010)  
**Status**: In Progress  
**Baseline**: Commit `c9e83b6`  
**Area**: Intake Clarification, Deterministic Domain Provenance, Cornell Notes UI  

---

## 1. Goal & Context

In civic and local journalism across Greater Los Angeles, one of the most frequent sources of misinformation and public confusion is the conflation of the **City of Los Angeles** (approx. 3.8 million residents, governed by the Mayor and City Council) and **Los Angeles County** (approx. 9.7 million residents across 88 incorporated cities and 120+ unincorporated areas, governed by the five-member Board of Supervisors).

Policies such as minimum wage increases, eviction moratoria, public health mandates, rent stabilization ordinances (RSO), policing oversight, and property taxes frequently differ fundamentally between City and County jurisdictions. When users ask questions like *"Did LA raise the minimum wage?"* or *"What is the LA eviction moratorium rule?"*, treating "LA" as a single entity produces confusing or contradictory research results.

**Milestone 4C Goal**:
1. **Intake Ambiguity Detection**: Automatically detect when an inquiry refers ambiguously to `"LA"` or `"Los Angeles"` without specifying City vs. County level governance.
2. **Clarification Disambiguation**: Surface clear disambiguation choices (**City of Los Angeles**, **Los Angeles County**, or **Both**) during `/api/clarify` intake before retrieval occurs.
3. **100% Deterministic Official Domain Provenance**: Map retrieved source URLs deterministically to verified government tier badges (`City of LA Official`, `LA County Official`, `LA Regional Agency`, `CA State Official`, `Government Official`). Never allow an LLM to guess or fabricate government jurisdiction credentials. Non-government domains (e.g. `latimes.com`, `laist.com`, `reddit.com`) receive zero official badges.
4. **Cornell Notes Provenance Badge**: Render verified jurisdiction badges inertly (`textContent` / `createTextNode`) next to domain and date provenance in the Cornell cue card column.

---

## 2. Hard Guardrails & Boundaries

1. **High Caution Files Protected**:
   - Do NOT touch `backend/app/retrieval/safe_fetcher.py`.
   - Do NOT touch `backend/app/search/serper_provider.py`.
   - Do NOT weaken exact character-offset substring verification (`extracted_text[start:end] == exact_passage`) in `passage_extractor.py`.
2. **Zero Hallucination / Zero LLM Guesswork for Provenance**:
   - Source jurisdiction classification is strictly mathematical and deterministic based on the source URL's parsed hostname.
   - LLMs are never consulted to assign or alter official jurisdiction badges.
3. **Inert DOM Rendering**:
   - All badge labels and attributes must be rendered via `textContent` or `document.createTextNode()`. Zero raw `innerHTML` injection.
4. **Out-of-Scope**:
   - Re-architecting the 88 individual other incorporated cities in LA County (e.g. Long Beach, Santa Monica, Pasadena) into distinct badges—these fall under standard state/county rules or future expansions.
   - Modifying Serper API query mechanics or budgets.

---

## 3. Deterministic Domain Rules

Domain classification matches parsed hostnames (case-insensitive, stripped of `www.` and port numbers):

| Jurisdiction Tier | Code (`jurisdiction_code`) | Badge Label (`jurisdiction_tag`) | Covered Domains & Subdomains |
|---|---|---|---|
| **City of Los Angeles** | `la_city` | `City of LA Official` | `lacity.gov`, `lacity.org`, `lapdonline.org`, `ladwp.com`, `lafd.org`, `lacontroller.org`, and all subdomains (e.g. `clerk.lacity.org`, `planning.lacity.org`, `housing.lacity.org`). |
| **Los Angeles County** | `la_county` | `LA County Official` | `lacounty.gov`, `lasd.org`, `lavote.gov`, and all subdomains (e.g. `bos.lacounty.gov`, `publichealth.lacounty.gov`, `dmh.lacounty.gov`, `dpw.lacounty.gov`, `assessor.lacounty.gov`, `da.lacounty.gov`). |
| **LA Regional / Joint Agencies** | `la_regional` | `LA Regional Agency` | `metro.net`, `lausd.net`, `lahsa.org`, `aqmd.gov`, `mwdh2o.com`, and all subdomains. *(Checked before `.gov` to ensure correct tiering).* |
| **CA State Government** | `ca_state` | `CA State Official` | `ca.gov` and all subdomains (e.g. `dir.ca.gov`, `edd.ca.gov`, `gov.ca.gov`, `courts.ca.gov`). |
| **US Federal / Other Government** | `us_gov` | `Government Official` | All other `*.gov` and `*.mil` hostnames (e.g. `dol.gov`, `census.gov`, `navy.mil`). |
| **Commercial / News / Third-Party** | *None* | *None* (`None`) | `latimes.com`, `laist.com`, `nytimes.com`, `reddit.com`, `example.com`, etc. *(Never assign official government badges to non-governmental sites).* |

---

## 4. LA Ambiguity Detection & Clarification Rules

Function: `detect_la_jurisdiction_ambiguity(text: str) -> bool`

- **Triggers Ambiguity (`True`)**:
  Input text references `LA`, `L.A.`, or `Los Angeles` as a standalone token or entity without already specifying explicit City or County level markers.
  - Examples:
    - *"Did LA raise the minimum wage?"* -> `True`
    - *"What is the LA eviction moratorium rule?"* -> `True`
    - *"LA law enforcement budget"* -> `True`
    - *"Los Angeles sales tax rate 2024"* -> `True`

- **Explicit or Unrelated (`False`)**:
  Input text already specifies City or County governance markers, or is completely unrelated to Los Angeles:
  - Explicit City markers: `"City of LA"`, `"City of Los Angeles"`, `"LA City"`, `"LAPD"`, `"LADWP"`, `"City Council"`, `"lacity"`.
  - Explicit County markers: `"LA County"`, `"Los Angeles County"`, `"LASD"`, `"Board of Supervisors"`, `"unincorporated"`, `"lacounty"`.
  - Unrelated queries: *"Did California raise the minimum wage?"*, *"Federal interest rate hike"*, *"Chicago zoning ordinance"*.

- **Clarification Behavior**:
  When `detect_la_jurisdiction_ambiguity(text)` is `True`, `/api/clarify` surfaces:
  - **Question**: *"Does this inquiry refer to the City of Los Angeles, Los Angeles County, or both?"*
  - **Choices**:
    1. `City of Los Angeles (City policy/ordinance)`
    2. `Los Angeles County (County/unincorporated)`
    3. `Both (City of LA and LA County)`
  - Confirmed scope incorporates the user's selected jurisdiction into downstream research and synthesis.

---

## 5. UI Presentation & Badges

1. **Cornell Cue Card**:
   - Inside `.cornell-cue-card .cue-source-meta`, when `jurisdiction_tag` is present on an evidence item, render:
     `<span class="jurisdiction-badge jurisdiction-{jurisdiction_code}">{jurisdiction_tag}</span>`
   - Styled with subtle, distinct hues in `frontend/style.css`.
2. **Inert Rendering**:
   - Created with `document.createElement("span")` and set via `textContent`.

---

## 6. Verification Criteria

1. 100% of domain classification test cases pass across City, County, Regional, State, Federal, and commercial domains.
2. Ambiguity detection correctly differentiates ambiguous LA questions from explicit or unrelated queries.
3. Full pytest offline test suite passes (all existing 164 tests + new jurisdiction tests).
4. Headless Chrome browser runner (`test_frontend_ordering.py`) passes with `.jurisdiction-badge` inert DOM assertion verified.
