"""Research orchestrator executing bounded search and safe retrieval for a single claim.

Per AGENTS.md, docs/evidence-search-design.md, and Milestone 2C:
- Strictly bounds execution:
  * 1 selected claim per research action.
  * At most 2 search queries per claim (each returning at most 5 hits).
  * At most 3 distinct candidate pages fetched (counting supplied source URL).
  * 90-second overall deadline covering search, retrieval, and passage extraction.
  * Preserves SafeFetcher's per-page (30s), redirect (3), MIME, and size (1MB) bounds.
- Distinguishes unexamined search snippets from safely retrieved page text.
- Candidate passages are exact spans with programmatic provenance verification.
- Does NOT produce verdicts, truth scores, or supported/contradicted assessments.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.gemini_adapter import GeminiAdapter
from app.models import ResearchRequest, ResearchResponse
from app.retrieval.passage_extractor import (
    clean_html_to_text,
    clean_text_content,
    deduplicate_urls,
    extract_candidate_passages,
    extract_keywords_from_claim,
    stem_word,
    verify_passage_provenance,
)
from app.retrieval.safe_fetcher import SafeFetcher, validate_url_syntax
from app.search.models import (
    ClaimLinkedQuery,
    EvidencePassage,
    RetrievedSource,
    SearchResultHit,
    SourceFetchState,
)
from app.search.provider import SearchProvider, SearchProviderError
from app.search.serper_provider import SerperSearchProvider

logger = logging.getLogger(__name__)

SOCIAL_SHELL_DOMAINS = {
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "threads.net",
}


def is_social_shell_url(url: str) -> bool:
    """Check if URL belongs to a JS-only social/forum shell domain."""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        for dom in SOCIAL_SHELL_DOMAINS:
            if host == dom or host.endswith("." + dom):
                return True
        return False
    except Exception:
        return False


def build_search_queries(
    claim_id: str,
    claim_text: str,
    location: str | None = None,
    date: str | None = None,
) -> list[tuple[str, str]]:
    """Build up to 2 deterministic, bounded query strings (query_text, query_intent)."""
    # Clean claim text of excessive whitespace or outer quotes
    cleaned = re.sub(r"\s+", " ", claim_text.strip().strip('"\''))
    # Strip leading conversational question words and trailing question marks
    cleaned_query = re.sub(r"\?+$", "", cleaned).strip()
    cleaned_query = re.sub(
        r"^(is|did|was|were|are|does|do|can|could|will|would|has|have|had)\s+",
        "",
        cleaned_query,
        flags=re.IGNORECASE,
    ).strip()

    loc = location.strip() if location else ""
    dt = date.strip() if date else ""

    # Primary assertion query
    parts_primary = [cleaned_query]
    if loc and loc.lower() not in cleaned_query.lower():
        parts_primary.append(loc)
    if dt and dt.lower() not in cleaned_query.lower():
        parts_primary.append(dt)
    q1 = " ".join(parts_primary)[:140].strip()
    if "-filetype:pdf" not in q1.lower():
        q1 = f"{q1} -filetype:pdf"

    # Broader keyword query (secondary fallback if primary returns 0 hits)
    keywords = extract_keywords_from_claim(cleaned_query, loc, dt)
    q2 = " ".join(keywords[:6])[:110].strip()
    if q2 and "-filetype:pdf" not in q2.lower():
        q2 = f"{q2} -filetype:pdf"

    queries = [(q1, "primary_assertion")]
    if q2 and q2.lower() != q1.lower():
        queries.append((q2, "broad_keywords"))

    return queries[:2]


TRAILING_STRIP_WORDS = {
    "due", "to", "because", "of", "in", "by", "for", "with", "and", "or",
    "as", "at", "from", "on", "into", "about", "that", "which", "over", "under"
}


def generate_fallback_next_queries(claim_text: str, location: str | None = None) -> list[str]:
    """Generate clean, plain-language search queries for exploring further without meta-wrapping or operators."""
    cleaned = re.sub(r"\?+$", "", claim_text.strip().strip('"\'')).strip()
    cleaned = re.sub(
        r"^(is|did|was|were|are|does|do|can|could|will|would|has|have|had)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", cleaned)
    core_words = words[:6] if words else re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", cleaned[:45])

    # Strip trailing prepositions / conjunctions from core words
    while core_words and core_words[-1].lower() in TRAILING_STRIP_WORDS:
        core_words.pop()

    core = " ".join(core_words)

    # Deduplicate location words already present in the subject phrase
    if location and location.strip():
        loc_tokens = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", location)
        core_stems = {stem_word(w) for w in core_words if stem_word(w)}
        new_loc_tokens = [
            t for t in loc_tokens
            if t.lower() not in core.lower() and stem_word(t) not in core_stems
        ]
        if new_loc_tokens:
            core = f"{core} {' '.join(new_loc_tokens)}"

    # Re-strip any trailing prepositions / conjunctions
    final_words = core.split()
    while final_words and final_words[-1].lower() in TRAILING_STRIP_WORDS:
        final_words.pop()
    core = " ".join(final_words)

    lower_text = claim_text.lower()
    if any(k in lower_text for k in ("ban", "banned", "recall", "suspend", "restriction", "residue", "safety", "inspect")):
        return [
            f"{core} official recall or import ban policy",
            f"{core} inspection report or fact check",
            f"{core} government agency official statement",
        ]
    elif any(k in lower_text for k in ("budget", "fund", "money", "dollar", "cost", "spend")):
        return [
            f"{core} official budget allocation report",
            f"{core} audit report or fiscal analysis",
            f"{core} council or agency records",
        ]
    else:
        return [
            f"{core} official inspection report or fact check",
            f"{core} regulatory policy or official records",
            f"{core} primary source statement",
        ]


def _sanitize_error_message(msg: str) -> str:
    """Sanitize error messages to avoid leaking sensitive credentials or internal paths."""
    if not msg:
        return "Search provider error"
    if settings.serper_api_key and settings.serper_api_key in msg:
        msg = msg.replace(settings.serper_api_key, "[REDACTED_API_KEY]")
    msg = re.sub(r"(api[-_]?key|key|token)[=:\s]+[A-Za-z0-9_\-]{8,}", r"\1=[REDACTED]", msg, flags=re.IGNORECASE)
    return msg


class ResearchOrchestrator:
    """Orchestrates search hit gathering and safe page retrieval for a single claim."""

    def __init__(
        self,
        search_provider: SearchProvider | None = None,
        fetcher: SafeFetcher | None = None,
        gemini_adapter: GeminiAdapter | None = None,
    ) -> None:
        self._search_provider = search_provider
        self._fetcher = fetcher
        self._gemini_adapter = gemini_adapter

    def _get_search_provider(self) -> SearchProvider:
        if self._search_provider is not None:
            return self._search_provider
        if not settings.has_search_credentials:
            raise SearchProviderError(
                "Search credentials are not configured. Please add SERPER_API_KEY to your backend/.env file."
            )
        return SerperSearchProvider(api_key=settings.serper_api_key)

    def _get_fetcher(self, timeout_seconds: float) -> SafeFetcher:
        if self._fetcher is not None:
            return self._fetcher
        return SafeFetcher(overall_timeout_seconds=timeout_seconds)

    def _get_gemini_adapter(self) -> GeminiAdapter | None:
        return self._gemini_adapter

    async def research_claim(self, req: ResearchRequest) -> ResearchResponse:
        """Execute bounded search, safe retrieval, and passage extraction for a single claim.

        Args:
            req: ResearchRequest identifying the claim, submission, and optional source URL.

        Returns:
            ResearchResponse with search hits, retrieved sources, and candidate passages.

        Raises:
            SearchProviderError: On upstream search configuration or API failure.
        """
        start_time = time.monotonic()
        overall_deadline = start_time + settings.research_timeout_seconds
        now_iso = datetime.now(timezone.utc).isoformat()

        queries_used: list[ClaimLinkedQuery] = []
        search_hits: list[SearchResultHit] = []
        retrieved_sources: list[RetrievedSource] = []
        candidate_passages: list[EvidencePassage] = []
        distinct_urls: list[str] = []
        timed_out = False
        search_error: str | None = None
        has_supplied_source = bool(req.source_url and req.source_url.strip())

        provider = self._get_search_provider()

        async def _run_pipeline() -> None:
            nonlocal distinct_urls, timed_out, search_error
            # Step 1: Generate and execute search queries (at most 2 queries)
            if req.override_query and req.override_query.strip():
                planned_queries = [(req.override_query.strip(), "override_query")]
            else:
                planned_queries = build_search_queries(
                    claim_id=req.claim_id,
                    claim_text=req.claim_text,
                    location=req.explicit_location,
                    date=req.explicit_date,
                )

            for q_text, q_intent in planned_queries:
                remaining = overall_deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break

                # Enforce max 2 search API requests including retries across the research action
                if getattr(provider, "total_requests_made", 0) >= settings.max_search_queries_per_claim:
                    break

                q_id = f"qry_{uuid.uuid4().hex[:10]}"
                linked_query = ClaimLinkedQuery(
                    query_id=q_id,
                    claim_id=req.claim_id,
                    query_text=q_text,
                    query_intent=q_intent,
                    generated_at=now_iso,
                )
                queries_used.append(linked_query)

                try:
                    raw_results = await asyncio.wait_for(
                        provider.search(
                            query=q_text,
                            max_results=settings.max_search_hits_per_query,
                        ),
                        timeout=max(0.001, remaining),
                    )
                except (TimeoutError, asyncio.TimeoutError):
                    timed_out = True
                    break
                except asyncio.CancelledError:
                    raise
                except SearchProviderError as exc:
                    logger.warning("Search provider failed on query '%s': %s", q_text, exc)
                    clean_msg = _sanitize_error_message(str(exc))
                    if not has_supplied_source:
                        raise SearchProviderError(clean_msg) from exc
                    search_error = clean_msg
                    break
                except Exception as exc:
                    logger.warning("Search provider unexpected failure on query '%s': %s", q_text, exc)
                    clean_msg = _sanitize_error_message(str(exc))
                    if not has_supplied_source:
                        raise SearchProviderError(f"Search provider error: {clean_msg}") from exc
                    search_error = f"Search provider error: {clean_msg}"
                    break

                for raw in raw_results:
                    hit_id = f"hit_{uuid.uuid4().hex[:10]}"
                    hit = SearchResultHit(
                        result_id=hit_id,
                        query_id=q_id,
                        claim_id=req.claim_id,
                        url=raw.url,
                        title=raw.title,
                        snippet=raw.snippet,
                        rank=raw.rank,
                        engine=raw.engine,
                        is_snippet_only=True,
                    )
                    search_hits.append(hit)

                # If primary query returned hits, don't execute secondary query to conserve search budget
                if search_hits:
                    break

            # Step 2: Build candidate URLs pool (up to 5 search hits + optional supplied source_url)
            # Deprioritize JS-only social/forum shell domains behind news, official, and fact-check domains
            candidate_pool: list[str] = []
            if req.source_url and req.source_url.strip():
                candidate_pool.append(req.source_url.strip())

            standard_hit_urls: list[str] = []
            social_hit_urls: list[str] = []
            for hit in search_hits:
                if is_social_shell_url(hit.url):
                    social_hit_urls.append(hit.url)
                else:
                    standard_hit_urls.append(hit.url)

            candidate_pool.extend(standard_hit_urls)
            candidate_pool.extend(social_hit_urls)
            candidate_pool = deduplicate_urls(candidate_pool)
            distinct_urls = list(candidate_pool)

            # Step 3: Fetch candidate pages with SafeFetcher until 3 pages retrieved or pool exhausted
            retrieved_count = 0
            for url in candidate_pool:
                if retrieved_count >= settings.max_fetched_pages_per_claim:
                    break

                remaining = overall_deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    retrieved_sources.append(
                        RetrievedSource(
                            source_id=f"src_{uuid.uuid4().hex[:12]}",
                            initial_url=url,
                            status=SourceFetchState.INACCESSIBLE,
                            fetched_at=datetime.now(timezone.utc).isoformat(),
                            error_message=f"TIMEOUT: Research deadline of {settings.research_timeout_seconds}s exceeded.",
                        )
                    )
                    continue

                fetch_timeout = min(30.0, remaining)
                fetcher = self._get_fetcher(timeout_seconds=fetch_timeout)

                # Execute safe fetch isolated per candidate URL
                try:
                    source = await fetcher.fetch(url)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    source = RetrievedSource(
                        source_id=f"src_{uuid.uuid4().hex[:12]}",
                        initial_url=url,
                        status=SourceFetchState.INACCESSIBLE,
                        fetched_at=datetime.now(timezone.utc).isoformat(),
                        error_message=f"FETCH_ERROR: {exc}",
                    )

                # If retrieved, clean HTML or plain text to readable plaintext and extract verbatim passages
                if source.status == SourceFetchState.RETRIEVED and source.extracted_text:
                    raw_sample = source.extracted_text[:5000]

                    # Cooperative deadline check before synchronous extraction
                    if time.monotonic() > overall_deadline:
                        timed_out = True
                        source = source.model_copy(
                            update={
                                "status": SourceFetchState.INACCESSIBLE,
                                "error_message": f"TIMEOUT: Research deadline of {settings.research_timeout_seconds}s exceeded during extraction.",
                                "extracted_text": None,
                                "raw_text": raw_sample,
                                "extraction_note": "Timed out before content cleaning.",
                            }
                        )
                        retrieved_sources.append(source)
                        break

                    try:
                        cleaned_text = clean_text_content(
                            source.extracted_text,
                            content_type=source.content_type,
                            deadline=overall_deadline,
                        )
                    except (TimeoutError, asyncio.TimeoutError):
                        timed_out = True
                        source = source.model_copy(
                            update={
                                "status": SourceFetchState.INACCESSIBLE,
                                "error_message": f"TIMEOUT: Research deadline of {settings.research_timeout_seconds}s exceeded during parsing.",
                                "extracted_text": None,
                                "raw_text": raw_sample,
                                "extraction_note": "Parsing timed out.",
                            }
                        )
                        retrieved_sources.append(source)
                        break

                    if cleaned_text:
                        source = source.model_copy(
                            update={
                                "extracted_text": cleaned_text,
                                "raw_text": raw_sample,
                                "extraction_note": f"MIME {source.content_type or 'unknown'}; normalized length {len(cleaned_text)} chars from {len(source.extracted_text)} raw chars.",
                            }
                        )
                        try:
                            passages = extract_candidate_passages(
                                source=source,
                                claim_id=req.claim_id,
                                claim_text=req.claim_text,
                                location=req.explicit_location,
                                date=req.explicit_date,
                                deadline=overall_deadline,
                                override_query=req.override_query,
                            )
                        except (TimeoutError, asyncio.TimeoutError):
                            timed_out = True
                            passages = []

                        for passage in passages:
                            if verify_passage_provenance(passage, source):
                                candidate_passages.append(passage)

                        retrieved_count += 1
                    else:
                        source = source.model_copy(
                            update={
                                "status": SourceFetchState.EXTRACTION_FAILED,
                                "error_message": "Document parsed to empty or non-text content.",
                                "extracted_text": None,
                                "raw_text": raw_sample,
                                "extraction_note": "Parsed to empty content.",
                            }
                        )

                retrieved_sources.append(source)

        try:
            async with asyncio.timeout(max(0.001, settings.research_timeout_seconds)):
                await _run_pipeline()
        except (TimeoutError, asyncio.TimeoutError):
            timed_out = True
        except asyncio.CancelledError:
            raise

        # Monotonic post-execution deadline check to ensure over-budget runs are never labeled ordinary success
        if time.monotonic() > overall_deadline:
            timed_out = True

        completed_seconds = round(time.monotonic() - start_time, 2)
        retrieved_count = sum(1 for s in retrieved_sources if s.status == SourceFetchState.RETRIEVED)

        # Ensure any candidate URLs not yet reached get a TIMEOUT record ONLY if timed out
        if timed_out:
            fetched_urls = {s.initial_url for s in retrieved_sources}
            for u in distinct_urls:
                if u not in fetched_urls:
                    retrieved_sources.append(
                        RetrievedSource(
                            source_id=f"src_{uuid.uuid4().hex[:12]}",
                            initial_url=u,
                            status=SourceFetchState.INACCESSIBLE,
                            fetched_at=datetime.now(timezone.utc).isoformat(),
                            error_message=f"TIMEOUT: Research deadline of {settings.research_timeout_seconds}s exceeded.",
                        )
                    )

        # Cross-source deduplication of near-identical verbatim quotes (top 1-5 distinct bullets)
        deduped_passages: list[EvidencePassage] = []
        for p in candidate_passages:
            p_text = p.exact_passage.strip().lower()
            p_words = set(re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", p_text))
            is_dup = False
            for existing in deduped_passages:
                e_text = existing.exact_passage.strip().lower()
                if p_text == e_text or p_text in e_text or e_text in p_text:
                    is_dup = True
                    break
                e_words = set(re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", e_text))
                if p_words and e_words:
                    intersection = len(p_words.intersection(e_words))
                    union = len(p_words.union(e_words))
                    if union > 0 and (intersection / union) >= 0.75:
                        is_dup = True
                        break
            if not is_dup:
                deduped_passages.append(p)
            if len(deduped_passages) >= 5:
                break
        candidate_passages = deduped_passages

        # Step 4: Grounded evidence synthesis and relevance explanations
        inquiry_synthesis: str | None = None
        suggested_next_queries: list[str] = []

        adapter = self._get_gemini_adapter()
        if adapter is not None and candidate_passages and not timed_out:
            remaining = overall_deadline - time.monotonic()
            if remaining > 1.0:
                synthesis_timeout = min(15.0, remaining)
                try:
                    llm_synth = await adapter.synthesize_evidence(
                        claim_text=req.claim_text,
                        passages=candidate_passages,
                        timeout_seconds=synthesis_timeout,
                    )
                    if llm_synth:
                        inquiry_synthesis = llm_synth.inquiry_synthesis
                        suggested_next_queries = llm_synth.suggested_next_queries[:3]
                        passage_items = getattr(llm_synth, "passages", None) or getattr(llm_synth, "passage_relevances", None) or []
                        rel_map = {}
                        for idx, pr in enumerate(passage_items):
                            pid = getattr(pr, "passage_id", None) or (pr.get("passage_id") if isinstance(pr, dict) else None)
                            expl = getattr(pr, "relevance_explanation", None) or (pr.get("relevance_explanation") if isinstance(pr, dict) else None)
                            if pid:
                                rel_map[pid] = expl
                            # Also support matching by 0-based index if LLM returned 1, 2, or index-based ids
                            if idx < len(candidate_passages) and expl and candidate_passages[idx].passage_id not in rel_map:
                                rel_map[candidate_passages[idx].passage_id] = expl

                        updated_passages: list[EvidencePassage] = []
                        for p in candidate_passages:
                            if p.passage_id in rel_map and rel_map[p.passage_id]:
                                updated_passages.append(p.model_copy(update={"relevance_explanation": rel_map[p.passage_id]}))
                            else:
                                updated_passages.append(p)
                        candidate_passages = updated_passages
                except Exception as exc:
                    logger.warning("Synthesis failed, falling back to deterministic: %s", exc)

        # Graceful deterministic fallback
        if not candidate_passages:
            if inquiry_synthesis is None:
                inquiry_synthesis = "No relevant verbatim passages directly matching the inquiry could be retrieved from candidate sources."
            if not suggested_next_queries:
                suggested_next_queries = generate_fallback_next_queries(req.claim_text, req.explicit_location)[:2]
        else:
            if inquiry_synthesis is None:
                inquiry_synthesis = (
                    f"Retrieved {len(candidate_passages)} substantive verbatim passage(s) matching terms in the inquiry. "
                    "Review the extracted quotes below to examine how primary sources address the claim."
                )
            if not suggested_next_queries:
                suggested_next_queries = generate_fallback_next_queries(req.claim_text, req.explicit_location)
            # Ensure every passage has relevance_explanation
            updated_passages = []
            for p in candidate_passages:
                if not p.relevance_explanation:
                    host = urllib.parse.urlparse(p.source_url).netloc or "source"
                    note_text = p.relevance_note or "Extracted lead passage"
                    explanation = f"From {host}: {note_text.lower()} directly referencing the inquiry subject."
                    updated_passages.append(p.model_copy(update={"relevance_explanation": explanation}))
                else:
                    updated_passages.append(p)
            candidate_passages = updated_passages

        if timed_out:
            status_msg = (
                f"TIMEOUT: Research deadline of {settings.research_timeout_seconds}s exceeded after {completed_seconds}s. "
                f"Gathered {len(search_hits)} candidate search hit(s); "
                f"fetched {retrieved_count} of {len(distinct_urls)} candidate page(s)."
            )
        elif search_error:
            status_msg = (
                f"Search provider unavailable ({search_error}). "
                f"Fetched {retrieved_count} of {len(distinct_urls)} candidate page(s) from supplied source URL "
                f"in {completed_seconds}s."
            )
        else:
            status_msg = (
                f"Gathered {len(search_hits)} candidate search hit(s); "
                f"fetched {retrieved_count} of {len(distinct_urls)} candidate page(s) "
                f"in {completed_seconds}s."
            )

        return ResearchResponse(
            submission_id=req.submission_id,
            claim_id=req.claim_id,
            queries_used=queries_used,
            search_hits=search_hits,
            retrieved_sources=retrieved_sources,
            candidate_passages=candidate_passages,
            researched_at=now_iso,
            status_message=status_msg,
            completed_in_seconds=completed_seconds,
            search_failure_message=search_error,
            inquiry_synthesis=inquiry_synthesis,
            suggested_next_queries=suggested_next_queries,
        )
