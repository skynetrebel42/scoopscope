"""Data models for search and evidence records.

Per docs/evidence-search-design.md:
Four strictly separated record layers:
1. ClaimLinkedQuery
2. SearchResultHit (always is_snippet_only=True; NEVER verified evidence)
3. RetrievedSource (HTTP fetch audit record with SourceFetchState)
4. EvidencePassage (verbatim quote from RETRIEVED source with SourceDependence)
"""

from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class RawSearchResult(BaseModel):
    """Raw result returned by a search engine implementation."""
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    snippet: str = Field(default="")
    rank: int = Field(ge=1, description="1-based search result rank")
    engine: str = Field(min_length=1, description="Search engine identifier, e.g. 'serper', 'mock'")


class ClaimLinkedQuery(BaseModel):
    """A search query generated to investigate a specific claim."""
    model_config = ConfigDict(frozen=True)

    query_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    query_intent: str = Field(min_length=1, description="e.g. 'primary_assertion', 'date_check', 'counter_evidence'")
    generated_at: str = Field(description="ISO 8601 UTC timestamp")


class SearchResultHit(BaseModel):
    """A search result hit linked to a query and claim.
    
    CRITICAL: is_snippet_only is permanently True.
    Search hits NEVER count as verified evidence merely because they contain a URL or snippet.
    """
    model_config = ConfigDict(frozen=True)

    result_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    title: str = Field(default="")
    snippet: str = Field(default="")
    rank: int = Field(ge=1)
    engine: str = Field(min_length=1)
    is_snippet_only: Literal[True] = Field(default=True, frozen=True)
    jurisdiction_tag: str | None = Field(default=None, description="Deterministic official jurisdiction label")
    jurisdiction_code: str | None = Field(default=None, description="Deterministic jurisdiction code")


class SourceFetchState(str, Enum):
    """Explicit lifecycle states for source retrieval."""
    RETRIEVED = "retrieved"                  # Safely fetched, verified text/html, body extracted
    INACCESSIBLE = "inaccessible"            # Network error, HTTP 4xx/5xx, timeout, robots.txt, paywall
    EXTRACTION_FAILED = "extraction_failed"  # HTTP 200, but content was unparseable or oversized
    SSRF_BLOCKED = "ssrf_blocked"            # Blocked by safe-fetch SSRF gate or private IP


class RetrievedSource(BaseModel):
    """Full HTTP fetch audit record.
    
    Documents whether the destination was accessible and safely fetched.
    Downloaded HTML or text is untrusted source data, never instructions.
    """
    source_id: str = Field(min_length=1)
    initial_url: str = Field(min_length=1)
    final_url: str | None = None
    redirect_count: int = Field(default=0, ge=0)
    resolved_ip: str | None = None
    status: SourceFetchState
    http_status_code: int | None = None
    content_type: str | None = None
    response_size_bytes: int = Field(default=0, ge=0)
    fetched_at: str = Field(description="ISO 8601 UTC timestamp")
    error_message: str | None = None
    extracted_text: str | None = None
    raw_text: str | None = Field(default=None, description="Bounded raw decoded source representation before cleaning (up to 1MB)")
    extraction_note: str | None = Field(default=None, description="Audit notes describing normalization and cleaning applied")
    jurisdiction_tag: str | None = Field(default=None, description="Deterministic official jurisdiction label")
    jurisdiction_code: str | None = Field(default=None, description="Deterministic jurisdiction code")


class SourceDependence(str, Enum):
    """Classification of source relationship to prevent circular reporting."""
    PRIMARY = "primary"                      # First-hand reporting, official document, data release
    SECONDARY_INDEPENDENT = "secondary_indep"# Independent reporting citing own sources
    REPUBLICATION_WIRE = "republication_wire"# Syndicated AP/Reuters copy or verbatim repost
    UNKNOWN = "unknown"                      # Lineage cannot be conclusively determined


class EvidencePassage(BaseModel):
    """An exact, verifiable excerpt extracted directly from a RETRIEVED source.
    
    Invariant: Must reference a RetrievedSource with status == RETRIEVED.
    """
    model_config = ConfigDict(frozen=True)

    passage_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    exact_passage: str = Field(min_length=1)
    context_surrounding: str | None = None
    publication_date: str | None = Field(default=None, description="ISO 8601 or None if unknown")
    updated_date: str | None = Field(default=None, description="ISO 8601 or None if unknown")
    date_provenance: str | None = Field(default=None, description="Source of extracted date, e.g. json-ld, meta, byline, time-tag")
    event_date: str | None = Field(default=None, description="ISO 8601 or None if unknown")
    source_dependence: SourceDependence = Field(default=SourceDependence.UNKNOWN)
    retrieved_at: str = Field(description="ISO 8601 UTC timestamp")
    start_offset: int | None = Field(default=None, ge=0, description="Start character offset in extracted_text")
    end_offset: int | None = Field(default=None, ge=0, description="End character offset in extracted_text")
    relevance_note: str | None = Field(default=None, description="Relevance diagnostic note (e.g. keyword match)")
    relevance_explanation: str | None = Field(default=None, description="Concise 1-sentence explanation of how this quote relates to the inquiry")
    jurisdiction_tag: str | None = Field(default=None, description="Deterministic official jurisdiction label")
    jurisdiction_code: str | None = Field(default=None, description="Deterministic jurisdiction code")

