"""Fixture data for tests.

IMPORTANT: These fixtures are ONLY for automated tests.  They are never
used in the normal user-facing flow.  The application always calls the
real Gemini API in production.  Tests that use these fixtures are clearly
labelled as "fixture-based" in test output and in STATUS.md.
"""

# A realistic LLM response for a multi-claim input.
MULTI_CLAIM_LLM_RESPONSE = {
    "claims": [
        {
            "original_wording": "Los Angeles has a population of about 4 million people",
            "normalized_assertion": "The population of Los Angeles is approximately 4 million.",
            "claim_type": "factual",
            "explicit_date": None,
            "explicit_location": "Los Angeles",
            "explicit_quantity": "about 4 million people",
            "qualifications": "approximate (\"about\")",
        },
        {
            "original_wording": "it will grow to 5 million by 2030",
            "normalized_assertion": "The population of Los Angeles will reach 5 million by 2030.",
            "claim_type": "prediction",
            "explicit_date": "2030",
            "explicit_location": None,
            "explicit_quantity": "5 million",
            "qualifications": None,
        },
        {
            "original_wording": "I think the weather there is the best in the country",
            "normalized_assertion": "Los Angeles has the best weather in the country.",
            "claim_type": "opinion",
            "explicit_date": None,
            "explicit_location": None,
            "explicit_quantity": None,
            "qualifications": "subjective (\"I think\")",
        },
    ]
}

# An empty-claims response (input contained no extractable claims).
EMPTY_CLAIMS_LLM_RESPONSE = {"claims": []}

# Malformed responses for testing validation.
MALFORMED_RESPONSES = {
    "not_json": "This is not JSON at all",
    "missing_claims_key": {"results": []},
    "wrong_claim_type": {
        "claims": [
            {
                "original_wording": "test",
                "normalized_assertion": "test",
                "claim_type": "INVALID_TYPE",
            }
        ]
    },
    "missing_required_field": {
        "claims": [
            {
                "original_wording": "test",
                # missing normalized_assertion
                "claim_type": "factual",
            }
        ]
    },
}

# Input texts for testing.
SAMPLE_INPUT = (
    "Los Angeles has a population of about 4 million people. "
    "It will grow to 5 million by 2030. "
    "I think the weather there is the best in the country."
)

OVERSIZED_INPUT = "x" * 10_001
