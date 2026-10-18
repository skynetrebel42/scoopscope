"""Tests for Custom Page Report & Evidence Bank Builder, artifact rejection, and fallback query grammar."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import ReportRequest, ReportVibe, SelectedPassageItem, SourceMetadataItem
from app.retrieval.passage_extractor import (
    is_substantive_passage,
    extract_candidate_passages,
)
from app.research import generate_fallback_next_queries
from app.gemini_adapter import GeminiAdapter, build_deterministic_custom_report


# ===========================================================================
# 1. Extraction Artifact & Tag Cloud Rejection Tests
# ===========================================================================

def test_rejects_html_url_leftovers():
    # Fragment containing raw HTML / URL leftovers
    raw_html_frag = '<div class="tweet">"> href="https://twitter.com/GavinNewsom/status/1838927192">Official statement</div>'
    assert is_substantive_passage(raw_html_frag) is False

    status_frag = "Click here to see more status/184920193 on twitter com/GavinNewsom/status/184920193 updates."
    assert is_substantive_passage(status_frag) is False

    href_frag = 'Further information available at href="https://example.com/reports" for public inspection.'
    assert is_substantive_passage(href_frag) is False


def test_rejects_tag_cloud_and_social_metadata():
    tag_cloud = "Related Topics: European Union, Beef, Agriculture, Trade policy, Chemical residues, Food safety."
    assert is_substantive_passage(tag_cloud) is False

    tags_block = "Tags: Argentina economy, Mercosur deal, EU imports, beef quotas, SENASA inspections."
    assert is_substantive_passage(tags_block) is False

    share_block = "Share via Email, Twitter, Facebook, LinkedIn or copy permanent link to clipboard."
    assert is_substantive_passage(share_block) is False

    # CamelCase-mashed tag lists like 'electionsChloe'
    mashed_tags = "electionsChloe policyCalifornia budgetUpdate senateAction legislatureReview"
    assert is_substantive_passage(mashed_tags) is False


def test_accepts_clean_substantive_passage():
    clean_passage = (
        "European food safety authorities suspended beef import certifications from three packaging "
        "facilities in September 2024 following chemical pesticide residue detections during routine audits."
    )
    assert is_substantive_passage(clean_passage) is True


# ===========================================================================
# 2. Tightened Subject Anchoring with Override Query
# ===========================================================================

def test_tightened_subject_anchoring_with_override_query():
    body = (
        "State Senator Erickson discussed transit improvements and local district updates during "
        "the committee hearing on Thursday afternoon in Sacramento.\n\n"
        "Governor Gavin Newsom signed the statewide clean energy infrastructure legislation into law "
        "following bipartisan approval by the California legislature.\n\n"
        "The state assembly committee also reviewed several unrelated municipal water bond provisions "
        "presented by regional water district directors."
    )

    from datetime import datetime, timezone
    from app.search.models import RetrievedSource

    source = RetrievedSource(
        source_id="src_anchor_1",
        initial_url="https://example.com/news",
        final_url="https://example.com/news",
        extracted_text=body,
        status="retrieved",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )

    passages = extract_candidate_passages(
        source=source,
        claim_id="claim_anchor_1",
        claim_text="California passed clean energy laws",
        location="California",
        override_query="Gavin Newsom legislation",
    )

    assert len(passages) >= 1
    for p in passages:
        # Every matched passage must mention Gavin Newsom
        assert "Newsom" in p.exact_passage
        assert "Erickson" not in p.exact_passage


# ===========================================================================
# 3. Clean Grammar in generate_fallback_next_queries
# ===========================================================================

def test_generate_fallback_next_queries_strips_trailing_prepositions_and_deduplicates():
    claim_text = "Europe currently ban Argentinian beef due"
    location = "Europe, Argentina"

    queries = generate_fallback_next_queries(claim_text=claim_text, location=location)

    assert len(queries) >= 1
    for q in queries:
        # Must not contain trailing "due"
        assert not q.startswith("Europe currently ban Argentinian beef due ")
        assert " due " not in q
        assert not q.endswith(" due")
        # Must not duplicate "Europe" in immediate succession like "due Europe, Argentina"
        words = q.lower().split()
        europe_count = words.count("europe")
        assert europe_count <= 1, f"Repeated Europe found in: {q}"


def test_generate_fallback_next_queries_strips_various_prepositions():
    for prep in ["because", "of", "to", "for", "with", "in", "by"]:
        claim = f"Los Angeles allocated emergency homeless funds {prep}"
        queries = generate_fallback_next_queries(claim_text=claim, location="Los Angeles")
        for q in queries:
            assert not q.endswith(f" {prep}")
            assert f" {prep} " not in q


# ===========================================================================
# 4. Report Builder & POST /api/report Endpoint Tests
# ===========================================================================

def test_deterministic_custom_report_synthesis():
    passages = [
        SelectedPassageItem(
            passage_id="p1",
            exact_passage="European food safety authorities suspended beef import certifications from three packaging plants.",
            context_surrounding="In September 2024, European food safety authorities suspended beef import certifications from three packaging plants following pesticide residue detections.",
            source_url="https://ec.europa.eu/food/safety/beef-safety",
            relevance_explanation="Confirms plant suspensions.",
            publication_date="2024-09-15",
        )
    ]
    sources = [
        SourceMetadataItem(
            url="https://ec.europa.eu/food/safety/beef-safety",
            domain="ec.europa.eu",
            title="European Commission Food Safety Audit",
            publication_date="2024-09-15",
            retrieval_date="2024-10-16T18:00:00Z",
            status="retrieved",
        )
    ]

    # Test each vibe
    for vibe in [ReportVibe.OBJECTIVE_BRIEF, ReportVibe.CORNELL_STUDY, ReportVibe.FACT_CHECK, ReportVibe.DEEP_DIVE]:
        req = ReportRequest(
            inquiry_title="Europe Argentinian Beef Restrictions",
            report_vibe=vibe,
            include_summary=True,
            include_evidence_bank=True,
            include_works_cited=True,
            include_open_questions=True,
            custom_focus="Focus on import ban timelines",
            selected_passages=passages,
            sources=sources,
        )
        resp = build_deterministic_custom_report(req)
        md = resp.markdown_content
        assert "# " in md and "Europe Argentinian Beef Restrictions" in md
        assert "Synthesis" in md or "Evidence Breakdown" in md or "Contextual Narrative" in md
        assert "Structured Evidence Bank" in md
        assert "Works Cited & Bibliography" in md
        assert "Unresolved Assumptions & Next Questions" in md
        assert "Focus on import ban timelines" in md
        assert "https://ec.europa.eu/food/safety/beef-safety" in md


def test_post_api_report_endpoint():
    client = TestClient(app)

    req_payload = {
        "inquiry_title": "Europe Argentinian Beef Restrictions",
        "report_vibe": "objective_brief",
        "include_summary": True,
        "include_evidence_bank": True,
        "include_works_cited": True,
        "include_open_questions": False,
        "custom_focus": None,
        "selected_passages": [
            {
                "passage_id": "psg_1",
                "exact_passage": "European food safety authorities suspended beef import certifications from three packaging plants.",
                "context_surrounding": "In September 2024, European food safety authorities suspended beef import certifications.",
                "source_url": "https://ec.europa.eu/food/safety/beef-safety",
                "relevance_explanation": "Confirms certification suspensions.",
                "publication_date": "2024-09-15"
            }
        ],
        "sources": [
            {
                "url": "https://ec.europa.eu/food/safety/beef-safety",
                "domain": "ec.europa.eu",
                "title": "European Commission Food Safety Audit",
                "publication_date": "2024-09-15",
                "retrieval_date": "2024-10-16T18:00:00Z",
                "status": "retrieved"
            }
        ]
    }

    resp = client.post("/api/report", json=req_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "Europe Argentinian Beef Restrictions" in data["report_title"]
    assert data["selected_quote_count"] == 1
    assert data["source_count"] == 1
    assert "Europe Argentinian Beef Restrictions" in data["markdown_content"]
    assert "https://ec.europa.eu/food/safety/beef-safety" in data["markdown_content"]
    assert "https://ec.europa.eu/food/safety/beef-safety" in data["markdown_content"]


def test_post_api_report_empty_passages_rejected():
    client = TestClient(app)
    req_payload = {
        "inquiry_title": "Europe Argentinian Beef Restrictions",
        "report_vibe": "objective_brief",
        "include_summary": True,
        "include_evidence_bank": True,
        "include_works_cited": True,
        "include_open_questions": False,
        "selected_passages": [],
        "sources": []
    }
    resp = client.post("/api/report", json=req_payload)
    assert resp.status_code == 400
    assert "at least one quote" in resp.json()["detail"].lower()


def test_post_api_report_citation_styles_deterministic():
    """Works Cited formats deterministically across Standard, APA, and MLA without fabricating authors or dates."""
    client = TestClient(app)

    base_payload = {
        "inquiry_title": "Norwalk Homeless Shelter Ordinance",
        "report_vibe": "objective_brief",
        "include_summary": False,
        "include_evidence_bank": False,
        "include_works_cited": True,
        "include_open_questions": False,
        "selected_passages": [
            {
                "passage_id": "pass_1",
                "exact_passage": "The City Council voted unanimously to enact an emergency moratorium on new emergency shelters.",
                "source_url": "https://norwalkca.gov/council-resolution",
                "source_title": "Norwalk City Council Resolution 24-01",
                "publication_date": "2024-08-06",
                "jurisdiction_tag": "LA Local City Official",
                "jurisdiction_code": "la_local_city",
            },
            {
                "passage_id": "pass_2",
                "exact_passage": "State housing officials issued a notice of violation to the municipality.",
                "source_url": "https://hcd.ca.gov/news/norwalk-notice",
                "source_title": "HCD Notice of Violation",
                "publication_date": None,  # Missing publication date
                "retrieval_date": "2024-10-18T12:00:00Z",
                "jurisdiction_tag": "CA State Official",
                "jurisdiction_code": "ca_state",
            }
        ],
        "sources": [
            {
                "url": "https://norwalkca.gov/council-resolution",
                "domain": "norwalkca.gov",
                "title": "Norwalk City Council Resolution 24-01",
                "publication_date": "2024-08-06",
                "retrieval_date": "2024-10-18T10:00:00Z",
                "status": "retrieved",
                "jurisdiction_tag": "LA Local City Official",
                "jurisdiction_code": "la_local_city",
            },
            {
                "url": "https://hcd.ca.gov/news/norwalk-notice",
                "domain": "hcd.ca.gov",
                "title": "HCD Notice of Violation",
                "publication_date": None,  # No date available
                "retrieval_date": "2024-10-18T12:00:00Z",
                "status": "retrieved",
                "jurisdiction_tag": "CA State Official",
                "jurisdiction_code": "ca_state",
            }
        ]
    }

    # 1. Standard citation style
    resp_std = client.post("/api/report", json={**base_payload, "citation_style": "standard"})
    assert resp_std.status_code == 200
    md_std = resp_std.json()["markdown_content"]
    assert "## Works Cited" in md_std
    assert "norwalkca.gov" in md_std
    assert "[LA Local City Official]" in md_std
    assert "[CA State Official]" in md_std

    # 2. APA (7th ed) citation style
    resp_apa = client.post("/api/report", json={**base_payload, "citation_style": "apa"})
    assert resp_apa.status_code == 200
    md_apa = resp_apa.json()["markdown_content"]
    assert "## Works Cited" in md_apa
    # For missing date, APA must render (n.d.) explicitly
    assert "(n.d.)" in md_apa
    # For known date, year is formatted
    assert "(2024" in md_apa
    # Jurisdiction badge appended
    assert "[LA Local City Official]" in md_apa

    # 3. MLA (9th ed) citation style
    resp_mla = client.post("/api/report", json={**base_payload, "citation_style": "mla"})
    assert resp_mla.status_code == 200
    md_mla = resp_mla.json()["markdown_content"]
    assert "## Works Cited" in md_mla
    # MLA quotation around title
    assert '"Norwalk City Council Resolution 24-01."' in md_mla or '"Norwalk City Council Resolution 24-01"' in md_mla
    assert "Accessed" in md_mla
    assert "[LA Local City Official]" in md_mla

