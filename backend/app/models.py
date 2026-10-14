"""Pydantic models for ScoopScope claim extraction.

These models define the API request/response shapes and the structured
output schema sent to the LLM.  The LLM schema is intentionally kept
separate from the API response so validation failures don't leak raw
model output to the frontend.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from app.search.models import (
    ClaimLinkedQuery,
    EvidencePassage,
    RetrievedSource,
    SearchResultHit,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ClaimType(str, enum.Enum):
    """Classification of an extracted claim."""
    FACTUAL = "factual"
    OPINION = "opinion"
    PREDICTION = "prediction"
    CAUSAL = "causal"


# ---------------------------------------------------------------------------
# LLM structured-output schema  (sent to Gemini via response_schema)
# ---------------------------------------------------------------------------

class ExtractedClaimLLM(BaseModel):
    """Schema the LLM must produce for each claim."""
    original_wording: str = Field(
        description="Exact quote from the input containing this claim."
    )
    normalized_assertion: str = Field(
        description="Concise rephrasing as a standalone declarative sentence."
    )
    claim_type: ClaimType = Field(
        description="Whether this is a checkable factual assertion, an opinion, "
                    "a prediction, or a causal interpretation."
    )
    explicit_date: Optional[str] = Field(
        default=None,
        description="Date or time range explicitly stated in the claim, or null.",
    )
    explicit_location: Optional[str] = Field(
        default=None,
        description="Geographic location explicitly stated in the claim, or null.",
    )
    explicit_quantity: Optional[str] = Field(
        default=None,
        description="Numerical quantity explicitly stated in the claim, or null.",
    )
    qualifications: Optional[str] = Field(
        default=None,
        description="Hedges, conditions, or caveats the author attached to this "
                    "claim, or null if unconditional.",
    )


class ClaimExtractionResultLLM(BaseModel):
    """Top-level schema the LLM must return."""
    claims: list[ExtractedClaimLLM] = Field(
        description="List of individual claims extracted from the input text."
    )


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class ExtractionRequest(BaseModel):
    """Incoming request from the frontend."""
    text: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="The statement or passage to extract claims from.",
    )
    source_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional URL where the statement was found.",
    )


class ExtractedClaim(BaseModel):
    """A single claim in the API response (adds an id for frontend use)."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    original_wording: str
    normalized_assertion: str
    claim_type: ClaimType
    explicit_date: Optional[str] = None
    explicit_location: Optional[str] = None
    explicit_quantity: Optional[str] = None
    qualifications: Optional[str] = None


class ExtractionResponse(BaseModel):
    """Successful extraction result sent to the frontend."""
    submission_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Unique ID for this submission (used to prevent stale overwrites).",
    )
    submitted_text: str
    source_url: Optional[str] = None
    claims: list[ExtractedClaim]
    extracted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    status_message: str = "Claims extracted. Evidence research not yet performed."


class ErrorResponse(BaseModel):
    """Error payload."""
    error: str
    detail: Optional[str] = None
    submitted_text: Optional[str] = None
    source_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Research API models (Milestone 2C)
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    """Incoming request to gather candidate evidence for a single claim."""
    submission_id: str = Field(..., min_length=1, max_length=200)
    claim_id: str = Field(..., min_length=1, max_length=200)
    claim_text: str = Field(..., min_length=1, max_length=5000)
    claim_type: str = Field(default="factual", max_length=50)
    explicit_location: Optional[str] = Field(default=None, max_length=500)
    explicit_date: Optional[str] = Field(default=None, max_length=500)
    source_url: Optional[str] = Field(default=None, max_length=4096)


class ResearchResponse(BaseModel):
    """Result of search and retrieval for a single claim.

    CRITICAL: Does NOT contain verification verdicts or truth scores.
    Gathers unverified search snippets and safely retrieved source passages only.
    """
    submission_id: str
    claim_id: str
    queries_used: list[ClaimLinkedQuery]
    search_hits: list[SearchResultHit]
    retrieved_sources: list[RetrievedSource]
    candidate_passages: list[EvidencePassage]
    researched_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status_message: str
    completed_in_seconds: float
    search_failure_message: Optional[str] = None
