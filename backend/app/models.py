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


class InvestigationPurpose(str, enum.Enum):
    """Identified primary intent of the user's inquiry."""
    CHECK_CLAIM = "check_claim"
    UNDERSTAND_CONTEXT = "understand_context"
    TRACE_ORIGIN = "trace_origin"


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


class ClarificationAnalysisLLM(BaseModel):
    """Schema the LLM produces for inquiry clarification and scope analysis."""
    purpose: InvestigationPurpose = Field(
        description="Identified user goal: check_claim (verify factual assertions), "
                    "understand_context (broader background/landscape), or trace_origin (find source/first speaker)."
    )
    is_clear: bool = Field(
        description="True if input has a clear, unambiguous checkable claim without material ambiguities. "
                    "False if material ambiguities (scope, entity, timeframe, compound terms) require clarification."
    )
    interpreted_question: str = Field(
        description="Concise, clear, plain-language question representing what will be investigated. "
                    "If unclear, this should reflect the best interpretation so far."
    )
    material_uncertainties: list[str] = Field(
        default_factory=list,
        description="Material scope uncertainties or unstated assumptions (e.g. 'Specific substance not stated in input', "
                    "'Jurisdiction Europe vs EU unconfirmed', 'Timeframe not specified'). Never invent missing particulars."
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="The single highest-value clarifying question to resolve the most critical ambiguity. "
                    "Null if is_clear is true."
    )
    clarification_choices: Optional[list[str]] = Field(
        default=None,
        description="Exactly three distinct, mutually exclusive choices answering the clarification_question. "
                    "All three must address the same dimension (e.g. all 3 are timeframes, or all 3 are entities). "
                    "Null if is_clear is true."
    )
    subclaims: list[ExtractedClaimLLM] = Field(
        default_factory=list,
        description="Individual checkable claims or decomposed parts of compound claims. "
                    "Each subclaim preserves original wording and causal relationships without inventing particulars."
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
# Clarification API models (Milestone 3A)
# ---------------------------------------------------------------------------

class ClarificationExchange(BaseModel):
    """A single round of clarification question and user response."""
    round_index: int = Field(..., ge=1, le=2)
    question: str
    selected_choice: Optional[str] = None
    free_text: Optional[str] = None


class ClarificationRequest(BaseModel):
    """Request to clarify and confirm an inquiry before research."""
    text: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="The statement or question submitted by the user.",
    )
    source_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional URL where the statement was found.",
    )
    round_index: int = Field(default=1, ge=1, le=3)
    exchanges: list[ClarificationExchange] = Field(default_factory=list)
    explicit_broad: bool = Field(
        default=False,
        description="If True, the user elected to proceed with a broad inquiry after clarification rounds.",
    )


class ClarificationResponse(BaseModel):
    """Result of inquiry clarification and scope confirmation."""
    submission_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Unique ID for this submission (prevents stale overwrites).",
    )
    submitted_text: str
    source_url: Optional[str] = None
    purpose: InvestigationPurpose
    is_clear: bool
    clarification_needed: bool
    round_index: int
    max_rounds_reached: bool
    question: Optional[str] = None
    choices: Optional[list[str]] = None
    interpreted_question: str
    material_uncertainties: list[str] = Field(default_factory=list)
    subclaims: list[ExtractedClaim] = Field(default_factory=list)
    limitation_note: Optional[str] = None
    status_message: str
    clarified_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


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
