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
import uuid
from typing import TYPE_CHECKING

from google import genai
from google.genai import types as genai_types

from app.config import settings
from app.models import (
    ClaimExtractionResultLLM,
    ClaimType,
    ClarificationAnalysisLLM,
    ClarificationExchange,
    ClarificationResponse,
    ExtractedClaim,
    ExtractedClaimLLM,
    InvestigationPurpose,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
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

CLARIFICATION_SYSTEM_INSTRUCTION = """\
You are an expert inquiry clarification and scope analyst for ScoopScope.
Your task is to analyze a submitted statement or inquiry before external research occurs.

Core Objectives:
1. Identify Purpose:
   - "check_claim": The user wants to check whether a specific factual assertion or statement is supported or contradicted.
   - "understand_context": The user wants background, policy history, systemic context, or landscape.
   - "trace_origin": The user wants to find where a quote, rumor, or claim originated and how it spread.

2. Assess Clarity and Scope:
   - If the statement is clear, specific, and unambiguous (e.g. specific entity, clear timeframe, unambiguous assertion), set is_clear=true. Do NOT invent ambiguity solely to force clarifying questions.
   - If material ambiguities exist (e.g. underspecified timeframe, ambiguous entity, unstated definitions, compound assertions) where clarifying the scope fundamentally changes what evidence should be retrieved, set is_clear=false.
   - When is_clear=false:
     - Ask the single highest-value clarifying question.
     - Provide EXACTLY THREE distinct, mutually exclusive choices answering that question.
     - All three choices must address the SAME dimension (e.g. all 3 are timeframes, or all 3 are entities, or all 3 are interpretations). Never mix dates, goals, and entities in one incoherent menu.
     - Never invent missing particulars: keep unstated details unknown (e.g. if an unspecified substance in beef is mentioned, keep it unknown; do not guess hormones or antibiotics without evidence; preserve "Europe" without silently assuming "EU" without confirmation or a visible unresolved scope note).
     - Preserve temporal intent: a current-status inquiry must not silently become a historical investigation, or vice versa.
   - When 1 prior exchange is provided (Round 2 of 2), synthesize the choice and only ask a follow-up question if a critical ambiguity still remains; when 2 prior exchanges are provided, set is_clear=true and place any remaining ambiguities in material_uncertainties.

3. Split Compound Claims:
   - Break compound claims into linked checkable subclaims while preserving original wording and causal linkages.
   - Each subclaim must classify claim_type (factual, opinion, prediction, causal).
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

        Timeout & Retry Policy:
        - Timeout is strictly PER ATTEMPT (settings.llm_timeout_seconds, default 90s).
        - Retries are bounded by settings.llm_max_retries (default 2 retries, per AGENTS.md).
        - Total attempts = 1 initial attempt + settings.llm_max_retries (3 total attempts).
        - Max overall operation duration (worst-case):
            Attempts: 3 * 90s = 270s
            Backoff between attempts:
              Attempt 1 failure delay: min(12 + 6, 30) = 18s (or 2s if non-rate-limit)
              Attempt 2 failure delay: min(12 + 12, 30) = 24s (or 4s if non-rate-limit)
            Total backoff: up to 42s
            Maximum overall elapsed duration: up to 312 seconds (~5.2 minutes).

        Raises:
            CredentialsMissingError: API key not configured.
            GeminiAdapterError: Provider or validation failure after all attempts exhausted.
        """
        if self._client is None:
            raise CredentialsMissingError(
                "GEMINI_API_KEY is not set. See backend/.env.example for instructions."
            )

        total_attempts = settings.llm_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, total_attempts + 1):  # 1 initial attempt + max_retries
            try:
                return await self._call_model(text, attempt)
            except CredentialsMissingError:
                raise  # never retry credential errors
            except Exception as exc:
                last_error = exc
                is_retry = attempt > 1
                logger.warning(
                    "Gemini call %s %d/%d failed: %s",
                    f"retry {attempt - 1}" if is_retry else "initial attempt",
                    attempt,
                    total_attempts,
                    exc,
                )
                if attempt < total_attempts:
                    err_str = str(exc).lower()
                    if any(k in err_str for k in ("429", "resource_exhausted", "503", "unavailable")):
                        delay = min(12.0 + (attempt * 6.0), 30.0)
                    else:
                        delay = float(min(2 ** attempt, 8))
                    await asyncio.sleep(delay)

        raise GeminiAdapterError(
            f"Claim extraction failed after {total_attempts} attempts "
            f"(1 initial + {settings.llm_max_retries} retries): {last_error}"
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

    async def clarify_inquiry(
        self,
        text: str,
        source_url: str | None = None,
        round_index: int = 1,
        exchanges: list[ClarificationExchange] | None = None,
        explicit_broad: bool = False,
    ) -> ClarificationResponse:
        """Clarify and confirm inquiry intent, scope, and checkable claims (Milestone 3A).

        - Identifies user purpose: check_claim, understand_context, or trace_origin.
        - Identifies whether the statement is clear or has material ambiguities.
        - Bounds clarification to at most 2 rounds (max_rounds_reached=True after round 2).
        - For unclear inputs: provides a single question with exactly 3 coherent choices + free text.
        - Decomposes compound claims into checkable subclaims while preserving original wording.
        - Retains identical timeout and retry bounds as extraction.
        """
        if self._client is None:
            raise CredentialsMissingError(
                "GEMINI_API_KEY is not set. See backend/.env.example for instructions."
            )

        total_attempts = settings.llm_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, total_attempts + 1):
            try:
                return await self._call_clarification_model(
                    text=text,
                    source_url=source_url,
                    round_index=round_index,
                    exchanges=exchanges or [],
                    explicit_broad=explicit_broad,
                    attempt=attempt,
                )
            except CredentialsMissingError:
                raise
            except Exception as exc:
                last_error = exc
                is_retry = attempt > 1
                logger.warning(
                    "Gemini clarification call %s %d/%d failed: %s",
                    f"retry {attempt - 1}" if is_retry else "initial attempt",
                    attempt,
                    total_attempts,
                    exc,
                )
                if attempt < total_attempts:
                    err_str = str(exc).lower()
                    if any(k in err_str for k in ("429", "resource_exhausted", "503", "unavailable")):
                        delay = min(12.0 + (attempt * 6.0), 30.0)
                    else:
                        delay = float(min(2 ** attempt, 8))
                    await asyncio.sleep(delay)

        raise GeminiAdapterError(
            f"Inquiry clarification failed after {total_attempts} attempts "
            f"(1 initial + {settings.llm_max_retries} retries): {last_error}"
        ) from last_error

    async def _call_clarification_model(
        self,
        text: str,
        source_url: str | None,
        round_index: int,
        exchanges: list[ClarificationExchange],
        explicit_broad: bool,
        attempt: int,
    ) -> ClarificationResponse:
        """Single model call for clarification with structured schema validation."""
        assert self._client is not None

        config = genai_types.GenerateContentConfig(
            system_instruction=CLARIFICATION_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ClarificationAnalysisLLM,
            temperature=0.1,
        )

        prompt_lines = [
            f"Analyze the following user statement for inquiry clarification and scope confirmation:\n\n{text}"
        ]
        if source_url:
            prompt_lines.append(f"\nSource URL: {source_url}")
        prompt_lines.append(
            f"\nCurrent clarification round: {round_index} of 2"
            if round_index <= 2
            else "\nFinal confirmation round: 2 clarification rounds completed"
        )
        if exchanges:
            prompt_lines.append("\nPrior clarification exchanges:")
            for ex in exchanges:
                ans = ex.selected_choice or ex.free_text or "No answer provided"
                prompt_lines.append(f"- Round {ex.round_index} Question: {ex.question}\n  User Choice: {ans}")
        if explicit_broad:
            prompt_lines.append("\nUser requested: Proceed with broad inquiry across interpretations without further questions.")

        prompt_text = "\n".join(prompt_lines)

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.models.generate_content,
                    model=settings.gemini_model,
                    contents=prompt_text,
                    config=config,
                ),
                timeout=settings.llm_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise GeminiAdapterError(
                f"Gemini clarification call timed out after {settings.llm_timeout_seconds}s "
                f"(attempt {attempt})"
            ) from exc

        return self._validate_clarification_response(
            response=response,
            submitted_text=text,
            source_url=source_url,
            round_index=round_index,
            exchanges=exchanges,
            explicit_broad=explicit_broad,
        )

    def _validate_clarification_response(
        self,
        response: object,
        submitted_text: str,
        source_url: str | None,
        round_index: int,
        exchanges: list[ClarificationExchange] | None = None,
        explicit_broad: bool = False,
    ) -> ClarificationResponse:
        """Parse, validate, and normalize clarification output."""
        raw_text = getattr(response, "text", None)
        if not raw_text:
            raise GeminiAdapterError("Model returned empty clarification response.")

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiAdapterError(
                f"Model returned invalid JSON for clarification: {exc}"
            ) from exc

        try:
            analysis = ClarificationAnalysisLLM.model_validate(parsed)
        except Exception as exc:
            raise GeminiAdapterError(
                f"Model clarification output failed schema validation: {exc}"
            ) from exc

        # Determine round bounds & clarity
        # Enforce hard ceiling only when len(exchanges) >= 2, round_index >= 3, or explicit_broad=True
        num_exchanges = len(exchanges or [])
        max_rounds_reached = (round_index >= 3) or (num_exchanges >= 2) or explicit_broad

        if max_rounds_reached:
            clarification_needed = False
            is_clear = True
        else:
            clarification_needed = not analysis.is_clear
            is_clear = not clarification_needed

        question: str | None = None
        choices: list[str] | None = None

        if clarification_needed:
            if not analysis.clarification_question or not analysis.clarification_question.strip():
                raise GeminiAdapterError("Model requested clarification but omitted a clarifying question.")
            question = analysis.clarification_question.strip()

            raw_choices = analysis.clarification_choices or []
            cleaned: list[str] = []
            for c in raw_choices:
                if c and isinstance(c, str):
                    s = c.strip()
                    if s and s not in cleaned:
                        cleaned.append(s)

            if len(cleaned) < 3:
                raise GeminiAdapterError(
                    f"Model requested clarification but returned fewer than 3 valid choices ({len(cleaned)} found)."
                )
            choices = cleaned[:3]

        # Convert subclaims to ExtractedClaim with UUIDs (no fabricated fallback subclaim)
        subclaims: list[ExtractedClaim] = []
        if analysis.subclaims:
            for sc in analysis.subclaims:
                subclaims.append(
                    ExtractedClaim(
                        original_wording=sc.original_wording,
                        normalized_assertion=sc.normalized_assertion,
                        claim_type=sc.claim_type,
                        explicit_date=sc.explicit_date,
                        explicit_location=sc.explicit_location,
                        explicit_quantity=sc.explicit_quantity,
                        qualifications=sc.qualifications,
                    )
                )

        # Limitation note for context and origin inquiries
        limitation_note: str | None = None
        if analysis.purpose in (InvestigationPurpose.UNDERSTAND_CONTEXT, InvestigationPurpose.TRACE_ORIGIN):
            limitation_note = (
                "Dedicated context and origin tracing pipelines are planned for future milestones. "
                "You can investigate this as an editable factual research question below."
            )

        if clarification_needed:
            status_message = f"Clarification requested (round {round_index} of 2) · 3 options available"
        elif max_rounds_reached and (round_index >= 3 or num_exchanges >= 2):
            status_message = "Clarification completed (2 rounds reached) · Remaining uncertainties documented below"
        else:
            status_message = "Inquiry scope confirmed · Ready to select a checkable claim for research"

        return ClarificationResponse(
            submitted_text=submitted_text,
            source_url=source_url,
            purpose=analysis.purpose,
            is_clear=is_clear,
            clarification_needed=clarification_needed,
            round_index=round_index,
            max_rounds_reached=max_rounds_reached,
            question=question,
            choices=choices,
            interpreted_question=analysis.interpreted_question,
            material_uncertainties=analysis.material_uncertainties,
            subclaims=subclaims,
            limitation_note=limitation_note,
            status_message=status_message,
        )
