"""Single live smoke investigation for ScoopScope Milestone 2C.

Connects to live Gemini and Serper APIs within strictly enforced bounds:
- 1 selected claim.
- At most 2 search API requests including retries.
- At most 5 hits per query.
- At most 3 candidate pages fetched via SafeFetcher.
- 90s deadline.
- Zero secret exposure.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import ASGITransport, AsyncClient

from app.main import app, research_orchestrator
from app.config import settings


async def run_live_smoke():
    print("=" * 60)
    print("SCOOPSCOPE MILESTONE 2C — LIVE SMOKE INVESTIGATION")
    print("=" * 60)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Step 1: Health check
        print("\n[Step 1] Checking /api/health...")
        health_res = await client.get("/api/health")
        assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
        health_data = health_res.json()
        print(f"  Health status: {health_data['status']}")
        print(f"  Gemini credentials configured: {health_data['credentials_configured']}")
        print(f"  Search credentials configured: {health_data.get('search_credentials_configured')}")
        assert health_data.get("search_credentials_configured") is True, "Search credentials not configured!"

        # Step 2: Extract claims from live statement
        test_statement = "Mayor Karen Bass took office in December 2022 as the 43rd Mayor of Los Angeles."
        print(f"\n[Step 2] Extracting claims via /api/extract...")
        print(f"  Input text: \"{test_statement}\"")

        extract_res = await client.post(
            "/api/extract",
            json={"text": test_statement, "source_url": None},
        )
        assert extract_res.status_code == 200, f"Extraction failed: {extract_res.text}"
        extract_data = extract_res.json()

        submission_id = extract_data["submission_id"]
        claims = extract_data["claims"]
        print(f"  Submission ID: {submission_id}")
        print(f"  Extracted {len(claims)} claim(s).")

        assert len(claims) >= 1, "Expected at least 1 claim extracted."
        selected_claim = claims[0]
        print(f"  Selected Claim ID: {selected_claim['id']}")
        print(f"  Normalized assertion: \"{selected_claim['normalized_assertion']}\"")
        print(f"  Claim type: {selected_claim['claim_type']}")
        print(f"  Location: {selected_claim.get('explicit_location')}")
        print(f"  Date: {selected_claim.get('explicit_date')}")

        # Step 3: Run single authorized research action via /api/research
        print(f"\n[Step 3] Dispatching live research request via /api/research...")
        research_payload = {
            "submission_id": submission_id,
            "claim_id": selected_claim["id"],
            "claim_text": selected_claim["normalized_assertion"] or selected_claim["original_wording"],
            "claim_type": selected_claim["claim_type"],
            "explicit_location": selected_claim.get("explicit_location"),
            "explicit_date": selected_claim.get("explicit_date"),
            "source_url": None,
        }

        t0 = time.monotonic()
        research_res = await client.post("/api/research", json=research_payload)
        elapsed = round(time.monotonic() - t0, 2)

        assert research_res.status_code == 200, f"Research failed ({research_res.status_code}): {research_res.text}"
        data = research_res.json()

        print(f"  Status: HTTP 200 OK (completed in {elapsed}s)")
        print(f"  Status message: {data['status_message']}")

        # Step 4: Validate budget and query limits
        queries = data.get("queries_used", [])
        hits = data.get("search_hits", [])
        sources = data.get("retrieved_sources", [])
        passages = data.get("candidate_passages", [])

        print(f"\n[Step 4] Validating Live Constraints:")
        provider_inst = getattr(research_orchestrator, "_search_provider", None) or research_orchestrator._get_search_provider()
        total_outbound = getattr(provider_inst, "total_requests_made", len(queries))
        print(f"  - Actual outbound search HTTP attempts made: {total_outbound} (limit <= 2)")
        assert total_outbound <= 2, f"Exceeded outbound search attempt limit: {total_outbound}"

        print(f"  - Queries executed: {len(queries)} (limit <= 2)")
        assert len(queries) <= 2, f"Exceeded query limit: {len(queries)}"
        for q in queries:
            print(f"    * \"{q['query_text']}\" (intent: {q['query_intent']})")

        print(f"  - Search hits returned: {len(hits)} (limit <= 5 per query)")
        assert len(hits) <= 5, f"Exceeded search hits limit: {len(hits)}"
        for hit in hits:
            print(f"    * #{hit['rank']} [{hit['title']}] -> {hit['url']}")
            print(f"      Snippet (snippet_only={hit['is_snippet_only']}): \"{hit['snippet'][:100]}...\"")
            assert hit["is_snippet_only"] is True, "Search hit must be marked snippet_only"

        print(f"  - Candidate pages fetched: {len(sources)} (limit <= 3)")
        assert len(sources) <= 3, f"Exceeded page fetch limit: {len(sources)}"
        for src in sources:
            print(f"    * URL: {src['final_url'] or src['initial_url']}")
            print(f"      Status: {src['status']}, HTTP: {src.get('http_status_code')}, IP: {src.get('resolved_ip')}, Size: {src.get('response_size_bytes')} bytes")

        print(f"  - Candidate verbatim passages extracted: {len(passages)}")
        for idx, p in enumerate(passages):
            print(f"\n    [Passage {idx+1}]")
            print(f"      Source ID: {p['source_id']}")
            print(f"      Exact Passage: \"{p['exact_passage']}\"")
            print(f"      Offsets: [{p['start_offset']}:{p['end_offset']}]")
            print(f"      Relevance: {p.get('relevance_note')}")
            print(f"      Dates: published={p.get('publication_date')}, event={p.get('event_date')}")
            print(f"      Source dependence: {p.get('source_dependence')}")

            # Verify provenance against matching source
            matching_source = next(s for s in sources if s["source_id"] == p["source_id"])
            extracted_text = matching_source["extracted_text"]
            assert extracted_text is not None, "Retrieved source extracted_text must not be None"
            sliced = extracted_text[p["start_offset"]:p["end_offset"]]
            assert sliced == p["exact_passage"], f"Provenance mismatch! Sliced: '{sliced}' vs Exact: '{p['exact_passage']}'"
            print(f"      Provenance check: VERIFIED EXACT SUBSTRING MATCH ({len(sliced)} chars)")

        # Verify research completed within overall 90-second deadline
        assert elapsed <= 90.0, f"Elapsed time {elapsed}s exceeded 90-second overall research deadline"

        # Verify nonempty evidence retrieval for the live assertion
        assert len(hits) >= 1, "Expected at least 1 search hit for known factual query"
        assert len(sources) >= 1, "Expected at least 1 retrieved candidate source"
        assert len(passages) >= 1, "Expected at least 1 verbatim candidate passage extracted"
        retrieved_sources = [s for s in sources if s["status"] == "retrieved"]
        assert len(retrieved_sources) >= 1, "Expected at least 1 source with status == RETRIEVED"

        # Verify zero verdict fields exist in payload
        assert "verdict" not in data, "Verdict must not be present in Milestone 2C"
        assert "truth_score" not in data, "Truth score must not be present in Milestone 2C"
        assert "confidence" not in data, "Confidence must not be present in Milestone 2C"

        print("\n" + "=" * 60)
        print(f"LIVE SMOKE INVESTIGATION: SUCCESSFUL AND FULLY VERIFIED ({elapsed}s, {len(retrieved_sources)} source(s), {len(passages)} passage(s))")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_live_smoke())
