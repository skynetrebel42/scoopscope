"""Tests for the /api/extract endpoint and Gemini adapter validation.

Test categories:
  - API input validation (no credentials needed)
  - Malformed model output handling (fixture-based, no credentials needed)
  - Missing credentials behaviour (no credentials needed)
  - Successful extraction (fixture-based mock, no credentials needed)
  - Stale response prevention (fixture-based mock, no credentials needed)

All tests that would normally call the Gemini API use mocked/fixture
responses.  These are clearly marked as [FIXTURE-BASED] in their names.
No test silently falls back to fixtures — the mock is explicit.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.fixtures import (
    EMPTY_CLAIMS_LLM_RESPONSE,
    MALFORMED_RESPONSES,
    MULTI_CLAIM_LLM_RESPONSE,
    OVERSIZED_INPUT,
    SAMPLE_INPUT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_gemini_response(payload: dict | str) -> SimpleNamespace:
    """Create a mock object mimicking genai response with .text attribute."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(text=text)


# ---------------------------------------------------------------------------
# Input validation tests (no credentials, no mocks needed)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_empty_input_returns_400():
    """Empty text should be rejected with a clear error."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/extract", json={"text": "", "source_url": None})
    assert resp.status_code == 400 or resp.status_code == 422  # Pydantic min_length=1


@pytest.mark.anyio
async def test_whitespace_only_input_returns_400():
    """Whitespace-only text should be rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/extract", json={"text": "   \n  ", "source_url": None})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_oversized_input_returns_400():
    """Input exceeding max characters should be rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/extract", json={"text": OVERSIZED_INPUT})
    assert resp.status_code == 400 or resp.status_code == 422


@pytest.mark.anyio
async def test_missing_text_field_returns_422():
    """Missing 'text' field should return validation error."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/extract", json={"source_url": "https://example.com"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Credentials check
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_missing_credentials_returns_503():
    """When no API key is set, should return 503 with helpful message."""
    with patch("app.main.gemini._client", None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/extract", json={"text": SAMPLE_INPUT})
        assert resp.status_code == 503
        data = resp.json()
        assert "credentials" in data["error"].lower() or "GEMINI_API_KEY" in data.get("detail", "")


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_health_endpoint():
    """Health endpoint should respond with status and config info."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "model" in data
    assert "credentials_configured" in data


# ---------------------------------------------------------------------------
# Malformed model output tests [FIXTURE-BASED]
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_fixture_based_malformed_not_json():
    """[FIXTURE-BASED] Model returning non-JSON should produce a clear error."""
    mock_resp = _mock_gemini_response(MALFORMED_RESPONSES["not_json"])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.main.gemini._client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/extract", json={"text": SAMPLE_INPUT})
        assert resp.status_code == 503
        data = resp.json()
        assert "failed" in data["error"].lower() or "invalid" in data.get("detail", "").lower()
        # Input should be echoed back
        assert data.get("submitted_text") == SAMPLE_INPUT


@pytest.mark.anyio
async def test_fixture_based_malformed_missing_claims_key():
    """[FIXTURE-BASED] Missing 'claims' key should fail validation."""
    mock_resp = _mock_gemini_response(MALFORMED_RESPONSES["missing_claims_key"])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.main.gemini._client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/extract", json={"text": SAMPLE_INPUT})
        assert resp.status_code == 503


@pytest.mark.anyio
async def test_fixture_based_malformed_wrong_claim_type():
    """[FIXTURE-BASED] Invalid claim_type enum should fail validation."""
    mock_resp = _mock_gemini_response(MALFORMED_RESPONSES["wrong_claim_type"])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.main.gemini._client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/extract", json={"text": SAMPLE_INPUT})
        assert resp.status_code == 503


@pytest.mark.anyio
async def test_fixture_based_malformed_missing_required_field():
    """[FIXTURE-BASED] Missing required field should fail validation."""
    mock_resp = _mock_gemini_response(MALFORMED_RESPONSES["missing_required_field"])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.main.gemini._client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/extract", json={"text": SAMPLE_INPUT})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Successful extraction [FIXTURE-BASED]
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_fixture_based_successful_extraction():
    """[FIXTURE-BASED] Well-formed model output should produce a valid response."""
    mock_resp = _mock_gemini_response(MULTI_CLAIM_LLM_RESPONSE)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.main.gemini._client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/extract",
                json={"text": SAMPLE_INPUT, "source_url": "https://example.com"},
            )

    assert resp.status_code == 200
    data = resp.json()

    # Structure checks
    assert data["submitted_text"] == SAMPLE_INPUT
    assert data["source_url"] == "https://example.com"
    assert len(data["claims"]) == 3
    assert data["status_message"] == "Claims extracted. Evidence research not yet performed."
    assert "submission_id" in data
    assert "extracted_at" in data

    # Claim content checks
    factual_claims = [c for c in data["claims"] if c["claim_type"] == "factual"]
    assert len(factual_claims) == 1
    assert "Los Angeles" in factual_claims[0]["original_wording"]
    assert factual_claims[0]["explicit_location"] == "Los Angeles"
    assert factual_claims[0]["explicit_quantity"] is not None

    predictions = [c for c in data["claims"] if c["claim_type"] == "prediction"]
    assert len(predictions) == 1
    assert predictions[0]["explicit_date"] == "2030"

    opinions = [c for c in data["claims"] if c["claim_type"] == "opinion"]
    assert len(opinions) == 1


@pytest.mark.anyio
async def test_fixture_based_empty_claims():
    """[FIXTURE-BASED] Input with no claims should return empty list."""
    mock_resp = _mock_gemini_response(EMPTY_CLAIMS_LLM_RESPONSE)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("app.main.gemini._client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/extract", json={"text": "Hello world"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["claims"] == []
    assert data["submitted_text"] == "Hello world"


# ---------------------------------------------------------------------------
# Input preservation on error
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_input_preserved_on_provider_error():
    """[FIXTURE-BASED] When the provider errors, the user's input should be echoed back."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API unavailable")

    with patch("app.main.gemini._client", mock_client):
        # Lower retries for faster test
        with patch("app.gemini_adapter.settings") as mock_settings:
            mock_settings.has_credentials = True
            mock_settings.gemini_api_key = "fake"
            mock_settings.gemini_model = "gemini-2.0-flash"
            mock_settings.llm_timeout_seconds = 5
            mock_settings.llm_max_retries = 0
            mock_settings.max_input_chars = 10000

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/extract",
                    json={"text": SAMPLE_INPUT, "source_url": "https://test.com"},
                )

    assert resp.status_code == 503
    data = resp.json()
    assert data["submitted_text"] == SAMPLE_INPUT
    assert data["source_url"] == "https://test.com"


# ---------------------------------------------------------------------------
# Stale-response prevention (concurrent submissions)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_fixture_based_submission_ids_are_unique():
    """[FIXTURE-BASED] Each response should have a unique submission_id."""
    mock_resp = _mock_gemini_response(MULTI_CLAIM_LLM_RESPONSE)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    ids = []
    with patch("app.main.gemini._client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(3):
                resp = await client.post("/api/extract", json={"text": SAMPLE_INPUT})
                ids.append(resp.json()["submission_id"])

    # All IDs should be distinct
    assert len(set(ids)) == 3
