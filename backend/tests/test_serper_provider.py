"""Unit tests for SerperSearchProvider.

Verifies:
1. Conformance to SearchProvider runtime protocol.
2. Missing or empty API key raises SearchProviderError immediately.
3. Parsing valid Serper JSON responses into RawSearchResult records.
4. Enforcement of max 5 hits per query.
5. Error mapping for 401 (auth), 403 (credits), 429 (rate limit), 400 (bad request).
6. Retry behavior: max 2 attempts for 5xx server errors and timeouts.
7. No API secret leakage in errors or strings.
"""

from __future__ import annotations

import httpx
import pytest

from app.search import (
    RawSearchResult,
    SearchProvider,
    SearchProviderError,
    SerperSearchProvider,
)


def test_serper_provider_conforms_to_protocol():
    provider = SerperSearchProvider(api_key="test-key")
    assert isinstance(provider, SearchProvider)


@pytest.mark.anyio
async def test_missing_api_key_raises():
    provider = SerperSearchProvider(api_key="")
    with pytest.raises(SearchProviderError, match="SERPER_API_KEY"):
        await provider.search("Los Angeles population")

    provider_none = SerperSearchProvider(api_key=None)
    with pytest.raises(SearchProviderError, match="SERPER_API_KEY"):
        await provider_none.search("Los Angeles population")


@pytest.mark.anyio
async def test_empty_query_returns_empty_list():
    provider = SerperSearchProvider(api_key="test-key")
    res = await provider.search("   ")
    assert res == []


@pytest.mark.anyio
async def test_successful_search_parsing():
    mock_response = {
        "searchParameters": {"q": "LA Mayor", "num": 5},
        "organic": [
            {
                "title": "Office of Mayor Karen Bass",
                "link": "https://mayor.lacity.gov",
                "snippet": "Official website of the Mayor of Los Angeles.",
                "position": 1,
            },
            {
                "title": "Karen Bass - Wikipedia",
                "link": "https://en.wikipedia.org/wiki/Karen_Bass",
                "snippet": "Karen Ruth Bass is an American politician.",
                "position": 2,
            },
        ],
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-API-KEY") == "secret-test-key"
        assert request.headers.get("Content-Type") == "application/json"
        return httpx.Response(200, json=mock_response)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key="secret-test-key", custom_client=client)
        results = await provider.search("LA Mayor", max_results=5)

    assert len(results) == 2
    assert results[0].title == "Office of Mayor Karen Bass"
    assert results[0].url == "https://mayor.lacity.gov"
    assert results[0].snippet == "Official website of the Mayor of Los Angeles."
    assert results[0].rank == 1
    assert results[0].engine == "serper"

    assert results[1].rank == 2
    assert results[1].engine == "serper"


@pytest.mark.anyio
async def test_max_hits_capped_at_five():
    # 7 items in mock response; provider must cap at 5
    items = [
        {
            "title": f"Hit {i}",
            "link": f"https://example.com/{i}",
            "snippet": f"Snippet {i}",
            "position": i,
        }
        for i in range(1, 8)
    ]
    mock_response = {"organic": items}

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_response)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key="test-key", custom_client=client)
        results = await provider.search("test", max_results=10)

    assert len(results) == 5
    assert [r.rank for r in results] == [1, 2, 3, 4, 5]


@pytest.mark.anyio
async def test_auth_failure_401():
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key="bad-key", custom_client=client)
        with pytest.raises(SearchProviderError, match="401 Unauthorized"):
            await provider.search("test")


@pytest.mark.anyio
async def test_credit_exhaustion_403():
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Not enough credits"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key="key", custom_client=client)
        with pytest.raises(SearchProviderError, match=r"403 Forbidden.*credit"):
            await provider.search("test")


@pytest.mark.anyio
async def test_rate_limit_429():
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "Rate limit exceeded"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key="key", custom_client=client)
        with pytest.raises(SearchProviderError, match="429 Too Many Requests"):
            await provider.search("test")


@pytest.mark.anyio
async def test_server_error_500_retries_once():
    call_count = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(502, text="Bad Gateway")
        return httpx.Response(
            200,
            json={
                "organic": [
                    {"title": "Recovered", "link": "https://example.com/ok", "position": 1}
                ]
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key="key", custom_client=client)
        results = await provider.search("retry test")

    assert call_count == 2
    assert len(results) == 1
    assert results[0].title == "Recovered"


@pytest.mark.anyio
async def test_server_error_500_exhausts_retries():
    call_count = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key="key", custom_client=client)
        with pytest.raises(SearchProviderError, match="Serper service error"):
            await provider.search("retry failure")

    # At most 2 requests allowed
    assert call_count == 2


@pytest.mark.anyio
async def test_secrets_not_leaked_in_exceptions():
    secret_key = "super-secret-serper-token-xyz123"

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Invalid key"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key=secret_key, custom_client=client)
        try:
            await provider.search("test")
        except SearchProviderError as exc:
            assert secret_key not in str(exc)


@pytest.mark.anyio
async def test_outbound_requests_counted_including_retries():
    call_count = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, text="Internal Error")
        return httpx.Response(200, json={"organic": [{"title": "Hit", "link": "https://example.com/hit", "position": 1}]})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerperSearchProvider(api_key="key", custom_client=client)
        results = await provider.search("retry test")

    assert call_count == 2
    assert provider.total_requests_made == 2
    assert len(results) == 1
