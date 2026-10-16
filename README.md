# ScoopScope

A claim clarification, extraction, and evidence retrieval tool. Paste a statement or inquiry, clarify the investigation scope through bounded options, confirm the checkable inquiry question, and retrieve real external evidence with verbatim passages.

> **Current capability (Milestone 3A Complete):**
> 1. **Inquiry Intake & Clarification**: Identifies user purpose (`check_claim`, `understand_context`, `trace_origin`), bounds clarification to at most two rounds with 3 coherent choices + free text, splits compound claims without inventing particulars, and presents an editable confirmed scope question with material unresolved assumptions.
> 2. **Bounded Search & Safe Retrieval (Milestone 2C)**: Gathers external search snippets via Serper (max 2 outbound requests, 5 hits), safely fetches up to 3 candidate pages using SSRF-pinned sockets, and extracts inspectable verbatim passages with character offsets.
> 3. **Auditing & Zero Automated Verdicts**: Candidate passages and search snippets are surfaced strictly for human inspection. No automated truth scores or simulated verdicts are computed.

---

## Prerequisites

- **Python 3.11+** (required for asyncio.timeout; tested with 3.14)
- **Gemini API key** from [Google AI Studio](https://aistudio.google.dev/apikey)
- **Serper API key** from [Serper.dev](https://serper.dev) for live search

## Setup (Windows)

```powershell
cd c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\backend

# Create virtual environment
py -3 -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install dependencies (editable mode)
pip install -e .

# Create your local .env from the template
copy .env.example .env
# Then edit .env and add your GEMINI_API_KEY and SERPER_API_KEY
```

### Credential Setup

1. Edit `backend/.env` and set:
   ```env
   GEMINI_API_KEY=your-gemini-api-key
   SERPER_API_KEY=your-serper-api-key
   ```
2. **Never commit `.env`** — it is git-ignored.

## Running

```powershell
cd c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000> in your browser.

## Running Tests

```powershell
cd c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\backend
.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```

All 132 tests run completely offline without external credentials using explicit mocks and fixtures.

## API Endpoints

| Method | Path            | Description                                                        |
|--------|-----------------|--------------------------------------------------------------------|
| GET    | `/api/health`   | Health check and credential configuration status                   |
| POST   | `/api/clarify`  | Clarify inquiry intent, scope, and confirm checkable claims (3A)   |
| POST   | `/api/extract`  | Extract structured claims from submitted text (legacy baseline)    |
| POST   | `/api/research` | Gather search snippets and safely retrieved source passages (2C)   |

### POST /api/clarify

**Request:**
```json
{
  "text": "Europe bans American beef because of dangerous chemicals.",
  "source_url": null,
  "round_index": 1,
  "exchanges": []
}
```

**Response (200 - clarification needed):**
```json
{
  "submission_id": "9a8b7c...",
  "submitted_text": "Europe bans American beef because of dangerous chemicals.",
  "purpose": "check_claim",
  "is_clear": false,
  "clarification_needed": true,
  "round_index": 1,
  "max_rounds_reached": false,
  "question": "Which specific substance or regulatory restriction would you like to investigate?",
  "choices": [
    "Bovine growth hormones (1989 EU hormone ban)",
    "Chlorine and antimicrobial carcass washes",
    "General chemical food additives and veterinary drugs"
  ],
  "interpreted_question": "Did European countries ban American beef over specific chemical substances?",
  "material_uncertainties": [
    "Specific substance in beef was not stated by the author (chemicals unspecified)",
    "Jurisdiction Europe as a whole vs European Union statutory framework unconfirmed"
  ],
  "subclaims": [
    {
      "id": "e4f5a6...",
      "original_wording": "Europe bans American beef",
      "normalized_assertion": "European countries prohibit imports of American beef.",
      "claim_type": "factual"
    },
    {
      "id": "b1c2d3...",
      "original_wording": "because of dangerous chemicals",
      "normalized_assertion": "The beef import restriction is caused by the presence of dangerous chemical substances.",
      "claim_type": "causal"
    }
  ],
  "status_message": "Clarification requested (round 1 of 2) · 3 options available"
}
```
