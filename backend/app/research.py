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

import logging
import re
import time
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.models import ResearchRequest, ResearchResponse
from app.retrieval.passage_extractor import (
    clean_html_to_text,
    deduplicate_urls,
    extract_candidate_passages,
    extract_keywords_from_claim,
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


def build_search_queries(
    claim_id: str,
    claim_text: str,
    location: str | None = None,
    date: str | None = None,
) -> list[tuple[str, str]]:
    """Build up to 2 deterministic, bounded query strings (query_text, query_intent)."""
    # Clean claim text of excessive whitespace or outer quotes
    cleaned = re.sub(r"\s+", " ", claim_text.strip().strip('"\''))
    loc = location.strip() if location else ""
    dt = date.strip() if date else ""

    # Primary assertion query
    parts_primary = [cleaned]
    if loc and loc.lower() not in cleaned.lower():
        parts_primary.append(loc)
    if dt and dt.lower() not in cleaned.lower():
        parts_primary.append(dt)
    q1 = " ".join(parts_primary)[:150].strip()

    # Broader keyword query (secondary fallback if primary returns 0 hits)
    keywords = extract_keywords_from_claim(cleaned, loc, dt)
    q2 = " ".join(keywords[:6])[:120].strip()

    queries = [(q1, "primary_assertion")]
    if q2 and q2.lower() != q1.lower():
        queries.append((q2, "broad_keywords"))

    return queries[:2]


class ResearchOrchestrator:
    """Orchestrates search hit gathering and safe page retrieval for a single claim."""

    def __init__(
        self,
        search_provider: SearchProvider | None = None,
        fetcher: SafeFetcher | None = None,
    ) -> None:
        self._search_provider = search_provider
        self._fetcher = fetcher

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

        provider = self._get_search_provider()

        # Step 1: Generate and execute search queries (at most 2 queries)
        planned_queries = build_search_queries(
            claim_id=req.claim_id,
            claim_text=req.claim_text,
            location=req.explicit_location,
            date=req.explicit_date,
        )

        for q_text, q_intent in planned_queries:
            remaining = overall_deadline - time.monotonic()
            if remaining <= 0:
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

            # Execute search hit gathering (max 5 hits per query)
            raw_results = await provider.search(
                query=q_text,
                max_results=settings.max_search_hits_per_query,
            )

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

            # If the primary query returned hits, don't execute secondary query to conserve search budget
            if search_hits:
                break

        # Step 2: Build candidate URLs (at most 3 distinct pages)
        candidate_urls: list[str] = []
        if req.source_url and req.source_url.strip():
            candidate_urls.append(req.source_url.strip())

        for hit in search_hits:
            candidate_urls.append(hit.url)

        # Deduplicate and cap at max_fetched_pages_per_claim (3)
        distinct_urls = deduplicate_urls(candidate_urls)[: settings.max_fetched_pages_per_claim]

        # Step 3: Fetch candidate pages with SafeFetcher
        for url in distinct_urls:
            remaining = overall_deadline - time.monotonic()
            if remaining <= 0:
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

            fetch_timeout = min(30.0, max(1.0, remaining))
            fetcher = self._get_fetcher(timeout_seconds=fetch_timeout)

            # Execute safe fetch
            source = await fetcher.fetch(url)

            # If retrieved, clean HTML to readable plaintext and extract verbatim passages
            if source.status == SourceFetchState.RETRIEVED and source.extracted_text:
                cleaned_text = clean_html_to_text(source.extracted_text)
                if cleaned_text:
                    source = source.model_copy(update={"extracted_text": cleaned_text})
                    passages = extract_candidate_passages(
                        source=source,
                        claim_id=req.claim_id,
                        claim_text=req.claim_text,
                        location=req.explicit_location,
                        date=req.explicit_date,
                    )
                    for passage in passages:
                        if verify_passage_provenance(passage, source):
                            candidate_passages.append(passage)
                else:
                    source = source.model_copy(
                        update={
                            "status": SourceFetchState.EXTRACTION_FAILED,
                            "error_message": "Document parsed to empty or non-text content.",
                            "extracted_text": None,
                        }
                    )

            retrieved_sources.append(source)

        completed_seconds = round(time.monotonic() - start_time, 2)
        retrieved_count = sum(1 for s in retrieved_sources if s.status == SourceFetchState.RETRIEVED)
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
        )
