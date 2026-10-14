"""FastAPI application for ScoopScope.

Serves the API and the static frontend.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.gemini_adapter import (
    CredentialsMissingError,
    GeminiAdapter,
    GeminiAdapterError,
)
from app.models import (
    ErrorResponse,
    ExtractionRequest,
    ExtractionResponse,
    ResearchRequest,
    ResearchResponse,
)
from app.research import ResearchOrchestrator
from app.search.provider import SearchProviderError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ScoopScope",
    description="Claim extraction and investigation API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev only
    allow_methods=["*"],
    allow_headers=["*"],
)

# Adapters created once at startup.
gemini = GeminiAdapter()
research_orchestrator = ResearchOrchestrator()

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "credentials_configured": settings.has_credentials,
        "search_credentials_configured": settings.has_search_credentials,
        "model": settings.gemini_model,
    }


@app.post(
    "/api/extract",
    response_model=ExtractionResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def extract_claims(req: ExtractionRequest):
    """Extract claims from submitted text.

    Returns structured claims with the original submission echoed back.
    The submission_id in the response lets the frontend prevent stale
    overwrites when rapid re-submissions occur.
    """
    text = req.text.strip()
    if not text:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="Empty input",
                detail="Please provide text containing at least one claim.",
                submitted_text=req.text,
                source_url=req.source_url,
            ).model_dump(),
        )

    if len(text) > settings.max_input_chars:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="Input too long",
                detail=f"Maximum {settings.max_input_chars:,} characters allowed.",
                submitted_text=req.text,
                source_url=req.source_url,
            ).model_dump(),
        )

    try:
        claims = await gemini.extract_claims(text)
    except CredentialsMissingError as exc:
        logger.error("Credentials missing: %s", exc)
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error="Credentials not configured",
                detail=str(exc),
                submitted_text=req.text,
                source_url=req.source_url,
            ).model_dump(),
        )
    except GeminiAdapterError as exc:
        logger.error("Gemini adapter error: %s", exc)
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error="Extraction failed",
                detail=str(exc),
                submitted_text=req.text,
                source_url=req.source_url,
            ).model_dump(),
        )
    except Exception as exc:
        logger.exception("Unexpected error during extraction")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal error",
                detail="An unexpected error occurred. Please try again.",
                submitted_text=req.text,
                source_url=req.source_url,
            ).model_dump(),
        )

    return ExtractionResponse(
        submitted_text=req.text,
        source_url=req.source_url,
        claims=claims,
    )


@app.post(
    "/api/research",
    response_model=ResearchResponse,
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def research_claim(req: ResearchRequest):
    """Gather search hits and safely retrieved passages for a single claim.

    CRITICAL: Does NOT generate verdicts or truth scores. Gathers inspectable
    candidate evidence only.
    """
    if not settings.has_search_credentials:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error="Search credentials not configured",
                detail="SERPER_API_KEY is not set in backend/.env. Please configure a valid Serper API key to search external sources.",
                submitted_text=req.claim_text,
                source_url=req.source_url,
            ).model_dump(),
        )

    try:
        result = await research_orchestrator.research_claim(req)
        return result
    except SearchProviderError as exc:
        logger.error("Search provider error: %s", exc)
        status_code = 503 if "not configured" in str(exc) else 502
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                error="Search provider failure",
                detail=str(exc),
                submitted_text=req.claim_text,
                source_url=req.source_url,
            ).model_dump(),
        )
    except Exception as exc:
        logger.exception("Unexpected error during research")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal research error",
                detail="An unexpected error occurred during research. Please try again.",
                submitted_text=req.claim_text,
                source_url=req.source_url,
            ).model_dump(),
        )


# ---------------------------------------------------------------------------
# Static frontend (must be mounted LAST so API routes take priority)
# ---------------------------------------------------------------------------

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
else:
    logger.warning("Frontend directory not found at %s", _FRONTEND_DIR)
