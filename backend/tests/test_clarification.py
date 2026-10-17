"""Automated tests for Milestone 3A: Inquiry Clarification and Confirmed Scope.

Covers the five Milestone 3A acceptance checks:
1. Intent and scope fidelity: Across user samples (DACA, beef, Obama, clear dated claim,
   unrelated ambiguous claim), selected choices/free text produce the confirmed question.
   Current-status selections never silently convert into historical investigations or vice versa.
2. No invented particulars: Beef example retains unspecified substances as unknown (no guessed
   hormones), preserves "Europe" without silently assuming "EU" without a visible scope note.
   Compound claims preserve links to original wording.
3. Bounded clarification: Exactly three choices + free text appear when needed; second-round
   behavior works; third automatic round is impossible; clear claims proceed directly.
4. State and spending: Zero search requests before explicit confirmation. Only confirmed claim
   research triggers bounded retrieval.
5. Honest UI & limitation notes: Context/origin purposes honestly noted with future pipeline
   limitations; checkable claims tagged; model failure produces clear 503 errors.

All tests run completely offline without external API keys using explicit mocks and fixtures.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.gemini_adapter import GeminiAdapter, GeminiAdapterError
from app.main import app
from app.models import (
    ClaimType,
    ClarificationExchange,
    ClarificationRequest,
    ClarificationResponse,
    InvestigationPurpose,
)


def _mock_gemini_response(payload: dict | str) -> SimpleNamespace:
    """Helper creating a mock Gemini response with a .text attribute."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(text=text)


# ===========================================================================
# 1. Input Validation & Security Tests
# ===========================================================================

@pytest.mark.anyio
async def test_clarify_empty_input_returns_400():
    """Empty statement must be rejected with 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/clarify", json={"text": "   ", "source_url": None})
    assert resp.status_code == 400
    assert resp.json()["error"] == "Empty input"


@pytest.mark.anyio
async def test_clarify_missing_credentials_returns_503():
    """When GEMINI_API_KEY is missing, endpoint returns 503 with helpful details."""
    with patch("app.main.gemini._client", None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/clarify", json={"text": "Did the city approve the budget?"})
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"] == "Credentials not configured"
        assert "GEMINI_API_KEY" in data["detail"]


# ===========================================================================
# 2. Acceptance Check 1: Intent & Scope Fidelity Across Samples
# ===========================================================================

@pytest.mark.anyio
async def test_acceptance_check_1_intent_and_scope_fidelity_temporal_distinction():
    """Current-status selection must not silently become historical, and vice versa."""
    adapter = GeminiAdapter()

    # User statement about DACA status
    text = "What is going on with DACA?"

    # Model payload for round 1 asking temporal/status vs history
    mock_r1 = {
        "purpose": "check_claim",
        "is_clear": False,
        "interpreted_question": "What is the legal status and policy history of DACA?",
        "material_uncertainties": ["Timeframe undefined: current legal status vs historical 2012 enactment"],
        "clarification_question": "Which timeframe or legal question are you asking about regarding DACA?",
        "clarification_choices": [
            "Current 2026 legal status and active court rulings",
            "Historical 2012 executive creation and original criteria",
            "Legislative reform proposals and Dream Act history"
        ],
        "subclaims": [
            {
                "original_wording": "What is going on with DACA?",
                "normalized_assertion": "DACA legal status is under current federal court dispute.",
                "claim_type": "factual",
                "explicit_date": None,
                "explicit_location": "United States",
                "explicit_quantity": None,
                "qualifications": None
            }
        ]
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_r1)
        r1_resp = await adapter.clarify_inquiry(text=text, round_index=1)

    assert r1_resp.clarification_needed is True
    assert r1_resp.choices is not None
    assert len(r1_resp.choices) == 3
    assert "Current 2026 legal status" in r1_resp.choices[0]

    # User specifically picks Choice 1: Current 2026 status
    chosen = r1_resp.choices[0]
    exchange = ClarificationExchange(
        round_index=1,
        question=r1_resp.question,
        selected_choice=chosen,
    )

    # Round 2 response must preserve current-status scope without converting to historical 2012 creation
    mock_r2 = {
        "purpose": "check_claim",
        "is_clear": True,
        "interpreted_question": "What is the current 2026 legal status of the DACA program under active federal court injunctions?",
        "material_uncertainties": ["Pending Supreme Court appeal status not yet decided"],
        "clarification_question": None,
        "clarification_choices": None,
        "subclaims": [
            {
                "original_wording": "What is going on with DACA?",
                "normalized_assertion": "The DACA program is currently operating under federal court injunctions allowing renewals in 2026.",
                "claim_type": "factual",
                "explicit_date": "2026",
                "explicit_location": "United States",
                "explicit_quantity": None,
                "qualifications": "limited to renewals"
            }
        ]
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_r2)
        r2_resp = await adapter.clarify_inquiry(
            text=text,
            round_index=2,
            exchanges=[exchange],
        )

    assert r2_resp.is_clear is True
    assert r2_resp.clarification_needed is False
    assert "current" in r2_resp.interpreted_question.lower() or "2026" in r2_resp.interpreted_question
    assert "2012" not in r2_resp.interpreted_question
    assert len(r2_resp.subclaims) >= 1
    assert r2_resp.subclaims[0].claim_type == ClaimType.FACTUAL


# ===========================================================================
# 3. Acceptance Check 2: No Invented Particulars (Beef & Compound Claims)
# ===========================================================================

@pytest.mark.anyio
async def test_acceptance_check_2_no_invented_particulars_beef():
    """Beef inquiry must retain unspecified substance as unknown and preserve Europe without guessing EU."""
    adapter = GeminiAdapter()
    text = "Europe bans American beef because of dangerous chemicals."

    mock_llm_payload = {
        "purpose": "check_claim",
        "is_clear": False,
        "interpreted_question": "Did European countries ban American beef over specific chemical substances?",
        "material_uncertainties": [
            "Specific substance in beef was not stated by the author (chemicals unspecified)",
            "Jurisdiction Europe as a whole vs European Union statutory framework unconfirmed"
        ],
        "clarification_question": "Which specific substance or regulatory restriction would you like to investigate?",
        "clarification_choices": [
            "Bovine growth hormones (1989 EU hormone ban)",
            "Chlorine and antimicrobial carcass washes",
            "General chemical food additives and veterinary drugs"
        ],
        "subclaims": [
            {
                "original_wording": "Europe bans American beef",
                "normalized_assertion": "European countries prohibit imports of American beef.",
                "claim_type": "factual",
                "explicit_date": None,
                "explicit_location": "Europe",
                "explicit_quantity": None,
                "qualifications": None
            },
            {
                "original_wording": "because of dangerous chemicals",
                "normalized_assertion": "The beef import restriction is caused by the presence of dangerous chemical substances.",
                "claim_type": "causal",
                "explicit_date": None,
                "explicit_location": None,
                "explicit_quantity": None,
                "qualifications": "unspecified chemical substances"
            }
        ]
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_llm_payload)
        resp = await adapter.clarify_inquiry(text=text, round_index=1)

    # 1. Unspecified substance is listed in material uncertainties, not silently invented
    assert any("not stated" in u.lower() or "unspecified" in u.lower() for u in resp.material_uncertainties)
    # 2. Europe vs EU distinction is preserved in uncertainties
    assert any("europe" in u.lower() for u in resp.material_uncertainties)
    # 3. Compound causal relationship is preserved across subclaims
    assert len(resp.subclaims) == 2
    claim_types = [c.claim_type for c in resp.subclaims]
    assert ClaimType.FACTUAL in claim_types
    assert ClaimType.CAUSAL in claim_types
    # Subclaims retain original wording verbatim
    assert resp.subclaims[0].original_wording == "Europe bans American beef"
    assert resp.subclaims[1].original_wording == "because of dangerous chemicals"


# ===========================================================================
# 4. Acceptance Check 3: Bounded Clarification (Exactly 3 Choices, Max 2 Rounds)
# ===========================================================================

@pytest.mark.anyio
async def test_acceptance_check_3_clear_input_bypasses_redundant_clarification():
    """A clear, concrete factual assertion proceeds to confirmation without clarifying questions."""
    adapter = GeminiAdapter()
    text = "Mayor Karen Bass was sworn in as the 43rd Mayor of Los Angeles on December 11, 2022."

    mock_llm_clear = {
        "purpose": "check_claim",
        "is_clear": True,
        "interpreted_question": "Was Karen Bass sworn in as the 43rd Mayor of Los Angeles on December 11, 2022?",
        "material_uncertainties": [],
        "clarification_question": None,
        "clarification_choices": None,
        "subclaims": [
            {
                "original_wording": "Mayor Karen Bass was sworn in as the 43rd Mayor of Los Angeles on December 11, 2022.",
                "normalized_assertion": "Karen Bass was sworn in as the 43rd Mayor of Los Angeles on December 11, 2022.",
                "claim_type": "factual",
                "explicit_date": "December 11, 2022",
                "explicit_location": "Los Angeles",
                "explicit_quantity": "43rd",
                "qualifications": None
            }
        ]
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_llm_clear)
        resp = await adapter.clarify_inquiry(text=text, round_index=1)

    assert resp.is_clear is True
    assert resp.clarification_needed is False
    assert resp.question is None
    assert resp.choices is None
    assert "Mayor of Los Angeles" in resp.interpreted_question


@pytest.mark.anyio
async def test_acceptance_check_3_full_two_round_clarification_flow_and_hard_ceiling():
    """Test full 2-round clarification flow:
    - Round 1 (0 exchanges): unclear -> clarification_needed=True, max_rounds_reached=False.
    - Round 2 (1 exchange): unclear -> clarification_needed=True, max_rounds_reached=False, returning a second question.
    - Round 3 (2 exchanges): even if LLM returns is_clear=False, hard ceiling enforces max_rounds_reached=True and terminates.
    """
    adapter = GeminiAdapter()
    text = "The new regulation will harm businesses."

    mock_r1 = {
        "purpose": "check_claim",
        "is_clear": False,
        "interpreted_question": "Does the new regulation cause economic harm to businesses?",
        "material_uncertainties": ["Regulation name not specified"],
        "clarification_question": "Which specific regulation are you inquiring about?",
        "clarification_choices": ["Local zoning regulation", "State tax regulation", "Federal environmental rule"],
        "subclaims": []
    }

    mock_r2 = {
        "purpose": "check_claim",
        "is_clear": False,
        "interpreted_question": "Does the local zoning regulation cause economic harm to small businesses?",
        "material_uncertainties": ["Industry sector not defined"],
        "clarification_question": "Which business sector would you like to investigate?",
        "clarification_choices": ["Retail storefronts", "Restaurants and hospitality", "Manufacturing and warehousing"],
        "subclaims": []
    }

    mock_r3_stubborn = {
        "purpose": "check_claim",
        "is_clear": False,
        "interpreted_question": "Does the local zoning regulation cause economic harm to restaurants in Los Angeles?",
        "material_uncertainties": ["Specific municipal code section unstated"],
        "clarification_question": "Which city code section?",
        "clarification_choices": ["Section A", "Section B", "Section C"],
        "subclaims": [
            {
                "original_wording": "The new regulation will harm businesses.",
                "normalized_assertion": "The local zoning regulation causes economic harm to restaurants.",
                "claim_type": "prediction",
                "explicit_date": None,
                "explicit_location": "Los Angeles",
                "explicit_quantity": None,
                "qualifications": None
            }
        ]
    }

    with patch.object(adapter, "_client") as mock_client:
        # Round 1
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_r1)
        r1_resp = await adapter.clarify_inquiry(text=text, round_index=1, exchanges=[])
        assert r1_resp.clarification_needed is True
        assert r1_resp.max_rounds_reached is False
        assert r1_resp.round_index == 1
        assert r1_resp.question == "Which specific regulation are you inquiring about?"
        assert r1_resp.choices is not None
        assert len(r1_resp.choices) == 3

        # Round 2: 1 prior exchange provided -> second question returned
        exchanges_r2 = [
            ClarificationExchange(
                round_index=1,
                question=r1_resp.question,
                selected_choice=r1_resp.choices[0],
            )
        ]
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_r2)
        r2_resp = await adapter.clarify_inquiry(text=text, round_index=2, exchanges=exchanges_r2)
        assert r2_resp.clarification_needed is True
        assert r2_resp.max_rounds_reached is False
        assert r2_resp.round_index == 2
        assert r2_resp.question == "Which business sector would you like to investigate?"
        assert r2_resp.choices is not None
        assert len(r2_resp.choices) == 3

        # Round 3: 2 prior exchanges provided -> Hard ceiling reached (3rd round impossible)!
        exchanges_r3 = exchanges_r2 + [
            ClarificationExchange(
                round_index=2,
                question=r2_resp.question,
                selected_choice=r2_resp.choices[1],
            )
        ]
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_r3_stubborn)
        r3_resp = await adapter.clarify_inquiry(text=text, round_index=3, exchanges=exchanges_r3)
        assert r3_resp.max_rounds_reached is True
        assert r3_resp.clarification_needed is False
        assert r3_resp.is_clear is True
        assert r3_resp.round_index == 3
        assert r3_resp.question is None
        assert r3_resp.choices is None
        assert len(r3_resp.material_uncertainties) >= 1


@pytest.mark.anyio
async def test_clarification_raises_when_fewer_than_three_choices():
    """When clarification_needed is True and model returns fewer than 3 choices, GeminiAdapterError is raised."""
    adapter = GeminiAdapter()
    text = "Some ambiguous text"
    mock_bad_choices = {
        "purpose": "check_claim",
        "is_clear": False,
        "interpreted_question": "Interpreted question",
        "material_uncertainties": [],
        "clarification_question": "Which aspect?",
        "clarification_choices": ["Only choice 1", "Only choice 2"],
        "subclaims": []
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_bad_choices)
        with pytest.raises(GeminiAdapterError) as exc_info:
            await adapter.clarify_inquiry(text=text, round_index=1)
        assert "fewer than 3 valid choices" in str(exc_info.value)


@pytest.mark.anyio
async def test_clarification_raises_when_question_missing():
    """When clarification_needed is True and model omits clarification_question, GeminiAdapterError is raised."""
    adapter = GeminiAdapter()
    text = "Some ambiguous text"
    mock_no_question = {
        "purpose": "check_claim",
        "is_clear": False,
        "interpreted_question": "Interpreted question",
        "material_uncertainties": [],
        "clarification_question": None,
        "clarification_choices": ["Choice 1", "Choice 2", "Choice 3"],
        "subclaims": []
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_no_question)
        with pytest.raises(GeminiAdapterError) as exc_info:
            await adapter.clarify_inquiry(text=text, round_index=1)
        assert "omitted a clarifying question" in str(exc_info.value)


@pytest.mark.anyio
async def test_clarification_preserves_empty_subclaims_without_fabrication():
    """When analysis.subclaims is empty, response.subclaims is [] and no subclaim is fabricated."""
    adapter = GeminiAdapter()
    text = "Unclear statement without extractable claims"
    mock_empty_subclaims = {
        "purpose": "check_claim",
        "is_clear": True,
        "interpreted_question": "What is being claimed?",
        "material_uncertainties": ["No checkable factual claims extracted"],
        "clarification_question": None,
        "clarification_choices": None,
        "subclaims": []
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_empty_subclaims)
        resp = await adapter.clarify_inquiry(text=text, round_index=1)

    assert resp.subclaims == []


@pytest.mark.anyio
async def test_acceptance_check_3_exactly_three_choices_normalized():
    """Ensure normalization guarantees exactly three coherent choices when clarification is needed."""
    adapter = GeminiAdapter()
    text = "Obama executive order legality."

    # Model returns 4 choices
    mock_llm_4_choices = {
        "purpose": "check_claim",
        "is_clear": False,
        "interpreted_question": "What is the constitutional legality of President Obama's executive actions?",
        "material_uncertainties": ["Executive order number not specified"],
        "clarification_question": "Which executive action would you like to examine?",
        "clarification_choices": ["DACA (2012)", "DAPA (2014)", "Clean Power Plan (2015)", "Extra choice 4"],
        "subclaims": []
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_llm_4_choices)
        resp = await adapter.clarify_inquiry(text=text, round_index=1)

    assert resp.clarification_needed is True
    assert resp.choices is not None
    assert len(resp.choices) == 3
    assert resp.choices[0] == "DACA (2012)"
    assert resp.choices[1] == "DAPA (2014)"
    assert resp.choices[2] == "Clean Power Plan (2015)"


# ===========================================================================
# 5. Acceptance Check 4: State & Spending (No Search Before Confirmation)
# ===========================================================================

@pytest.mark.anyio
async def test_acceptance_check_4_no_search_requests_during_clarification():
    import app.main as app_main

    mock_provider = AsyncMock()
    mock_fetcher = AsyncMock()

    with patch.object(app_main.research_orchestrator, "_search_provider", mock_provider), \
         patch.object(app_main.research_orchestrator, "_fetcher", mock_fetcher), \
         patch("app.main.gemini.clarify_inquiry") as mock_clarify:

        mock_clarify.return_value = ClarificationResponse(
            submitted_text="Unclear topic",
            purpose=InvestigationPurpose.CHECK_CLAIM,
            is_clear=False,
            clarification_needed=True,
            round_index=1,
            max_rounds_reached=False,
            question="Which aspect?",
            choices=["A", "B", "C"],
            interpreted_question="Interpreted topic",
            material_uncertainties=["Uncertainty 1"],
            subclaims=[],
            status_message="Clarification requested",
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/clarify", json={"text": "Unclear topic"})

        assert resp.status_code == 200
        # CRITICAL: Verify ZERO outbound search requests or fetcher requests were made
        assert mock_provider.search.await_count == 0
        assert mock_fetcher.fetch.await_count == 0


# ===========================================================================
# 6. Acceptance Check 5: Honest UI & Purpose Limitations
# ===========================================================================

@pytest.mark.anyio
async def test_acceptance_check_5_context_and_origin_honesty_limitation_note():
    """Context and origin tracing inquiries are stored honestly and display limitation notes."""
    adapter = GeminiAdapter()

    # User asks for origin tracing of a rumor
    text = "Where did the rumor that windmills cause cancer come from?"

    mock_llm_origin = {
        "purpose": "trace_origin",
        "is_clear": True,
        "interpreted_question": "What is the historical origin and earliest documented appearance of the claim that windmills cause cancer?",
        "material_uncertainties": ["First public speech reference vs earlier social media origin"],
        "clarification_question": None,
        "clarification_choices": None,
        "subclaims": [
            {
                "original_wording": "Where did the rumor that windmills cause cancer come from?",
                "normalized_assertion": "The claim that windmills cause cancer originated in public political speeches in April 2019.",
                "claim_type": "factual",
                "explicit_date": "April 2019",
                "explicit_location": None,
                "explicit_quantity": None,
                "qualifications": "earliest major documented transcript"
            }
        ]
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_llm_origin)
        resp = await adapter.clarify_inquiry(text=text, round_index=1)

    assert resp.purpose == InvestigationPurpose.TRACE_ORIGIN
    assert resp.limitation_note is not None
    assert "Dedicated context and origin tracing pipelines are planned" in resp.limitation_note
    assert resp.subclaims[0].claim_type == ClaimType.FACTUAL


@pytest.mark.anyio
async def test_clarify_explicit_broad_inquiry():
    """When user requests broad inquiry, adapter confirms broad scope without further questions."""
    adapter = GeminiAdapter()
    text = "The new city ordinance and its effects."

    mock_broad_llm = {
        "purpose": "understand_context",
        "is_clear": True,
        "interpreted_question": "What are the overall legal and operational effects of the new city ordinance?",
        "material_uncertainties": ["Broad scope: includes residential, commercial, and enforcement aspects"],
        "clarification_question": None,
        "clarification_choices": None,
        "subclaims": [
            {
                "original_wording": "The new city ordinance and its effects.",
                "normalized_assertion": "The city ordinance introduces new municipal compliance regulations.",
                "claim_type": "factual",
                "explicit_date": None,
                "explicit_location": None,
                "explicit_quantity": None,
                "qualifications": None
            }
        ]
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.models.generate_content.return_value = _mock_gemini_response(mock_broad_llm)
        resp = await adapter.clarify_inquiry(
            text=text,
            round_index=1,
            explicit_broad=True,
        )

    assert resp.is_clear is True
    assert resp.clarification_needed is False
    assert resp.max_rounds_reached is True
    assert "overall" in resp.interpreted_question.lower() or "broad" in str(resp.material_uncertainties).lower()
