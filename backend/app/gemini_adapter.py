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
import urllib.parse
import uuid
from datetime import datetime, timezone
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
    EvidenceSynthesisLLM,
    ExtractedClaim,
    ExtractedClaimLLM,
    InvestigationPurpose,
    PassageRelevanceLLM,
    ReportRequest,
    ReportResponse,
    ReportVibe,
)
from app.search.models import EvidencePassage

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

4. Plain-Language & Clarification Context Integration:
   - Phrase clarification_choices, interpreted_question, and subclaims in plain, everyday journalistic and regulatory language (e.g., "food safety recalls, banned antibiotics, or contamination reports") rather than academic textbook jargon (like "veterinary drug residues") that skews search toward medical journals.
   - When prior clarification exchanges exist, ensure every extracted subclaim's normalized_assertion actively incorporates the user's selected clarification context.
"""

SYNTHESIS_SYSTEM_INSTRUCTION = """\
You are an objective evidence synthesis analyst for ScoopScope.
Your task is to analyze how safely retrieved verbatim source quotes address a user's inquiry or claim.

Rules and Guardrails:
1. STRICT GROUNDING: You MUST base your analysis strictly on the provided verbatim quotes.
   Never invent facts, external assertions, quotes, or citations.
2. NO TRUTH SCORES OR BARE VERDICTS: Do NOT assign numeric truth percentages or one-word verdicts (like "True" or "False").
3. INQUIRY SYNTHESIS:
   - Provide a concise, neutral 2-4 sentence synthesis explaining how the retrieved passages address the user's inquiry:
     what they support or clarify, what nuances they provide, and what critical aspects remain unverified or unknown.
   - If no relevant quotes were retrieved or quotes do not address the claim, state clearly that no verifying passages were found.
4. RELEVANCE EXPLANATIONS:
   - For each provided passage, write exactly one concise sentence explaining how that specific quote relates to the inquiry.
5. SUGGESTED NEXT QUERIES:
   - Provide 2 to 3 concrete, actionable follow-up questions or sharper search phrases (e.g. referencing official regulatory agencies, primary records, or specific unresolved scopes) to help the user explore further.
   - Output clean, direct search queries using key entities/locations and angles (e.g. "European Commission Food Safety audit Argentine beef 2024").
   - NEVER wrap queries in meta-instructions like "Check primary regulatory filings regarding..." or "Search official archives for updates on...".
   - NEVER include search operators like "site:" or "filetype:".
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

    async def synthesize_evidence(
        self,
        claim_text: str,
        passages: list[EvidencePassage],
        timeout_seconds: float = 30.0,
    ) -> EvidenceSynthesisLLM | None:
        """Generate grounded synthesis and per-quote relevance explanations using Gemini.

        Strict Guardrails:
        - Grounded 100% in provided verbatim passages.
        - Zero invented facts, quotes, or citations.
        - No numeric truth scores or bare True/False verdicts.
        - Bounded single call; returns None on failure or timeout so callers can fall back gracefully.
        """
        if self._client is None or not passages:
            return None

        config = genai_types.GenerateContentConfig(
            system_instruction=SYNTHESIS_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=EvidenceSynthesisLLM,
            temperature=0.1,
        )

        passage_blocks: list[str] = []
        for p in passages:
            passage_blocks.append(
                f"Passage ID: {p.passage_id}\n"
                f"Source URL: {p.source_url}\n"
                f"Publication Date: {p.publication_date or 'Unknown'}\n"
                f"Exact Verbatim Quote: \"{p.exact_passage}\"\n"
            )

        prompt = (
            f"Inquiry / Claim to evaluate:\n\"{claim_text}\"\n\n"
            f"Retrieved Verbatim Source Passages ({len(passages)} total):\n"
            + "\n---\n".join(passage_blocks)
            + "\n\nSynthesize how these verbatim quotes address the inquiry. Never invent quotes or verdicts."
        )

        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                    config=config,
                ),
                timeout=max(0.001, timeout_seconds),
            )
            if not response or not response.text:
                return None
            data = json.loads(response.text)
            return EvidenceSynthesisLLM.model_validate(data)
        except Exception as exc:
            logger.warning("Evidence synthesis call failed or timed out: %s", exc)
            return None

    async def generate_custom_report(
        self,
        req: ReportRequest,
        timeout_seconds: float = 30.0,
    ) -> ReportResponse:
        """Synthesize a custom report and evidence bank from user-selected quotes.

        Guarantees:
        - Strict grounding in user-selected quotes and source metadata without hallucination.
        - Robust fallback to deterministic offline report builder on LLM failure or timeout.
        """
        if self._client is None or not req.selected_passages:
            return build_deterministic_custom_report(req)

        # Build prompt for Gemini
        vibe = req.report_vibe or "objective_brief"
        passage_entries = []
        for idx, p in enumerate(req.selected_passages, start=1):
            domain = _extract_domain(p.source_url)
            passage_entries.append(
                f"[{idx}] Source: {domain} ({p.source_url})\n"
                f"    Date: {p.publication_date or 'Unknown'}\n"
                f"    Verbatim Quote: \"{p.exact_passage}\"\n"
                f"    Fit Note: {p.relevance_explanation or 'Contextual quote'}"
            )

        sections_requested = []
        if req.include_summary:
            sections_requested.append("Topic & Inquiry Synthesis")
        if req.include_evidence_bank:
            sections_requested.append("Structured Evidence Bank (Numbered [1], [2], verbatim quotes, fit, and links)")
        if req.include_open_questions:
            sections_requested.append("Unresolved Assumptions & Next Questions")
        if req.include_works_cited:
            sections_requested.append("Works Cited / Bibliography")

        prompt = (
            f"Inquiry Title: \"{req.inquiry_title}\"\n"
            f"Requested Vibe: {vibe}\n"
            f"Custom Focus: {req.custom_focus or 'None'}\n"
            f"Required Sections: {', '.join(sections_requested)}\n\n"
            f"Selected Verbatim Passages ({len(req.selected_passages)} total):\n"
            + "\n\n".join(passage_entries)
            + "\n\nSynthesize an authoritative, beautifully structured Markdown report following the specified vibe and sections. Never invent quotes or facts outside these passages."
        )

        sys_inst = (
            f"You are an expert research analyst and objective synthesist. "
            f"Generate an elegant Markdown report based strictly on the provided verbatim quotes. "
            f"Report Vibe: {vibe}. "
            f"Strict Rules: Never invent facts, statistics, or quotes not provided. "
            f"Preserve verbatim quotes exactly when citing evidence. Do not issue single-label true/false verdicts."
        )

        config = genai_types.GenerateContentConfig(
            system_instruction=sys_inst,
            temperature=0.2,
        )

        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                    config=config,
                ),
                timeout=max(0.001, timeout_seconds),
            )
            if response and response.text and len(response.text.strip()) > 100:
                clean_md = response.text.strip()
                # Remove markdown fences if model enclosed entire response in ```markdown ... ```
                if clean_md.startswith("```markdown"):
                    clean_md = clean_md[11:]
                elif clean_md.startswith("```"):
                    clean_md = clean_md[3:]
                if clean_md.endswith("```"):
                    clean_md = clean_md[:-3]
                clean_md = clean_md.strip()

                title_map = {
                    "objective_brief": f"Executive Briefing: {req.inquiry_title}",
                    "cornell_study": f"Cornell Study Guide: {req.inquiry_title}",
                    "fact_check": f"Fact-Check Breakdown: {req.inquiry_title}",
                    "deep_dive": f"Topic Deep-Dive: {req.inquiry_title}",
                }
                report_title = title_map.get(vibe, f"Research Report: {req.inquiry_title}")

                unique_sources = {p.source_url for p in req.selected_passages} | {s.url for s in req.sources}
                return ReportResponse(
                    report_title=report_title,
                    vibe_used=vibe,
                    markdown_content=clean_md,
                    selected_quote_count=len(req.selected_passages),
                    source_count=len(unique_sources),
                    is_fallback=False,
                )
        except Exception as exc:
            logger.warning("LLM report generation failed or timed out; falling back to deterministic builder: %s", exc)

        return build_deterministic_custom_report(req)


def _extract_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.hostname.replace("www.", "") if parsed.hostname else url
    except Exception:
        return url


def build_deterministic_custom_report(req: ReportRequest) -> ReportResponse:
    """Deterministic offline/fallback custom report and evidence bank generator."""
    vibe = req.report_vibe or "objective_brief"
    title_map = {
        "objective_brief": f"Executive Briefing: {req.inquiry_title}",
        "cornell_study": f"Cornell Study Guide: {req.inquiry_title}",
        "fact_check": f"Fact-Check Breakdown: {req.inquiry_title}",
        "deep_dive": f"Topic Deep-Dive: {req.inquiry_title}",
    }
    report_title = title_map.get(vibe, f"Research Report: {req.inquiry_title}")

    vibe_descriptions = {
        "objective_brief": "Objective executive synthesis grounded strictly in verified passages.",
        "cornell_study": "Structured cues, core takeaways, and topical synthesis for learning.",
        "fact_check": "Detailed evidence breakdown: supported facts, nuances, and unverified aspects.",
        "deep_dive": "Comprehensive contextual narrative connecting all selected source records.",
    }
    vibe_desc = vibe_descriptions.get(vibe, "Comprehensive factual evidence report.")

    from app.models import SourceMetadataItem

    unique_sources: dict[str, SourceMetadataItem] = {}
    for s in req.sources:
        unique_sources[s.url] = s
    for p in req.selected_passages:
        if p.source_url not in unique_sources:
            unique_sources[p.source_url] = SourceMetadataItem(
                url=p.source_url,
                domain=_extract_domain(p.source_url),
                title=p.source_title,
                publication_date=p.publication_date,
            )

    quote_count = len(req.selected_passages)
    source_count = len(unique_sources)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md_lines: list[str] = []
    md_lines.append(f"# {report_title}\n")
    md_lines.append(f"*{vibe_desc}*\n")
    md_lines.append(f"**Generated**: {now_iso} | **Evidence Base**: {quote_count} quotes across {source_count} sources\n")

    if req.custom_focus and req.custom_focus.strip():
        md_lines.append(f"> **Report Focus & Angle**: {req.custom_focus.strip()}\n")

    md_lines.append("---\n")

    # 1. Summary / Synthesis
    if req.include_summary:
        if vibe == "cornell_study":
            md_lines.append("## Cornell Study Guide & Synthesis\n")
            md_lines.append("### Key Cues & Inquiry Prompts")
            if req.selected_passages:
                for idx, p in enumerate(req.selected_passages, start=1):
                    fit = p.relevance_explanation or "Key substantive evidence."
                    domain = _extract_domain(p.source_url)
                    md_lines.append(f"- **Cue [{idx}]** ({domain}): {fit}")
            else:
                md_lines.append("- No specific passages selected.")
            md_lines.append("\n### Core Takeaways & Synthesis")
            if req.selected_passages:
                quotes_summary = " ".join([f'"{p.exact_passage[:120]}..."' for p in req.selected_passages[:3]])
                md_lines.append(f"The extracted evidence directly addresses '{req.inquiry_title}'. As documented across {source_count} independent sources, the record provides direct quotes: {quotes_summary}")
            else:
                md_lines.append("No verbatim evidence passages were included in this study guide.")
            md_lines.append("")
        elif vibe == "fact_check":
            md_lines.append("## Fact-Check Evidence Breakdown\n")
            md_lines.append("### Directly Supported by Retrieved Evidence")
            if req.selected_passages:
                for p in req.selected_passages:
                    fit = p.relevance_explanation or "Directly verified statement in source text."
                    md_lines.append(f"- **Documented**: {fit}")
            else:
                md_lines.append("- No selected evidence passages provided.")
            md_lines.append("\n### Contextual Nuances & Limitations")
            md_lines.append("- All findings reflect the exact wording of retrieved source documents at their time of publication.")
            md_lines.append("- Technical nuances and regulatory scopes must be evaluated in full primary context rather than isolated headlines.")
            md_lines.append("\n### What Remains Unverified or Unknown")
            md_lines.append("- Primary agency records or determinations outside the scope of the selected passages remain unverified.")
            md_lines.append("")
        elif vibe == "deep_dive":
            md_lines.append("## Topic Deep-Dive & Contextual Narrative\n")
            md_lines.append(f"Investigation into **{req.inquiry_title}** synthesizes evidence from {source_count} independent sources. The collected passages document how various parties, policies, and timelines interact.")
            if req.selected_passages:
                for idx, p in enumerate(req.selected_passages, start=1):
                    domain = _extract_domain(p.source_url)
                    fit = p.relevance_explanation or "Corroborating record excerpt."
                    pub = f" (Published: {p.publication_date})" if p.publication_date else ""
                    md_lines.append(f"\n#### [{idx}] Evidence from {domain}{pub}")
                    md_lines.append(f"> \"{p.exact_passage}\"\n")
                    md_lines.append(f"*{fit}*")
            md_lines.append("")
        else:  # objective_brief
            md_lines.append("## Executive Briefing & Synthesis\n")
            if req.selected_passages:
                md_lines.append(f"This briefing synthesizes {quote_count} verified verbatim passages addressing the inquiry: **{req.inquiry_title}**.\n")
                for p in req.selected_passages:
                    fit = p.relevance_explanation or "Substantive context statement."
                    domain = _extract_domain(p.source_url)
                    md_lines.append(f"- **{domain}**: {fit}")
                md_lines.append("\n**Analytical Note**: The excerpts provide inspectable factual anchors. Unaddressed elements remain subject to further investigation.")
            else:
                md_lines.append("No selected quotes were provided for this executive briefing.")
            md_lines.append("")

    # 2. Evidence Bank
    if req.include_evidence_bank:
        md_lines.append("## Structured Evidence Bank\n")
        if req.selected_passages:
            for idx, p in enumerate(req.selected_passages, start=1):
                domain = _extract_domain(p.source_url)
                pub = p.publication_date or "Unknown"
                fit = p.relevance_explanation or "Context quote addressing inquiry terms."
                md_lines.append(f"### Evidence [{idx}]: {domain}")
                md_lines.append(f"> \"{p.exact_passage}\"\n")
                md_lines.append(f"- **Fit & Significance**: {fit}")
                md_lines.append(f"- **Source URL**: [{domain}]({p.source_url})")
                md_lines.append(f"- **Publication Date**: {pub}\n")
        else:
            md_lines.append("*No evidence passages were selected for inclusion in the Evidence Bank.*\n")

    # 3. Open Questions
    if req.include_open_questions:
        md_lines.append("## Unresolved Assumptions & Next Questions\n")
        md_lines.append(f"1. **Primary Records**: What direct government agency filings, official council records, or primary court filings confirm the details of '{req.inquiry_title}'?")
        md_lines.append("2. **Temporal Validity**: Have there been more recent updates, policy reversals, or amendments since the dates published above?")
        md_lines.append("3. **Counter-Evidence**: Do credible opposing viewpoints or contradictory datasets exist that challenge these excerpts?\n")

    # 4. Works Cited
    if req.include_works_cited:
        md_lines.append("## Works Cited & Bibliography\n")
        if unique_sources:
            for idx, (url, s) in enumerate(unique_sources.items(), start=1):
                domain = s.domain or _extract_domain(url)
                title = s.title or domain
                pub = s.publication_date or "Date unknown"
                ret = s.retrieval_date or "Retrieved during investigation"
                md_lines.append(f"{idx}. **{domain}** — [{title}]({url})")
                md_lines.append(f"   - *Published*: {pub} | *Retrieval*: {ret}")
        else:
            md_lines.append("*No sources recorded.*")

    return ReportResponse(
        report_title=report_title,
        vibe_used=vibe,
        markdown_content="\n".join(md_lines),
        selected_quote_count=quote_count,
        source_count=source_count,
        is_fallback=True,
    )

