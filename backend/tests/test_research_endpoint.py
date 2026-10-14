"""Integration and unit tests for ResearchOrchestrator and /api/research endpoint.

Verifies:
1. Missing credentials behavior (returns 503 without mock fallback).
2. Query generation & execution budget (max 2 queries, max 5 hits per query).
3. Candidate page budget (max 3 distinct URLs, deduplication, includes source_url).
4. Provenance preservation and character offset invariants.
5. Partial failure handling (mix of retrieved, inaccessible, and SSRF blocked sources).
6. Snippet-only isolation (search hits never marked as examined evidence).
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app, research_orchestrator
from app.models import ResearchRequest
from app.research import ResearchOrchestrator, build_search_queries
from app.retrieval.passage_extractor import verify_passage_provenance
from app.retrieval.safe_fetcher import SafeFetcher
from app.search.models import (
    RawSearchResult,
    SourceDependence,
    SourceFetchState,
)
from app.search.provider import SearchProvider, SearchProviderError


class MockSearchBackend(SearchProvider):
    """Deterministic mock search provider for test suite."""

    def __init__(self, hits: list[RawSearchResult] | None = None) -> None:
        self.hits = hits if hits is not None else [
            RawSearchResult(
                title="Office of Mayor Karen Bass",
                url="https://example.com/mayor-bass",
                snippet="Mayor Karen Bass took office in December 2022.",
                rank=1,
                engine="mock",
            ),
            RawSearchResult(
                title="LA Housing Department",
                url="https://example.com/la-housing",
                snippet="Affordable housing initiatives across the City of Los Angeles.",
                rank=2,
                engine="mock",
            ),
            RawSearchResult(
                title="Duplicate URL Article",
                url="https://example.com/mayor-bass#section",  # should be deduped
                snippet="Additional coverage of Mayor Bass.",
                rank=3,
                engine="mock",
            ),
            RawSearchResult(
                title="LA County vs City",
                url="https://example.com/county-distinction",
                snippet="Distinguishing Los Angeles County governance from the City.",
                rank=4,
                engine="mock",
            ),
        ]
        self.call_count = 0
        self.queries_received: list[str] = []

    async def search(self, query: str, max_results: int = 5) -> list[RawSearchResult]:
        self.call_count += 1
        self.queries_received.append(query)
        return self.hits[:max_results]


def test_build_search_queries_bounds():
    queries = build_search_queries(
        claim_id="c1",
        claim_text="The City of Los Angeles approved a 13 billion budget for 2024",
        location="Los Angeles",
        date="2024",
    )
    assert len(queries) <= 2
    q1_text, q1_intent = queries[0]
    assert "13 billion budget" in q1_text
    assert q1_intent == "primary_assertion"


@pytest.mark.anyio
async def test_research_orchestrator_full_flow():
    mock_search = MockSearchBackend()

    # Create mock fetch transport returning controlled HTML for example.com
    html_content_1 = """
    <html><body>
    <h1>Executive Actions in Los Angeles</h1>
    <p>Mayor Karen Bass took office in December 2022, declaring an urgent state of emergency on homelessness.</p>
    <p>This action mobilized city resources and streamlined approvals for affordable housing units.</p>
    </body></html>
    """

    html_content_2 = """
    <html><body>
    <h1>Affordable Housing Production</h1>
    <p>Affordable housing initiatives across the City of Los Angeles accelerated under ED1.</p>
    <p>City council members reviewed progress quarterly.</p>
    </body></html>
    """

    async def mock_fetch_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "mayor-bass" in url_str:
            return httpx.Response(200, text=html_content_1, headers={"Content-Type": "text/html"})
        if "la-housing" in url_str:
            return httpx.Response(200, text=html_content_2, headers={"Content-Type": "text/html"})
        if "404" in url_str:
            return httpx.Response(404, text="Not Found", headers={"Content-Type": "text/html"})
        return httpx.Response(403, text="Forbidden", headers={"Content-Type": "text/html"})

    mock_transport = httpx.MockTransport(mock_fetch_handler)
    fetcher = SafeFetcher(
        dns_resolver=lambda host: ["93.184.216.34"],
        custom_transport=mock_transport,
    )

    orchestrator = ResearchOrchestrator(search_provider=mock_search, fetcher=fetcher)

    req = ResearchRequest(
        submission_id="sub_test_001",
        claim_id="claim_001",
        claim_text="Mayor Karen Bass took office in December 2022",
        claim_type="factual",
        explicit_location="Los Angeles",
        source_url="https://example.com/404-page",  # supplied source url that fails
    )

    response = await orchestrator.research_claim(req)

    # 1. Submission & claim linkage
    assert response.submission_id == "sub_test_001"
    assert response.claim_id == "claim_001"

    # 2. Search query limits
    assert len(response.queries_used) <= 2
    assert mock_search.call_count == 1  # 1 was enough since it returned hits

    # 3. Search hits isolation
    assert len(response.search_hits) > 0
    for hit in response.search_hits:
        assert hit.is_snippet_only is True
        assert hit.claim_id == "claim_001"
        assert hit.engine == "mock"

    # 4. Candidate URL budget (max 3 distinct pages fetched)
    assert len(response.retrieved_sources) <= 3
    # Check deduplication: mayor-bass#section must NOT cause duplicate fetch of mayor-bass
    initial_urls = [s.initial_url for s in response.retrieved_sources]
    assert len(initial_urls) == len(set(initial_urls))

    # 5. Partial failure recorded accurately
    statuses = [s.status for s in response.retrieved_sources]
    assert SourceFetchState.RETRIEVED in statuses
    assert SourceFetchState.INACCESSIBLE in statuses  # 404 page

    # 6. Candidate passages extracted and provenance verified
    assert len(response.candidate_passages) >= 1
    for passage in response.candidate_passages:
        # Find matching retrieved source
        matching_source = next(s for s in response.retrieved_sources if s.source_id == passage.source_id)
        assert matching_source.status == SourceFetchState.RETRIEVED
        assert verify_passage_provenance(passage, matching_source) is True

        # Invariant checks
        assert passage.publication_date is None
        assert passage.event_date is None
        assert passage.source_dependence == SourceDependence.UNKNOWN
        assert passage.claim_id == "claim_001"
        assert passage.exact_passage in matching_source.extracted_text


def test_missing_credentials_endpoint_returns_503(monkeypatch):
    client = TestClient(app)

    # Ensure search credentials are unset
    monkeypatch.setattr(
        "app.main.settings",
        settings.__class__(gemini_api_key="mock", serper_api_key=None),
    )

    res = client.post(
        "/api/research",
        json={
            "submission_id": "sub_1",
            "claim_id": "c1",
            "claim_text": "Karen Bass is mayor",
        },
    )

    assert res.status_code == 503
    data = res.json()
    assert "Search credentials not configured" in data["error"]
    assert "SERPER_API_KEY" in data["detail"]


# ---------------------------------------------------------------------------
# R2 Regressions: Orchestrator Cancellable Deadlines
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_research_orchestrator_enforces_cancellable_deadline(monkeypatch):
    """R2: Slow search provider must be cancelled and timed out within deadline."""
    import asyncio
    import time

    class SlowSearchBackend(SearchProvider):
        async def search(self, query: str, max_results: int = 5):
            await asyncio.sleep(0.3)
            return []

    from dataclasses import replace
    monkeypatch.setattr("app.research.settings", replace(settings, research_timeout_seconds=0.05))

    orchestrator = ResearchOrchestrator(
        search_provider=SlowSearchBackend(),
        fetcher=SafeFetcher(dns_resolver=lambda h: ["93.184.216.34"]),
    )

    req = ResearchRequest(
        submission_id="sub_timeout",
        claim_id="claim_timeout",
        claim_text="Assertion with slow search",
    )

    t0 = time.monotonic()
    response = await orchestrator.research_claim(req)
    elapsed = time.monotonic() - t0

    assert "TIMEOUT" in response.status_message
    assert elapsed < 0.2, f"Orchestrator timeout took too long: {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# R3 Regressions: Malformed Port Isolation
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_malformed_port_does_not_abort_research():
    """R3: Malformed port in candidate URL must be isolated without failing the request."""
    mock_search = MockSearchBackend([
        RawSearchResult(
            title="Valid Source",
            url="https://example.com/valid-article",
            snippet="Valid snippet content.",
            rank=1,
            engine="mock",
        ),
        RawSearchResult(
            title="Bad Port Source",
            url="https://example.com:bad/path",
            snippet="Bad port snippet.",
            rank=2,
            engine="mock",
        ),
        RawSearchResult(
            title="Overflow Port Source",
            url="https://example.com:99999/path",
            snippet="Overflow port snippet.",
            rank=3,
            engine="mock",
        ),
    ])

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<p>Valid article text here.</p>", headers={"Content-Type": "text/html"})

    mock_transport = httpx.MockTransport(mock_handler)
    fetcher = SafeFetcher(
        dns_resolver=lambda h: ["93.184.216.34"],
        custom_transport=mock_transport,
    )

    orchestrator = ResearchOrchestrator(search_provider=mock_search, fetcher=fetcher)

    req = ResearchRequest(
        submission_id="sub_r3",
        claim_id="claim_r3",
        claim_text="Valid article text here",
    )

    response = await orchestrator.research_claim(req)

    # Valid source was retrieved
    retrieved = [s for s in response.retrieved_sources if s.status == SourceFetchState.RETRIEVED]
    assert len(retrieved) >= 1
    assert "Valid article text here." in retrieved[0].extracted_text

    # Bad port sources were isolated as INACCESSIBLE
    inaccessible = [s for s in response.retrieved_sources if s.status == SourceFetchState.INACCESSIBLE]
    assert len(inaccessible) >= 1
    for s in inaccessible:
        assert "INVALID_URL" in (s.error_message or "") or "port" in (s.error_message or "").lower()


# ---------------------------------------------------------------------------
# F1 Regressions: Search Failure Preservation vs Normal Zero-Hit Search
# ---------------------------------------------------------------------------

class FailingSearchBackend(SearchProvider):
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.call_count = 0

    async def search(self, query: str, max_results: int = 5):
        self.call_count += 1
        raise self.exc


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error_exc,expected_status",
    [
        (SearchProviderError("Serper authentication failed (401 Unauthorized). The configured SERPER_API_KEY is invalid."), 502),
        (SearchProviderError("Serper request refused (403 Forbidden). Your Serper account may have exhausted its credit balance."), 502),
        (SearchProviderError("Serper rate limit exceeded (429 Too Many Requests). Please retry after a brief pause."), 502),
        (SearchProviderError("Serper search timed out after 2 attempts: HTTP 500 server error"), 502),
    ],
)
async def test_search_provider_failure_without_source_url_propagates_error(error_exc, expected_status, monkeypatch):
    """F1: When no source_url is supplied, search failure must propagate SearchProviderError and endpoint returns 502/503."""
    orchestrator = ResearchOrchestrator(
        search_provider=FailingSearchBackend(error_exc),
        fetcher=SafeFetcher(),
    )
    req = ResearchRequest(
        submission_id="sub_f1_fail",
        claim_id="claim_f1_fail",
        claim_text="The City approved a 13 billion budget",
        source_url=None,
    )

    # 1. Orchestrator must raise SearchProviderError directly
    with pytest.raises(SearchProviderError) as exc_info:
        await orchestrator.research_claim(req)
    assert str(error_exc) in str(exc_info.value) or "Serper" in str(exc_info.value)

    # 2. Endpoint handler must catch SearchProviderError and return structured 502/503 error
    from dataclasses import replace
    monkeypatch.setattr("app.main.settings", replace(settings, serper_api_key="mock_key"))
    monkeypatch.setattr("app.main.research_orchestrator", orchestrator)
    client = TestClient(app)
    response = client.post("/api/research", json=req.model_dump())
    assert response.status_code == expected_status
    body = response.json()
    assert body["error"] == "Search provider failure"
    assert "Serper" in body["detail"]
    # Assert no sensitive api keys leaked
    assert "mock_key" not in body["detail"]


@pytest.mark.anyio
async def test_search_provider_failure_with_source_url_preserves_partial_evidence():
    """F1: When source_url is supplied, search failure must be preserved in search_failure_message while extracting supplied source."""
    failing_search = FailingSearchBackend(SearchProviderError("Serper request refused (403 Forbidden). Quota exhausted."))

    html_content = """
    <html><body>
    <article>
        <p>The Los Angeles City Council approved a 13 billion budget for fiscal year 2024.</p>
    </article>
    </body></html>
    """

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html_content, headers={"Content-Type": "text/html"})

    fetcher = SafeFetcher(
        dns_resolver=lambda h: ["93.184.216.34"],
        custom_transport=httpx.MockTransport(mock_handler),
    )
    orchestrator = ResearchOrchestrator(search_provider=failing_search, fetcher=fetcher)

    req = ResearchRequest(
        submission_id="sub_f1_partial",
        claim_id="claim_f1_partial",
        claim_text="The City approved a 13 billion budget for 2024",
        source_url="https://example.com/budget-report",
    )

    response = await orchestrator.research_claim(req)

    # Search failure preserved
    assert response.search_failure_message is not None
    assert "403 Forbidden" in response.search_failure_message
    assert "Search provider unavailable" in response.status_message

    # Supplied source was still safely retrieved
    assert len(response.retrieved_sources) == 1
    assert response.retrieved_sources[0].status == SourceFetchState.RETRIEVED
    assert len(response.candidate_passages) >= 1
    assert "13 billion budget" in response.candidate_passages[0].exact_passage


@pytest.mark.anyio
async def test_legitimate_empty_search_distinguishable_from_provider_failure():
    """F1: Legitimate zero-hit search returns 200 with search_failure_message=None."""
    empty_search = MockSearchBackend(hits=[])
    orchestrator = ResearchOrchestrator(search_provider=empty_search, fetcher=SafeFetcher())

    req = ResearchRequest(
        submission_id="sub_f1_empty",
        claim_id="claim_f1_empty",
        claim_text="Obscure assertion with zero external index hits",
    )

    response = await orchestrator.research_claim(req)

    assert response.search_failure_message is None
    assert len(response.search_hits) == 0
    assert "Gathered 0 candidate search hit(s)" in response.status_message
    assert "Search provider unavailable" not in response.status_message


# ---------------------------------------------------------------------------
# F3 Regressions: Synchronous Extraction Deadline Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_synchronous_extraction_deadline_enforcement(monkeypatch):
    """F3: When synchronous cleaner/extractor exceeds budget, result must report TIMEOUT, not success."""
    import time
    from dataclasses import replace

    # Generate a roughly 670KB HTML document with many tags and paragraphs
    paragraph = "<p>This is paragraph text describing the city budget and mayor announcements in Los Angeles 2024.</p>\n"
    large_html = "<html><body><main>\n" + (paragraph * 7000) + "</main></body></html>"
    assert len(large_html) > 650000

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=large_html, headers={"Content-Type": "text/html"})

    mock_search = MockSearchBackend([
        RawSearchResult(
            title="Large Document Source",
            url="https://example.com/large-doc",
            snippet="Large document snippet.",
            rank=1,
            engine="mock",
        )
    ])

    fetcher = SafeFetcher(
        dns_resolver=lambda h: ["93.184.216.34"],
        custom_transport=httpx.MockTransport(mock_handler),
    )

    # Set extremely small research budget: 20ms (0.02s)
    monkeypatch.setattr("app.research.settings", replace(settings, research_timeout_seconds=0.02))

    orchestrator = ResearchOrchestrator(search_provider=mock_search, fetcher=fetcher)
    req = ResearchRequest(
        submission_id="sub_f3",
        claim_id="claim_f3",
        claim_text="City budget and mayor announcements in Los Angeles 2024",
    )

    t0 = time.monotonic()
    response = await orchestrator.research_claim(req)
    elapsed = time.monotonic() - t0

    # Must report TIMEOUT, never ordinary success
    assert "TIMEOUT" in response.status_message, f"Expected TIMEOUT in status_message, got: {response.status_message}"
    assert "Gathered 1 candidate search hit(s); fetched 1 of 1 candidate page(s) in" not in response.status_message

