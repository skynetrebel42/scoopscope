"""Gemini LLM adapter for claim extraction.

Responsibilities:
- Build the extraction prompt (no schema in prompt text; schema is enforced
  via response_schema).
- Call the google-genai SDK with structured output, timeout, and retries.
- Validate the response against Pydantic models.
- Surface clear errors for missing credentials, provider failures, and
  malformed output.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from google import genai
from google.genai import types as genai_types

from app.config import settings
from app.models import (
    ClaimExtractionResultLLM,
    ExtractedClaim,
    ExtractedClaimLLM,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTION = """\
You are a careful claim extractor.  Given a piece of text, identify every
individual claim it contains.

Rules:
- Preserve the author's original wording for each claim.
- Produce a concise normalized assertion as a standalone declarative sentence.
- Classify each claim: factual, opinion, prediction, or causal.
- Extract explicit dates, locations, and quantities only when the text states
  them.  Leave unknown details as null.
- Note any hedges, conditions, or qualifications the author attached.
- Do NOT invent information that is not in the input text.
- If the text contains no extractable claims, return an empty claims list.
"""


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class GeminiAdapterError(Exception):
    """Raised when the Gemini adapter encounters a non-recoverable error."""


class CredentialsMissingError(GeminiAdapterError):
    """Raised when no API key is configured."""


class GeminiAdapter:
    """Stateless adapter wrapping the google-genai client for claim extraction."""

    def __init__(self) -> None:
        if not settings.has_credentials:
            # Don't create the client; extraction calls will raise clearly.
            self._client = None
            return
        self._client = genai.Client(api_key=settings.gemini_api_key)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def extract_claims(self, text: str) -> list[ExtractedClaim]:
        """Extract structured claims from *text*.

        Raises:
            CredentialsMissingError: API key not configured.
            GeminiAdapterError: Provider or validation failure after retries.
        """
        if self._client is None:
            raise CredentialsMissingError(
                "GEMINI_API_KEY is not set. See backend/.env.example for instructions."
            )

        last_error: Exception | None = None
        for attempt in range(1, settings.llm_max_retries + 2):  # 1 initial + retries
            try:
                return await self._call_model(text, attempt)
            except CredentialsMissingError:
                raise  # never retry credential errors
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Gemini call attempt %d/%d failed: %s",
                    attempt,
                    settings.llm_max_retries + 1,
                    exc,
                )
                if attempt <= settings.llm_max_retries:
                    err_str = str(exc).lower()
                    if any(k in err_str for k in ("429", "resource_exhausted", "503", "unavailable")):
                        delay = min(12.0 + (attempt * 6.0), 30.0)
                    else:
                        delay = float(min(2 ** attempt, 8))
                    await asyncio.sleep(delay)

        raise GeminiAdapterError(
            f"Claim extraction failed after {settings.llm_max_retries + 1} attempts: "
            f"{last_error}"
        ) from last_error

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _call_model(self, text: str, attempt: int) -> list[ExtractedClaim]:
        """Single model call with timeout and validation."""
        assert self._client is not None

        config = genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ClaimExtractionResultLLM,
            temperature=0.1,
        )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.models.generate_content,
                    model=settings.gemini_model,
                    contents=f"Extract claims from the following text:\n\n{text}",
                    config=config,
                ),
                timeout=settings.llm_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise GeminiAdapterError(
                f"Gemini call timed out after {settings.llm_timeout_seconds}s "
                f"(attempt {attempt})"
            ) from exc

        return self._validate_response(response)

    def _validate_response(self, response: object) -> list[ExtractedClaim]:
        """Parse and validate the model's JSON output."""
        raw_text = getattr(response, "text", None)
        if not raw_text:
            raise GeminiAdapterError("Model returned empty response.")

        # Parse JSON
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiAdapterError(
                f"Model returned invalid JSON: {exc}"
            ) from exc

        # Validate against Pydantic schema
        try:
            result = ClaimExtractionResultLLM.model_validate(parsed)
        except Exception as exc:
            raise GeminiAdapterError(
                f"Model output failed schema validation: {exc}"
            ) from exc

        # Convert LLM schema → API schema (adds per-claim IDs)
        return [
            ExtractedClaim(
                original_wording=c.original_wording,
                normalized_assertion=c.normalized_assertion,
                claim_type=c.claim_type,
                explicit_date=c.explicit_date,
                explicit_location=c.explicit_location,
                explicit_quantity=c.explicit_quantity,
                qualifications=c.qualifications,
            )
            for c in result.claims
        ]
