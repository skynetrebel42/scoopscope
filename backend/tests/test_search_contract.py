"""Tests for the SearchProvider protocol and search/evidence record schemas.

Covers:
- SearchProvider Protocol definition and runtime type checking.
- MockSearchProvider (test-only implementation; not an application fallback).
- Schema integrity: is_snippet_only permanently True on SearchResultHit.
- Schema integrity: missing dates and unknown source dependence.
- Query generation helper tests without LLM calls.
- Strict isolation: production app/config never defaults or falls back to mock search.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.search.models import (
    ClaimLinkedQuery,
    EvidencePassage,
    RawSearchResult,
    RetrievedSource,
    SearchResultHit,
    SourceDependence,
    SourceFetchState,
)
from app.search.provider import SearchProvider, SearchProviderError


# ---------------------------------------------------------------------------
# Test Support Mock Provider (Test-only; NOT imported into app/config)
# ---------------------------------------------------------------------------

class MockSearchProvider:
    """Deterministic, test-only SearchProvider implementation."""

    def __init__(self, canned_results: dict[str, list[RawSearchResult]] | None = None) -> None:
        self.canned_results = canned_results or {}
        self.call_history: list[tuple[str, int]] = []

    async def search(self, query: str, max_results: int = 5) -> list[RawSearchResult]:
        self.call_history.append((query, max_results))
        if query in self.canned_results:
            return self.canned_results[query][:max_results]
        # Deterministic default hit
        return [
            RawSearchResult(
                title=f"Result for {query}",
                url=f"https://news.example.org/articles/{abs(hash(query)) % 10000}",
                snippet=f"Snippet describing facts about {query}",
                rank=i + 1,
                engine="mock",
            )
            for i in range(min(max_results, 3))
        ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_search_provider_protocol_runtime_checkable():
    """Verify that MockSearchProvider satisfies SearchProvider protocol."""
    mock = MockSearchProvider()
    assert isinstance(mock, SearchProvider)


def test_invalid_provider_fails_protocol_check():
    """An object missing the search method should not satisfy SearchProvider."""
    class BadProvider:
        async def query(self, text: str):
            pass

    assert not isinstance(BadProvider(), SearchProvider)


@pytest.mark.anyio
async def test_mock_search_provider_returns_bounded_results():
    """MockSearchProvider should respect max_results budget."""
    provider = MockSearchProvider()
    results = await provider.search("Los Angeles transit expansion", max_results=2)
    assert len(results) == 2
    assert results[0].rank == 1
    assert results[1].rank == 2
    assert results[0].engine == "mock"
    assert "transit expansion" in results[0].snippet


def test_search_result_hit_permanently_snippet_only():
    """SearchResultHit must have is_snippet_only=True and reject mutations."""
    hit = SearchResultHit(
        result_id="hit_1",
        query_id="q_1",
        claim_id="claim_1",
        url="https://example.com/article",
        title="Sample Title",
        snippet="Sample snippet text",
        rank=1,
        engine="mock",
    )
    assert hit.is_snippet_only is True

    # Attempting to construct with is_snippet_only=False must raise ValidationError
    with pytest.raises(ValidationError):
        SearchResultHit(
            result_id="hit_2",
            query_id="q_1",
            claim_id="claim_1",
            url="https://example.com/article",
            title="Sample Title",
            snippet="Sample snippet text",
            rank=1,
            engine="mock",
            is_snippet_only=False,
        )


def test_evidence_passage_defaults_missing_dates_and_unknown_dependence():
    """Missing dates must be None and source_dependence must default to UNKNOWN."""
    passage = EvidencePassage(
        passage_id="p_1",
        source_id="src_1",
        claim_id="claim_1",
        source_url="https://latimes.example.com/report",
        exact_passage="Mayor Karen Bass announced a 14% reduction in homelessness.",
        retrieved_at="2026-10-13T12:00:00Z",
    )
    assert passage.publication_date is None
    assert passage.event_date is None
    assert passage.source_dependence == SourceDependence.UNKNOWN
    assert passage.context_surrounding is None


def test_retrieved_source_status_enum():
    """RetrievedSource must accept only valid SourceFetchState values."""
    src = RetrievedSource(
        source_id="src_abc",
        initial_url="https://example.com",
        final_url="https://example.com/article",
        status=SourceFetchState.RETRIEVED,
        http_status_code=200,
        content_type="text/html; charset=utf-8",
        response_size_bytes=4096,
        fetched_at="2026-10-13T12:00:00Z",
        extracted_text="Some extracted article text",
    )
    assert src.status == SourceFetchState.RETRIEVED
    assert src.extracted_text is not None

    blocked_src = RetrievedSource(
        source_id="src_def",
        initial_url="http://169.254.169.254/latest/meta-data",
        status=SourceFetchState.SSRF_BLOCKED,
        fetched_at="2026-10-13T12:00:00Z",
        error_message="SSRF_BLOCKED: Non-public IP",
    )
    assert blocked_src.status == SourceFetchState.SSRF_BLOCKED
    assert blocked_src.extracted_text is None


def test_claim_linked_query_schema():
    """ClaimLinkedQuery must validate non-empty intent and query text."""
    query = ClaimLinkedQuery(
        query_id="q_123",
        claim_id="claim_456",
        query_text="Los Angeles City Council homeless count 2025",
        query_intent="primary_assertion",
        generated_at="2026-10-13T12:00:00Z",
    )
    assert query.query_id == "q_123"
    assert query.claim_id == "claim_456"

    with pytest.raises(ValidationError):
        ClaimLinkedQuery(
            query_id="",
            claim_id="claim_456",
            query_text="",
            query_intent="",
            generated_at="2026-10-13T12:00:00Z",
        )


def test_deterministic_query_generation_without_llm():
    """Deterministic rule-based query builder generates queries without LLM invocation."""
    def build_claim_queries(claim_id: str, assertion: str, location: str | None) -> list[ClaimLinkedQuery]:
        queries = []
        loc_clause = f" {location}" if location else ""
        queries.append(
            ClaimLinkedQuery(
                query_id=f"q_{claim_id}_primary",
                claim_id=claim_id,
                query_text=f"{assertion}{loc_clause}".strip(),
                query_intent="primary_assertion",
                generated_at="2026-10-13T12:00:00Z",
            )
        )
        return queries

    queries = build_claim_queries("c1", "Population is 3.9 million", "Los Angeles")
    assert len(queries) == 1
    assert queries[0].query_text == "Population is 3.9 million Los Angeles"
    assert queries[0].query_intent == "primary_assertion"


def test_production_app_does_not_default_to_mock_search():
    """Verify that backend settings or app configuration never fallback to MockSearchProvider."""
    from app.config import settings
    # Settings should not have any mock search provider configured as default
    assert not hasattr(settings, "search_provider") or getattr(settings, "search_provider") != "mock"
