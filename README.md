# ScoopScope

A claim extraction and investigation tool. Paste a statement, get structured
claims back — with original wording, classification, and extracted metadata.

> **Current capability:** Claim extraction only. Evidence research is not yet
> implemented.

---

## Prerequisites

- **Python 3.10+** (tested with 3.14)
- **Gemini API key** from [Google AI Studio](https://aistudio.google.dev/apikey)
  (free tier available — see notes below)

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
# Then edit .env and add your GEMINI_API_KEY
```

### Credential Setup

1. Go to <https://aistudio.google.dev/apikey>
2. Create an API key (sign in with a Google account)
3. Edit `backend/.env` and set:
   ```
   GEMINI_API_KEY=your-actual-key-here
   ```
4. **Never commit `.env`** — it is git-ignored.

### Gemini Free Tier Notes

- The free tier allows **$0 usage** of Flash-tier models (e.g. `gemini-flash-lite-latest`, `gemini-3.8-flash`).
- Rate limits depend on the model and account tier (typically 5–15 RPM for free-tier Flash models, with daily request caps) — check your Google AI Studio dashboard for current limits.
- Free-tier data **may be used by Google** to improve models.
- This is distinct from Gemini access in coding assistants — you need an
  application API key from AI Studio, not a coding-tool subscription.

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

All tests run without credentials (they use explicit mocks/fixtures).

## Project Structure

```
ScoopScope/
├── AGENTS.md              # Project rules and evidence policy
├── GEMINI.md              # Pointer to AGENTS.md
├── STATUS.md              # Current state and next task
├── README.md              # This file
├── .gitignore
├── backend/
│   ├── pyproject.toml     # Dependencies and build config
│   ├── .env.example       # Credential template
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py      # Settings from .env
│   │   ├── models.py      # Pydantic request/response/LLM schemas
│   │   ├── gemini_adapter.py  # Gemini API client with retries
│   │   └── main.py        # FastAPI application
│   └── tests/
│       ├── __init__.py
│       ├── fixtures.py    # Test-only data (never used in production)
│       └── test_extraction.py
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## API Endpoints

| Method | Path           | Description                        |
|--------|----------------|------------------------------------|
| GET    | `/api/health`  | Health check, credential status    |
| POST   | `/api/extract` | Extract claims from submitted text |

### POST /api/extract

**Request:**
```json
{
  "text": "Los Angeles has about 4 million people.",
  "source_url": "https://example.com"
}
```

**Response (200):**
```json
{
  "submission_id": "abc123...",
  "submitted_text": "Los Angeles has about 4 million people.",
  "source_url": "https://example.com",
  "claims": [
    {
      "id": "a1b2c3d4e5f6",
      "original_wording": "Los Angeles has about 4 million people",
      "normalized_assertion": "The population of Los Angeles is approximately 4 million.",
      "claim_type": "factual",
      "explicit_date": null,
      "explicit_location": "Los Angeles",
      "explicit_quantity": "about 4 million people",
      "qualifications": "approximate (\"about\")"
    }
  ],
  "extracted_at": "2026-10-13T08:00:00Z",
  "status_message": "Claims extracted. Evidence research not yet performed."
}
```
