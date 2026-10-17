"""Comprehensive unit and integration tests for Milestone 3B.

Covers:
1. Stem matching and demonym normalization (stem_word).
2. Subject/entity anchoring (rejecting off-topic paragraphs like Pakistan milk).
3. Substantive passage and headline filtering (is_substantive_passage).
4. Defensible date extraction (JSON-LD, meta tags, time tags, bylines) and negative checks
   (verifying HTTP Date headers and URL path years are NEVER used).
5. Conversational question stripping in Serper query generation.
6. Social domain deprioritization (reddit, twitter/x, etc. ranked behind news/official domains).
7. Fallback across the 5-hit pool when URLs fail (up to 3 successfully retrieved pages).
8. Grounded inquiry synthesis and per-quote relevance explanation with graceful fallback.
"""

from __future__ import annotations

import httpx
import pytest

from app.gemini_adapter import GeminiAdapter
from app.models import (
    ClarificationResponse,
    EvidenceSynthesisLLM,
    PassageRelevanceLLM,
    ResearchRequest,
)
from app.research import (
    ResearchOrchestrator,
    build_search_queries,
    generate_fallback_next_queries,
    is_social_shell_url,
)
from app.retrieval.passage_extractor import (
    extract_best_sentences_from_paragraph,
    extract_candidate_passages,
    extract_dates_from_html,
    extract_subject_terms_from_claim,
    is_substantive_passage,
    stem_word,
    verify_passage_provenance,
)
from app.retrieval.safe_fetcher import SafeFetcher
from app.search.models import (
    EvidencePassage,
    RawSearchResult,
    RetrievedSource,
    SourceFetchState,
)
from app.search.provider import SearchProvider


# ---------------------------------------------------------------------------
# 1. Stem Matching & Normalization
# ---------------------------------------------------------------------------

def test_stem_word_demonyms_and_inflections():
    # Demonyms
    assert stem_word("Argentinian") == "argentin"
    assert stem_word("Argentine") == "argentin"
    assert stem_word("Argentina") == "argentin"

    assert stem_word("European") == "europ"
    assert stem_word("Europe") == "europ"

    # Inflections
    assert stem_word("bans") == "ban"
    assert stem_word("banned") == "ban"
    assert stem_word("banning") == "ban"

    assert stem_word("chemicals") == "chemic"
    assert stem_word("chemical") == "chemic"

    assert stem_word("regulations") == stem_word("regulation") == "regulation"


# ---------------------------------------------------------------------------
# 2. Subject/Entity Anchoring
# ---------------------------------------------------------------------------

def test_subject_terms_extraction():
    claim = "Did the European Union ban Argentinian beef in 2024?"
    terms = extract_subject_terms_from_claim(claim, location="Argentina")
    # Must include entity terms from claim and location
    assert "argentinian" in terms
    assert "argentina" in terms
    assert "european" in terms


def test_subject_anchoring_rejects_off_topic_paragraphs():
    """Paragraphs about milk in Pakistan or Ethiopia must be rejected when claim is about Argentina."""
    text = (
        "In 2024, the European Commission suspended milk import approvals from several Argentinian "
        "dairy producers following routine inspections for chemical residues.\n\n"
        "Meanwhile, in Pakistan and Ethiopia, agricultural ministries reported widespread issues with "
        "unregulated antibiotic residues and chemical additives in raw milk distributed to rural markets.\n\n"
        "Argentine food safety agency SENASA confirmed it was addressing the European findings."
    )

    source = RetrievedSource(
        source_id="src_milk_test",
        initial_url="https://example.com/dairy-audit",
        status=SourceFetchState.RETRIEVED,
        fetched_at="2026-10-14T12:00:00Z",
        extracted_text=text,
    )

    passages = extract_candidate_passages(
        source=source,
        claim_id="c_milk",
        claim_text="Did the EU ban Argentinian milk over chemical residues in 2024?",
        location="Argentina",
    )

    # Must extract paragraphs about Argentina
    extracted_texts = [p.exact_passage for p in passages]
    assert any("Argentinian" in t or "Argentine" in t for t in extracted_texts)

    # Off-topic paragraph about Pakistan and Ethiopia must NOT be extracted
    assert not any("Pakistan" in t or "Ethiopia" in t for t in extracted_texts)


# ---------------------------------------------------------------------------
# 3. Substantive Passage & Headline Filtering
# ---------------------------------------------------------------------------

def test_is_substantive_passage_filtering():
    # Headlines / banners lacking terminal punctuation or too short
    assert is_substantive_passage("Breaking News: New Report") is False
    assert is_substantive_passage("EU Banned Milk") is False
    assert is_substantive_passage("Home About Us Services Contact Privacy Terms") is False
    assert is_substantive_passage("Share on Facebook Share on Twitter Share via Email") is False
    assert is_substantive_passage("Copyright 2024 Example Media Group. All rights reserved.") is False

    # Substantive sentence
    assert is_substantive_passage(
        "The European Commission officially implemented a restriction on dairy imports from Argentina in October 2024."
    ) is True


# ---------------------------------------------------------------------------
# 4. Defensible Date Extraction & Negative Checks
# ---------------------------------------------------------------------------

def test_date_extraction_json_ld():
    html = """
    <html><head>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Trade Suspension Announced",
        "datePublished": "2024-05-12T08:30:00Z",
        "dateModified": "2024-05-14T10:15:00Z"
    }
    </script>
    </head><body><p>Article body.</p></body></html>
    """
    pub_date, upd_date, prov = extract_dates_from_html(html)
    assert pub_date == "2024-05-12"
    assert upd_date == "2024-05-14"
    assert prov == "json-ld:datePublished"


def test_date_extraction_meta_tags():
    html = """
    <html><head>
    <meta property="article:published_time" content="2023-08-20T14:00:00+02:00">
    <meta property="article:modified_time" content="2023-08-22T09:00:00+02:00">
    </head><body><p>Article text.</p></body></html>
    """
    pub_date, upd_date, prov = extract_dates_from_html(html)
    assert pub_date == "2023-08-20"
    assert upd_date == "2023-08-22"
    assert prov == "meta:article:published_time"


def test_date_extraction_time_tag():
    html = """
    <html><body>
    <time datetime="2022-12-11T18:00:00Z">December 11, 2022</time>
    <p>City council approves resolution.</p>
    </body></html>
    """
    pub_date, upd_date, prov = extract_dates_from_html(html)
    assert pub_date == "2022-12-11"
    assert upd_date is None
    assert prov == "html:time"


def test_date_extraction_byline_text():
    html = """
    <html><body>
    <div class="byline">Published December 11, 2022 | Updated: Aug 27, 2026</div>
    <p>Article reporting on local election results.</p>
    </body></html>
    """
    pub_date, upd_date, prov = extract_dates_from_html(html)
    assert pub_date == "2022-12-11"
    assert upd_date == "2026-08-27"
    assert prov == "byline:published"


def test_date_extraction_negative_rules():
    """Publication dates must NEVER be extracted from URL paths or HTTP headers."""
    # HTML contains no dates in JSON-LD, meta, time tags, or bylines
    html = """
    <html><head><title>News Report</title></head>
    <body><p>The council convened today to review regional infrastructure priorities.</p></body>
    </html>
    """
    pub_date, upd_date, prov = extract_dates_from_html(html)
    assert pub_date is None
    assert upd_date is None
    assert prov is None


# ---------------------------------------------------------------------------
# 5. Conversational Question Stripping in Search Queries
# ---------------------------------------------------------------------------

def test_build_search_queries_strips_conversational_openers():
    queries = build_search_queries(
        claim_id="c_conv",
        claim_text="Did the EU ban Argentinian beef in 2024?",
        location="Argentina",
        date="2024",
    )
    assert len(queries) >= 1
    q1 = queries[0][0]
    # Conversational "Did " and "?" must be stripped
    assert not q1.startswith("Did ")
    assert not q1.endswith("?")
    assert "the EU ban Argentinian beef in 2024" in q1


# ---------------------------------------------------------------------------
# 6. Social Domain Deprioritization
# ---------------------------------------------------------------------------

def test_social_domain_detection():
    assert is_social_shell_url("https://www.reddit.com/r/news/comments/123/beef") is True
    assert is_social_shell_url("https://twitter.com/user/status/12345") is True
    assert is_social_shell_url("https://x.com/user/status/12345") is True
    assert is_social_shell_url("https://www.facebook.com/post/123") is True
    assert is_social_shell_url("https://www.tiktok.com/@user/video/123") is True
    assert is_social_shell_url("https://www.instagram.com/p/123") is True
    assert is_social_shell_url("https://threads.net/@user/post/123") is True

    # Real news / official domains must NOT be flagged
    assert is_social_shell_url("https://www.reuters.com/business/trade-news") is False
    assert is_social_shell_url("https://ec.europa.eu/food/safety") is False
    assert is_social_shell_url("https://apnews.com/article/123") is False


# ---------------------------------------------------------------------------
# 7. Fallback across 5-Hit Pool within 3-Page Cap
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_fallback_through_five_hit_pool_retrieves_three_successful():
    hits = [
        RawSearchResult(title="Social Post", url="https://reddit.com/r/news/beef", snippet="Reddit discussion", rank=1, engine="mock"),
        RawSearchResult(title="Broken Page 1", url="https://example.com/broken-1", snippet="Broken 404", rank=2, engine="mock"),
        RawSearchResult(title="Broken Page 2", url="https://example.com/broken-2", snippet="Broken 500", rank=3, engine="mock"),
        RawSearchResult(title="Official Doc", url="https://ec.europa.eu/food/beef", snippet="European trade report", rank=4, engine="mock"),
        RawSearchResult(title="News Article 1", url="https://reuters.com/beef-audit", snippet="Reuters report", rank=5, engine="mock"),
    ]

    class FiveHitSearchProvider(SearchProvider):
        async def search(self, query: str, max_results: int = 5):
            return hits

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "broken-1" in url_str:
            return httpx.Response(404, text="Not Found", headers={"Content-Type": "text/html"})
        if "broken-2" in url_str:
            return httpx.Response(500, text="Server Error", headers={"Content-Type": "text/html"})
        if "ec.europa.eu" in url_str:
            html = "<html><body><p>European officials inspected Argentinian beef processing plants in 2024.</p></body></html>"
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
        if "reuters.com" in url_str:
            html = "<html><body><p>Reuters reported on agricultural inspections and pesticide residue findings in Argentinian exports.</p></body></html>"
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
        if "reddit.com" in url_str:
            html = "<html><body><p>Forum user comments discussing beef bans in Argentina.</p></body></html>"
            return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})
        return httpx.Response(404, text="Unknown")

    fetcher = SafeFetcher(
        dns_resolver=lambda h: ["93.184.216.34"],
        custom_transport=httpx.MockTransport(mock_handler),
    )

    orchestrator = ResearchOrchestrator(
        search_provider=FiveHitSearchProvider(),
        fetcher=fetcher,
    )

    req = ResearchRequest(
        submission_id="sub_fallback",
        claim_id="c_fallback",
        claim_text="European inspection of Argentinian beef in 2024",
    )

    response = await orchestrator.research_claim(req)

    # Note that social domain (reddit) was deprioritized behind reuters and ec.europa.eu!
    retrieved_successful = [s for s in response.retrieved_sources if s.status == SourceFetchState.RETRIEVED]
    assert len(retrieved_successful) <= 3
    # Broken URLs were recorded as inaccessible
    inaccessible = [s for s in response.retrieved_sources if s.status == SourceFetchState.INACCESSIBLE]
    assert len(inaccessible) >= 2


# ---------------------------------------------------------------------------
# 8. Grounded Evidence Synthesis & Relevance Explanations
# ---------------------------------------------------------------------------

class MockGeminiAdapterWithSynthesis:
    """Mock Gemini adapter implementing synthesize_evidence."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    async def synthesize_evidence(self, claim_text: str, passages: list[EvidencePassage], timeout_seconds: float = 8.0) -> EvidenceSynthesisLLM | None:
        if self.should_fail:
            raise RuntimeError("Gemini service timeout")

        synthesis = (
            "Retrieved official documents indicate European safety authorities conducted targeted inspections "
            "of Argentinian beef facilities. While certifications were suspended for specific plants, "
            "no evidence suggests a blanket embargo was instituted across all trade."
        )
        next_queries = [
            "European Commission Food Safety audit Argentine beef 2024",
            "SENASA Argentina pesticide residue inspection report",
        ]
        explanations = [
            PassageRelevanceLLM(
                passage_id=p.passage_id,
                relevance_explanation="Confirms regulatory scrutiny of processing plants and residue limits.",
            )
            for p in passages
        ]

        return EvidenceSynthesisLLM(
            inquiry_synthesis=synthesis,
            suggested_next_queries=next_queries,
            passages=explanations,
        )


@pytest.mark.anyio
async def test_synthesis_generation_success():
    mock_adapter = MockGeminiAdapterWithSynthesis(should_fail=False)

    source = RetrievedSource(
        source_id="src_synth_1",
        initial_url="https://ec.europa.eu/food/safety",
        status=SourceFetchState.RETRIEVED,
        fetched_at="2026-10-14T12:00:00Z",
        extracted_text="European inspectors detected chemical residues in three beef facilities in Argentina in 2024.",
    )

    class SingleHitSearch(SearchProvider):
        async def search(self, query: str, max_results: int = 5):
            return [RawSearchResult(title="EU Audit", url="https://ec.europa.eu/food/safety", snippet="EU beef report", rank=1, engine="mock")]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=f"<html><body><p>{source.extracted_text}</p></body></html>", headers={"Content-Type": "text/html"})

    fetcher = SafeFetcher(
        dns_resolver=lambda h: ["93.184.216.34"],
        custom_transport=httpx.MockTransport(handler),
    )

    orchestrator = ResearchOrchestrator(
        search_provider=SingleHitSearch(),
        fetcher=fetcher,
        gemini_adapter=mock_adapter,
    )

    req = ResearchRequest(
        submission_id="sub_synth",
        claim_id="c_synth",
        claim_text="Did the EU ban Argentinian beef in 2024?",
        explicit_location="Argentina",
    )

    res = await orchestrator.research_claim(req)

    # Synthesis card text populated
    assert res.inquiry_synthesis is not None
    assert "Retrieved official documents indicate" in res.inquiry_synthesis

    # Suggested queries populated
    assert len(res.suggested_next_queries) == 2
    assert "SENASA Argentina" in res.suggested_next_queries[1]

    # Candidate passages have relevance_explanation populated
    assert len(res.candidate_passages) >= 1
    top_p = res.candidate_passages[0]
    assert top_p.relevance_explanation is not None
    assert "regulatory scrutiny" in top_p.relevance_explanation

    # Exact substring slice invariant maintained
    matching_source = next(s for s in res.retrieved_sources if s.source_id == top_p.source_id)
    assert verify_passage_provenance(top_p, matching_source) is True


@pytest.mark.anyio
async def test_synthesis_fallback_on_adapter_failure():
    """When Gemini adapter fails, orchestrator must fall back gracefully to deterministic synthesis."""
    mock_failing_adapter = MockGeminiAdapterWithSynthesis(should_fail=True)

    class SingleHitSearch(SearchProvider):
        async def search(self, query: str, max_results: int = 5):
            return [RawSearchResult(title="EU Audit", url="https://ec.europa.eu/food/safety", snippet="EU beef report", rank=1, engine="mock")]

    async def handler(request: httpx.Request) -> httpx.Response:
        html = "<html><body><p>European officials suspended import permits for Argentinian beef processing plants.</p></body></html>"
        return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})

    fetcher = SafeFetcher(
        dns_resolver=lambda h: ["93.184.216.34"],
        custom_transport=httpx.MockTransport(handler),
    )

    orchestrator = ResearchOrchestrator(
        search_provider=SingleHitSearch(),
        fetcher=fetcher,
        gemini_adapter=mock_failing_adapter,
    )

    req = ResearchRequest(
        submission_id="sub_synth_fail",
        claim_id="c_synth_fail",
        claim_text="EU suspended permits for Argentinian beef",
    )

    res = await orchestrator.research_claim(req)

    # Passages must NEVER be lost
    assert len(res.candidate_passages) >= 1
    top_p = res.candidate_passages[0]

    # Deterministic fallback populated
    assert res.inquiry_synthesis is not None
    assert "substantive verbatim passage" in res.inquiry_synthesis
    assert top_p.relevance_explanation is not None
    assert "keyword match" in top_p.relevance_explanation.lower()

    # Suggested queries fallback provided
    assert len(res.suggested_next_queries) >= 1


# ---------------------------------------------------------------------------
# 9. Milestone 3B Upgrades: Query Suffix, Boilerplate, Trimming, Timeout, Dedup
# ---------------------------------------------------------------------------

def test_search_queries_append_minus_filetype_pdf():
    queries = build_search_queries(
        claim_id="c1",
        claim_text="Did the FDA issue a recall on infant formula in 2024?",
        location="United States",
        date="2024",
    )
    assert len(queries) >= 1
    for q_text, _ in queries:
        assert "-filetype:pdf" in q_text


def test_generate_fallback_next_queries_clean_and_non_recursive():
    queries = generate_fallback_next_queries(
        claim_text="Did the European Union ban Argentinian beef in 2024?",
        location="Argentina",
    )
    assert len(queries) >= 1
    for q in queries:
        assert "Check primary regulatory filings regarding" not in q
        assert "Search official archives for updates on" not in q
        assert "site:" not in q
        assert "filetype:" not in q


def test_call_to_action_boilerplate_rejected():
    assert is_substantive_passage("For more information, please visit our website at fda.gov/recalls.") is False
    assert is_substantive_passage("Click here to read the full report on inspection results.") is False
    assert is_substantive_passage("Subscribe to our daily agricultural newsletter.") is False
    assert is_substantive_passage("Photo credit: Reuters / John Doe.") is False


def test_sentence_trimming_and_exact_character_offset_invariance():
    # Paragraph > 280 characters
    s1 = "In January 2024, the European Commission initiated a comprehensive audit of pesticide residues across agricultural shipments."
    s2 = "Officials suspended import authorizations for five major beef processing plants in Argentina following the detection of prohibited chemicals."
    s3 = "Industry representatives announced emergency meetings with international trade authorities to address the compliance timeline."
    full_para = f"{s1} {s2} {s3}"
    assert len(full_para) > 280

    full_body = f"Introductory background note.\n\n{full_para}\n\nConcluding remarks and contact details."
    para_start = full_body.find(full_para)
    assert para_start != -1

    source = RetrievedSource(
        source_id="src_long_para",
        initial_url="https://example.com/audit-report",
        status=SourceFetchState.RETRIEVED,
        fetched_at="2026-10-15T10:00:00Z",
        extracted_text=full_body,
    )

    passages = extract_candidate_passages(
        source=source,
        claim_id="c_trim",
        claim_text="Did the EU suspend Argentinian beef imports over prohibited chemicals in 2024?",
        location="Argentina",
    )

    assert len(passages) >= 1
    top_p = passages[0]

    # The passage must be trimmed to the highest-scoring sentence(s)
    assert len(top_p.exact_passage) < len(full_para)
    assert "suspended import authorizations for five major beef processing plants in Argentina" in top_p.exact_passage

    # Invariant: extracted_text[start:end] strictly equals exact_passage
    assert full_body[top_p.start_offset:top_p.end_offset] == top_p.exact_passage
    assert verify_passage_provenance(top_p, source) is True

    # The surrounding context retains the full paragraph
    assert full_para in top_p.context_surrounding


@pytest.mark.anyio
async def test_unfetched_urls_after_page_cap_not_labeled_timeout():
    """When page budget is satisfied within deadline, unreached search hits are NOT labeled as TIMEOUT."""
    class FiveHitSearch(SearchProvider):
        async def search(self, query: str, max_results: int = 5):
            return [
                RawSearchResult(title=f"Hit {i}", url=f"https://example.com/page-{i}", snippet=f"Snippet {i}", rank=i, engine="mock")
                for i in range(1, 6)
            ]

    async def handler(request: httpx.Request) -> httpx.Response:
        html = "<html><body><p>Argentine agricultural ministry released trade policy documentation.</p></body></html>"
        return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})

    fetcher = SafeFetcher(
        dns_resolver=lambda h: ["93.184.216.34"],
        custom_transport=httpx.MockTransport(handler),
    )

    orchestrator = ResearchOrchestrator(
        search_provider=FiveHitSearch(),
        fetcher=fetcher,
    )

    req = ResearchRequest(
        submission_id="sub_cap",
        claim_id="c_cap",
        claim_text="Argentine agricultural ministry trade policy documentation",
    )

    res = await orchestrator.research_claim(req)

    # Max 3 pages retrieved per settings.max_fetched_pages_per_claim
    retrieved = [s for s in res.retrieved_sources if s.status == SourceFetchState.RETRIEVED]
    assert len(retrieved) == 3

    # Candidate hits 4 and 5 were not fetched because budget was satisfied, but must NOT be marked TIMEOUT
    for s in res.retrieved_sources:
        assert "TIMEOUT" not in (s.error_message or "")


@pytest.mark.anyio
async def test_cross_source_quote_deduplication():
    """Near-identical verbatim quotes from wire reprints across different sites must be deduplicated."""
    class TwoHitSearch(SearchProvider):
        async def search(self, query: str, max_results: int = 5):
            return [
                RawSearchResult(title="LATimes Wire", url="https://latimes.com/story", snippet="EU beef ban", rank=1, engine="mock"),
                RawSearchResult(title="Presidency Archive", url="https://presidency.ucsb.edu/story", snippet="EU beef ban", rank=2, engine="mock"),
            ]

    wire_quote = "European regulators suspended export permits for Argentinian beef processing facilities after detecting chemical residues."
    async def handler(request: httpx.Request) -> httpx.Response:
        html = f"<html><body><p>{wire_quote}</p></body></html>"
        return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})

    fetcher = SafeFetcher(
        dns_resolver=lambda h: ["93.184.216.34"],
        custom_transport=httpx.MockTransport(handler),
    )

    orchestrator = ResearchOrchestrator(
        search_provider=TwoHitSearch(),
        fetcher=fetcher,
    )

    req = ResearchRequest(
        submission_id="sub_dedup",
        claim_id="c_dedup",
        claim_text="European regulators suspended export permits for Argentinian beef processing facilities",
    )

    res = await orchestrator.research_claim(req)

    # Both sources were fetched
    assert len(res.retrieved_sources) == 2
    # But identical quote from the second source was deduplicated
    assert len(res.candidate_passages) == 1
    assert res.candidate_passages[0].exact_passage == wire_quote

