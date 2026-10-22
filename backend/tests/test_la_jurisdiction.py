"""Automated tests for Milestone 4C: Los Angeles City vs. County Jurisdiction Guardrails.

Covers:
1. Deterministic Official Domain Provenance (classify_source_jurisdiction) across:
   - City of LA official domains and subdomains
   - LA County official domains and subdomains
   - LA Regional / Joint agencies
   - CA State Official domains (*.ca.gov)
   - US Government Official domains (*.gov, *.mil)
   - Third-party news and commercial domains (None)
   - Edge cases (ports, query parameters, uppercase, malformed URLs)
2. LA Ambiguity Detection in Clarification (detect_la_jurisdiction_ambiguity):
   - Ambiguous LA queries (returns True)
   - Explicit City of LA queries (returns False)
   - Explicit LA County queries (returns False)
   - Queries unrelated to Los Angeles (returns False)
3. API Endpoint Integration:
   - /api/clarify surfaces City vs. County vs. Both disambiguation on ambiguous LA inquiries
   - /api/research populates jurisdiction_tag and jurisdiction_code on sources and passages
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.jurisdiction import (
    classify_source_jurisdiction,
    detect_la_jurisdiction_ambiguity,
)
from app.main import app
from app.models import ClarificationResponse, InvestigationPurpose, ResearchRequest
from app.research import ResearchOrchestrator
from app.search.models import RawSearchResult
from app.search.provider import SearchProvider


# ===========================================================================
# 1. Deterministic Official Domain Provenance Tests
# ===========================================================================

@pytest.mark.parametrize(
    "url,expected_code,expected_label",
    [
        # City of LA official domains & subdomains
        ("https://lacity.gov", "la_city", "City of LA Official"),
        ("https://www.lacity.gov/my-page", "la_city", "City of LA Official"),
        ("https://lacity.org", "la_city", "City of LA Official"),
        ("https://www.lacity.org/directory", "la_city", "City of LA Official"),
        ("https://lapdonline.org", "la_city", "City of LA Official"),
        ("https://www.lapdonline.org/news", "la_city", "City of LA Official"),
        ("https://ladwp.com", "la_city", "City of LA Official"),
        ("https://www.ladwp.com/rates", "la_city", "City of LA Official"),
        ("https://lafd.org", "la_city", "City of LA Official"),
        ("https://www.lafd.org/alerts", "la_city", "City of LA Official"),
        ("https://lacontroller.org", "la_city", "City of LA Official"),
        ("https://clerk.lacity.org/elections", "la_city", "City of LA Official"),
        ("https://planning.lacity.org/plans", "la_city", "City of LA Official"),
        ("https://housing.lacity.org/renters", "la_city", "City of LA Official"),
        ("http://controller.lacity.org/reports", "la_city", "City of LA Official"),
        ("https://sub.portal.lacity.gov:8080/path?arg=1", "la_city", "City of LA Official"),

        # LA County official domains & subdomains
        ("https://lacounty.gov", "la_county", "LA County Official"),
        ("https://www.lacounty.gov/government", "la_county", "LA County Official"),
        ("https://bos.lacounty.gov/agenda", "la_county", "LA County Official"),
        ("https://lasd.org", "la_county", "LA County Official"),
        ("https://www.lasd.org/stations", "la_county", "LA County Official"),
        ("https://publichealth.lacounty.gov/covid", "la_county", "LA County Official"),
        ("https://dmh.lacounty.gov/services", "la_county", "LA County Official"),
        ("https://dpw.lacounty.gov/roads", "la_county", "LA County Official"),
        ("https://assessor.lacounty.gov/portal", "la_county", "LA County Official"),
        ("https://lavote.gov/voting", "la_county", "LA County Official"),
        ("https://da.lacounty.gov/cases", "la_county", "LA County Official"),
        ("http://ceo.lacounty.gov/budget", "la_county", "LA County Official"),

        # LA Regional / Joint agencies
        ("https://metro.net", "la_regional", "LA Regional Agency"),
        ("https://www.metro.net/riding/fares", "la_regional", "LA Regional Agency"),
        ("https://lausd.net", "la_regional", "LA Regional Agency"),
        ("https://www.lausd.net/schools", "la_regional", "LA Regional Agency"),
        ("https://lahsa.org", "la_regional", "LA Regional Agency"),
        ("https://www.lahsa.org/homelessness", "la_regional", "LA Regional Agency"),
        ("https://aqmd.gov", "la_regional", "LA Regional Agency"),
        ("https://www.aqmd.gov/air-quality", "la_regional", "LA Regional Agency"),
        ("https://mwdh2o.com", "la_regional", "LA Regional Agency"),
        ("https://www.mwdh2o.com/water-supply", "la_regional", "LA Regional Agency"),

        # LA Local City official domains (independent incorporated municipalities in LA County)
        ("https://norwalk.org", "la_local_city", "LA Local City Official"),
        ("https://www.norwalk.org/city-hall", "la_local_city", "LA Local City Official"),
        ("https://norwalkca.gov", "la_local_city", "LA Local City Official"),
        ("https://www.norwalkca.gov/council", "la_local_city", "LA Local City Official"),
        ("https://longbeach.gov", "la_local_city", "LA Local City Official"),
        ("https://police.longbeach.gov/alerts", "la_local_city", "LA Local City Official"),
        ("https://santamonica.gov", "la_local_city", "LA Local City Official"),
        ("https://library.santamonica.gov/books", "la_local_city", "LA Local City Official"),
        ("https://cityofpasadena.net", "la_local_city", "LA Local City Official"),
        ("https://water.cityofpasadena.net/service", "la_local_city", "LA Local City Official"),
        ("https://glendaleca.gov", "la_local_city", "LA Local City Official"),
        ("https://www.glendaleca.gov/government", "la_local_city", "LA Local City Official"),
        ("https://culvercity.org", "la_local_city", "LA Local City Official"),
        ("https://beverlyhills.org", "la_local_city", "LA Local City Official"),
        ("https://torranceca.gov", "la_local_city", "LA Local City Official"),
        ("https://inglewood.org", "la_local_city", "LA Local City Official"),
        ("https://burbankca.gov", "la_local_city", "LA Local City Official"),
        ("https://pomona.gov", "la_local_city", "LA Local City Official"),

        # CA State official
        ("https://ca.gov", "ca_state", "CA State Official"),
        ("https://www.ca.gov", "ca_state", "CA State Official"),
        ("https://dir.ca.gov/dlse/minimum_wage.htm", "ca_state", "CA State Official"),
        ("https://edd.ca.gov/unemployment", "ca_state", "CA State Official"),
        ("https://gov.ca.gov/news", "ca_state", "CA State Official"),
        ("https://courts.ca.gov/opinions", "ca_state", "CA State Official"),

        # US Government / Other Government official
        ("https://dol.gov/agencies/whd", "us_gov", "Government Official"),
        ("https://www.dol.gov", "us_gov", "Government Official"),
        ("https://census.gov/data", "us_gov", "Government Official"),
        ("https://whitehouse.gov/briefing-room", "us_gov", "Government Official"),
        ("https://navy.mil/info", "us_gov", "Government Official"),
    ],
)
def test_classify_source_jurisdiction_official_domains(url: str, expected_code: str, expected_label: str):
    """Official government domains must map deterministically to verified jurisdiction badges."""
    result = classify_source_jurisdiction(url)
    assert result is not None, f"Expected jurisdiction classification for {url}"
    assert result["code"] == expected_code
    assert result["label"] == expected_label


@pytest.mark.parametrize(
    "url",
    [
        "https://latimes.com/california/story/2024-01-15/minimum-wage",
        "https://www.latimes.com",
        "https://laist.com/news/housing/eviction-protections",
        "https://www.laist.com",
        "https://nytimes.com/section/us",
        "https://reddit.com/r/losangeles/comments/xyz",
        "https://twitter.com/lacity",
        "https://example.com/la-budget",
        "https://en.wikipedia.org/wiki/Los_Angeles",
        "https://cnn.com/us",
        "not_a_valid_url",
        "",
        "http://",
    ],
)
def test_classify_source_jurisdiction_non_government(url: str):
    """Third-party, news, social, commercial, or invalid domains must NEVER receive government badges."""
    result = classify_source_jurisdiction(url)
    assert result is None, f"Non-government URL {url} must not receive an official badge"


# ===========================================================================
# 2. LA Ambiguity Detection Tests
# ===========================================================================

@pytest.mark.parametrize(
    "text",
    [
        "Did LA raise the minimum wage?",
        "What is the LA eviction moratorium rule?",
        "LA law enforcement budget",
        "Los Angeles sales tax rate 2024",
        "Who handles trash collection in LA?",
        "Did L.A. pass rent control rules?",
        "LA rent increase cap 2024",
        "Can I build an ADU in Los Angeles?",
    ],
)
def test_detect_la_ambiguity_returns_true(text: str):
    """Inquiries referencing LA or Los Angeles without City vs County markers must trigger ambiguity."""
    assert detect_la_jurisdiction_ambiguity(text) is True


@pytest.mark.parametrize(
    "text",
    [
        # Explicit City markers
        "Did the City of LA raise the minimum wage?",
        "Did the City of Los Angeles pass an eviction moratorium?",
        "Mayor Karen Bass was sworn in as the 43rd Mayor of Los Angeles on December 11, 2022.",
        "LAPD annual operating budget",
        "LADWP power outage compensation policy",
        "What did the LA City Council vote on today?",
        "LA City minimum wage increase 2024",
        "lacity planning department zoning guidelines",

        # Explicit County markers
        "Did LA County raise the minimum wage?",
        "Los Angeles County eviction moratorium rules",
        "LASD deputy hiring requirements",
        "LA County Board of Supervisors agenda item 4",
        "Tenant rights in unincorporated LA County",
        "Eviction rules in unincorporated Los Angeles",
        "lacounty health department inspection results",

        # Unrelated to Los Angeles
        "Did California raise the minimum wage?",
        "Federal minimum wage laws in 2024",
        "What is the Chicago eviction ordinance?",
        "Explain the blast radius of a volcanic explosion",
        "New York City subway maintenance schedule",
    ],
)
def test_detect_la_ambiguity_returns_false(text: str):
    """Explicit City/County queries or queries unrelated to LA must NOT trigger ambiguity."""
    assert detect_la_jurisdiction_ambiguity(text) is False


# ===========================================================================
# 3. API Endpoint Integration Tests
# ===========================================================================

@pytest.mark.anyio
async def test_clarify_endpoint_surfaces_la_disambiguation():
    """Endpoint plumbing coverage: verify /api/clarify delegates to the adapter with expected inputs
    and returns the structured clarification response without network calls.

    Note: This tests FastAPI request handling and response serialization plumbing. A mocked response
    does not verify that the live Gemini model prompt will select these specific choices in production.
    """
    mock_clarification = ClarificationResponse(
        submitted_text="Did LA raise the minimum wage?",
        purpose=InvestigationPurpose.CHECK_CLAIM,
        is_clear=False,
        clarification_needed=True,
        round_index=1,
        max_rounds_reached=False,
        question="Which jurisdiction does your inquiry refer to?",
        choices=[
            "City of Los Angeles (City policy/ordinance)",
            "Los Angeles County (County/unincorporated)",
            "Both (City of LA and LA County)",
        ],
        interpreted_question="Did the City of Los Angeles or Los Angeles County raise the minimum wage?",
        material_uncertainties=["Jurisdiction unconfirmed: City of Los Angeles vs. Los Angeles County"],
        subclaims=[],
        status_message="Clarification requested for LA civic jurisdiction",
    )

    with patch("app.main.gemini.clarify_inquiry", new_callable=AsyncMock) as mock_clarify:
        mock_clarify.return_value = mock_clarification
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/clarify",
                json={
                    "text": "Did LA raise the minimum wage?",
                    "source_url": None,
                    "round_index": 1,
                },
            )

        # Assert adapter plumbing delegation with expected inputs
        mock_clarify.assert_awaited_once_with(
            text="Did LA raise the minimum wage?",
            source_url=None,
            round_index=1,
            exchanges=[],
            explicit_broad=False,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["clarification_needed"] is True
    assert data["choices"] is not None
    assert len(data["choices"]) == 3
    # Check that choices differentiate City of Los Angeles and Los Angeles County
    choices_str = " ".join(data["choices"]).lower()
    assert "city" in choices_str
    assert "county" in choices_str


class DummyMockSearchProvider(SearchProvider):
    """Deterministic mock provider returning official and non-official hits."""
    def __init__(self, hits: list[RawSearchResult]):
        self._hits = hits
        self.total_requests_made = 0

    async def search(self, query: str, max_results: int = 5) -> list[RawSearchResult]:
        self.total_requests_made += 1
        return self._hits[:max_results]


@pytest.mark.anyio
async def test_research_populates_jurisdiction_provenance_badges():
    """Retrieved sources and evidence passages must populate deterministic jurisdiction tags and codes."""
    mock_hits = [
        RawSearchResult(
            title="City of LA Minimum Wage",
            url="https://lacity.gov/wage-rules",
            snippet="The City of Los Angeles minimum wage is $17.28 per hour.",
            rank=1,
            engine="mock",
        ),
        RawSearchResult(
            title="LA County Unincorporated Wage",
            url="https://lacounty.gov/wage-ordinance",
            snippet="Los Angeles County unincorporated minimum wage is $17.27 per hour.",
            rank=2,
            engine="mock",
        ),
        RawSearchResult(
            title="LA Times Wage Comparison",
            url="https://latimes.com/california/minimum-wage-la",
            snippet="Understanding the differences between City and County wage rules.",
            rank=3,
            engine="mock",
        ),
    ]

    orchestrator = ResearchOrchestrator(
        search_provider=DummyMockSearchProvider(mock_hits)
    )

    req = ResearchRequest(
        submission_id="test_sub_la",
        claim_id="claim_la_1",
        claim_text="Did the City of Los Angeles raise the minimum wage?",
        explicit_location="City of Los Angeles",
    )

    response = await orchestrator.research_claim(req)

    # Check search hits carry jurisdiction tags
    hits_by_url = {h.url: h for h in response.search_hits}
    assert hits_by_url["https://lacity.gov/wage-rules"].jurisdiction_code == "la_city"
    assert hits_by_url["https://lacity.gov/wage-rules"].jurisdiction_tag == "City of LA Official"

    assert hits_by_url["https://lacounty.gov/wage-ordinance"].jurisdiction_code == "la_county"
    assert hits_by_url["https://lacounty.gov/wage-ordinance"].jurisdiction_tag == "LA County Official"

    assert hits_by_url["https://latimes.com/california/minimum-wage-la"].jurisdiction_code is None
    assert hits_by_url["https://latimes.com/california/minimum-wage-la"].jurisdiction_tag is None


@pytest.mark.anyio
async def test_jurisdiction_domain_ranking_in_research():
    """When confirmed inquiry scope specifies a jurisdiction, matching official domains rank ahead of mismatched municipal domains."""
    mock_hits = [
        RawSearchResult(
            url="https://latimes.com/news/norwalk-ordinance",
            title="LA Times Report on Norwalk",
            snippet="The city of Norwalk discussed housing rules.",
            rank=1,
            engine="test",
        ),
        RawSearchResult(
            url="https://lacity.gov/city-rules",
            title="City of Los Angeles Rules",
            snippet="Rules governing the City of LA.",
            rank=2,
            engine="test",
        ),
        RawSearchResult(
            url="https://norwalkca.gov/council-resolution",
            title="City of Norwalk Official Resolution",
            snippet="Official resolution passed by Norwalk City Council.",
            rank=3,
            engine="test",
        ),
        RawSearchResult(
            url="https://longbeach.gov/council-item",
            title="City of Long Beach Item",
            snippet="Long Beach city council items.",
            rank=4,
            engine="test",
        ),
    ]

    orchestrator = ResearchOrchestrator(
        search_provider=DummyMockSearchProvider(mock_hits)
    )

    req = ResearchRequest(
        submission_id="test_sub_norwalk",
        claim_id="claim_norwalk_1",
        claim_text="Did Norwalk City Council pass a moratorium on homeless shelters?",
        confirmed_scope_question="Did Norwalk City Council pass a moratorium on homeless shelters?",
    )

    response = await orchestrator.research_claim(req)

    # Check that retrieved sources or candidate pool prioritizes norwalkca.gov first
    source_urls = [s.initial_url for s in response.retrieved_sources]
    assert len(source_urls) >= 3
    # norwalkca.gov must be ranked #1 ahead of latimes.com and ahead of mismatched lacity.gov / longbeach.gov
    assert source_urls[0] == "https://norwalkca.gov/council-resolution"
    assert "https://lacity.gov/city-rules" not in source_urls[:2]

