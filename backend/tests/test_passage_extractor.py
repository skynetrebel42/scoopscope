"""Unit tests for HTML text cleaning, passage extraction, and provenance validation.

Verifies:
1. Script and style execution prevention (all executable tags stripped).
2. Exact character offset invariant: extracted_text[start:end] == exact_passage.
3. Provenance verification: verify_passage_provenance checks exact match and source status.
4. Default dates and dependence are unknown (None and UNKNOWN).
5. Inaccessible/failed sources yield zero candidate passages.
6. URL deduplication preserves order and normalizes trailing slashes and fragments.
"""

from __future__ import annotations

from app.retrieval.passage_extractor import (
    clean_html_to_text,
    deduplicate_urls,
    extract_candidate_passages,
    verify_passage_provenance,
)
from app.search.models import (
    RetrievedSource,
    SourceDependence,
    SourceFetchState,
)


def test_clean_html_strips_scripts_and_styles():
    raw_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <script>alert("malicious script execution");</script>
        <style>body { background: red; }</style>
    </head>
    <body>
        <header><nav><a href="/">Home</a></nav></header>
        <h1>City of Los Angeles Budget</h1>
        <p>The Los Angeles City Council approved a $13 billion budget for the fiscal year.</p>
        <script type="text/javascript">
            document.write("evil text");
        </script>
        <noscript>Please enable JS</noscript>
        <p>This includes funding for emergency services and housing programs.</p>
    </body>
    </html>
    """
    cleaned = clean_html_to_text(raw_html)
    assert "malicious" not in cleaned
    assert "evil text" not in cleaned
    assert "background: red" not in cleaned
    assert "City of Los Angeles Budget" in cleaned
    assert "approved a $13 billion budget" in cleaned
    assert "funding for emergency services" in cleaned


def test_exact_passage_offset_invariant():
    text = (
        "The City of Los Angeles officially declared a housing emergency in December 2022.\n\n"
        "Mayor Karen Bass signed Executive Directive 1 to accelerate affordable housing development.\n\n"
        "Over 10,000 units of housing have been approved under this directive."
    )

    source = RetrievedSource(
        source_id="src_test_123",
        initial_url="https://example.com/la-housing",
        final_url="https://example.com/la-housing",
        status=SourceFetchState.RETRIEVED,
        fetched_at="2026-10-14T12:00:00Z",
        extracted_text=text,
    )

    passages = extract_candidate_passages(
        source=source,
        claim_id="claim_001",
        claim_text="Karen Bass signed Executive Directive 1 for affordable housing",
        location="Los Angeles",
    )

    assert len(passages) >= 1
    top_passage = passages[0]

    # Verify exact substring match
    assert top_passage.exact_passage in text
    assert top_passage.start_offset is not None
    assert top_passage.end_offset is not None

    # Programmatic character slice invariant
    assert text[top_passage.start_offset:top_passage.end_offset] == top_passage.exact_passage

    # Verification function must pass
    assert verify_passage_provenance(top_passage, source) is True

    # Unknown dates and unknown source dependence preserved
    assert top_passage.publication_date is None
    assert top_passage.event_date is None
    assert top_passage.source_dependence == SourceDependence.UNKNOWN
    assert top_passage.claim_id == "claim_001"
    assert top_passage.source_url == "https://example.com/la-housing"


def test_provenance_verification_fails_on_tampering():
    text = "The quick brown fox jumps over the lazy dog."
    source = RetrievedSource(
        source_id="src_abc",
        initial_url="https://example.com",
        status=SourceFetchState.RETRIEVED,
        fetched_at="2026-10-14T12:00:00Z",
        extracted_text=text,
    )

    passages = extract_candidate_passages(source, "c1", "quick brown fox")
    assert len(passages) >= 1
    p = passages[0]

    # Verification succeeds on genuine passage
    assert verify_passage_provenance(p, source) is True

    # Fails if source status is not RETRIEVED
    bad_source = source.model_copy(update={"status": SourceFetchState.INACCESSIBLE})
    assert verify_passage_provenance(p, bad_source) is False

    # Fails if passage source_id doesn't match
    bad_source_id = source.model_copy(update={"source_id": "different_id"})
    assert verify_passage_provenance(p, bad_source_id) is False

    # Fails if exact passage was tampered with
    tampered_passage = p.model_copy(update={"exact_passage": "The slow blue fox"})
    assert verify_passage_provenance(tampered_passage, source) is False


def test_inaccessible_source_yields_no_passages():
    failed_source = RetrievedSource(
        source_id="src_fail",
        initial_url="https://example.com/blocked",
        status=SourceFetchState.SSRF_BLOCKED,
        fetched_at="2026-10-14T12:00:00Z",
        error_message="Destination resolved to private IP",
    )
    passages = extract_candidate_passages(failed_source, "c1", "any assertion")
    assert passages == []


def test_url_deduplication():
    urls = [
        "https://example.com/page",
        "https://example.com/page#section1",
        "https://example.com/page/",
        "https://EXAMPLE.COM/page",
        "https://example.com/other-page",
    ]
    deduped = deduplicate_urls(urls)
    assert len(deduped) == 2
    assert deduped[0] == "https://example.com/page"
    assert deduped[1] == "https://example.com/other-page"
