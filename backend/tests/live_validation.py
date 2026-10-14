r"""Live validation script for ScoopScope Milestone 1.

Run AFTER configuring GEMINI_API_KEY in backend/.env.

Usage:
    cd c:\Users\minhb\OneDrive\Desktop\Projects\ScoopScope\backend
    .venv\Scripts\python.exe -m tests.live_validation

This script:
  1. Checks the /api/health endpoint for credential status.
  2. Tests missing-credentials error path (mocked — does not touch the key).
  3. Sends three synthetic inputs through /api/extract and evaluates
     the extraction quality against explicit expectations.
  4. Reports pass/fail for each check.

All provider responses are LIVE — no mocks for the extraction tests.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from httpx import ASGITransport, AsyncClient

# Import the app — this loads settings from .env.
from app.main import app


# ---------------------------------------------------------------------------
# Synthetic test inputs (clearly labelled)
# ---------------------------------------------------------------------------

INPUT_1_MIXED = {
    "label": "INPUT 1: Mixed factual assertions and opinion",
    "text": (
        "The City of Los Angeles covers 469 square miles and has a population "
        "of roughly 3.9 million people according to the 2020 Census. "
        "It is, in my opinion, the most culturally vibrant city in the United States."
    ),
    "source_url": None,
    "checks": [
        ("At least 2 claims extracted", lambda d: len(d["claims"]) >= 2),
        (
            "At least one factual claim",
            lambda d: any(c["claim_type"] == "factual" for c in d["claims"]),
        ),
        (
            "At least one opinion claim",
            lambda d: any(c["claim_type"] == "opinion" for c in d["claims"]),
        ),
        (
            "Quantity preserved (469 or 3.9 million)",
            lambda d: any(
                c.get("explicit_quantity") and ("469" in c["explicit_quantity"] or "3.9" in c["explicit_quantity"])
                for c in d["claims"]
            ),
        ),
        (
            "Location 'Los Angeles' extracted",
            lambda d: any(
                c.get("explicit_location") and "Los Angeles" in c["explicit_location"]
                for c in d["claims"]
            ),
        ),
        (
            "No invented details (no claims with locations not in input)",
            lambda d: all(
                c.get("explicit_location") is None
                or any(
                    loc in c["explicit_location"]
                    for loc in ["Los Angeles", "United States"]
                )
                for c in d["claims"]
            ),
        ),
    ],
}

INPUT_2_AMBIGUOUS_LA = {
    "label": "INPUT 2: Ambiguous 'Los Angeles' reference (city vs county)",
    "text": (
        "Los Angeles approved a new transit expansion plan last Tuesday. "
        "The plan will add three new rail lines by 2035."
    ),
    "source_url": None,
    "checks": [
        ("At least 1 claim extracted", lambda d: len(d["claims"]) >= 1),
        (
            "Location says 'Los Angeles' (not resolved to city or county)",
            lambda d: any(
                c.get("explicit_location") and "Los Angeles" in c["explicit_location"]
                for c in d["claims"]
            ),
        ),
        (
            "Does NOT invent 'City of' or 'County of' disambiguation",
            lambda d: all(
                c.get("explicit_location") is None
                or ("City of" not in c["explicit_location"] and "County of" not in c["explicit_location"])
                for c in d["claims"]
            ),
        ),
        (
            "Date '2035' extracted",
            lambda d: any(
                c.get("explicit_date") and "2035" in c["explicit_date"]
                for c in d["claims"]
            ),
        ),
        (
            "Quantity 'three' or '3' extracted",
            lambda d: any(
                c.get("explicit_quantity") and ("three" in c["explicit_quantity"].lower() or "3" in c["explicit_quantity"])
                for c in d["claims"]
            ),
        ),
    ],
}

INPUT_3_COMPOUND = {
    "label": "INPUT 3: Compound claim with number, date, attribution, and qualification",
    "text": (
        "According to the LA Times, Mayor Bass stated in March 2025 that "
        "the city had reduced homelessness by approximately 14%, although "
        "critics argue this figure relies on a narrowed counting methodology."
    ),
    "source_url": "https://example.com/latimes-article",
    "checks": [
        ("At least 2 claims extracted (assertion + criticism)", lambda d: len(d["claims"]) >= 2),
        (
            "Date 'March 2025' extracted",
            lambda d: any(
                c.get("explicit_date") and "2025" in c["explicit_date"]
                for c in d["claims"]
            ),
        ),
        (
            "Quantity '14%' extracted",
            lambda d: any(
                c.get("explicit_quantity") and "14" in c["explicit_quantity"]
                for c in d["claims"]
            ),
        ),
        (
            "Qualification preserved (approximately / narrowed methodology)",
            lambda d: any(
                c.get("qualifications") and (
                    "approximate" in c["qualifications"].lower()
                    or "narrowed" in c["qualifications"].lower()
                    or "methodology" in c["qualifications"].lower()
                    or "critics" in c["qualifications"].lower()
                )
                for c in d["claims"]
            ),
        ),
        (
            "Source URL echoed back",
            lambda d: d.get("source_url") == "https://example.com/latimes-article",
        ),
        (
            "No invented sources or scores",
            lambda d: all(
                "verified" not in json.dumps(c).lower()
                and "score" not in json.dumps(c).lower()
                and "confidence" not in json.dumps(c).lower()
                for c in d["claims"]
            ),
        ),
    ],
}

LIVE_INPUTS = [INPUT_1_MIXED, INPUT_2_AMBIGUOUS_LA, INPUT_3_COMPOUND]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_validation() -> bool:
    all_passed = True
    results_summary: list[dict[str, Any]] = []

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=60.0,
    ) as client:
        # -- Step 1: Health check --
        print("=" * 70)
        print("STEP 1: Health check")
        print("=" * 70)
        resp = await client.get("/api/health")
        health = resp.json()
        print(f"  Status: {health['status']}")
        print(f"  Credentials configured: {health['credentials_configured']}")
        print(f"  Model: {health['model']}")

        if not health["credentials_configured"]:
            print("\n  [FAIL] GEMINI_API_KEY is not set in backend/.env")
            print("         Cannot proceed with live validation.")
            print(f"         File: c:\\Users\\minhb\\Projects\\ScoopScope\\backend\\.env")
            return False

        # -- Step 2: Missing-credentials error path --
        print()
        print("=" * 70)
        print("STEP 2: Missing-credentials error (simulated)")
        print("=" * 70)
        from unittest.mock import patch
        with patch("app.main.gemini._client", None):
            resp = await client.post("/api/extract", json={"text": "test claim"})
        cred_ok = resp.status_code == 503 and "credentials" in resp.json().get("error", "").lower()
        print(f"  Status code: {resp.status_code} (expected 503)")
        print(f"  Error message mentions credentials: {cred_ok}")
        if cred_ok:
            print("  [PASS]")
        else:
            print("  [FAIL]")
            all_passed = False

        # -- Step 3: Live extraction tests --
        for i, test_input in enumerate(LIVE_INPUTS, 1):
            if i > 1:
                # Free-tier rate limit is 5 RPM.
                # A 25s cooldown guarantees requests stay well below the 5 RPM quota.
                print("  [INFO] Pausing 25s for free-tier rate limit cooldown...")
                await asyncio.sleep(25)

            print()
            print("=" * 70)
            print(f"STEP 3.{i}: {test_input['label']}")
            print("=" * 70)
            print(f"  Input text: {test_input['text'][:100]}...")

            resp = await client.post(
                "/api/extract",
                json={
                    "text": test_input["text"],
                    "source_url": test_input.get("source_url"),
                },
            )

            if resp.status_code != 200:
                print(f"  [FAIL] HTTP {resp.status_code}: {resp.json()}")
                all_passed = False
                results_summary.append({
                    "input": test_input["label"],
                    "status": "HTTP_ERROR",
                    "code": resp.status_code,
                })
                continue

            data = resp.json()
            print(f"  Claims extracted: {len(data['claims'])}")
            print(f"  Submission ID: {data['submission_id']}")

            # Print each claim for inspection
            for j, claim in enumerate(data["claims"], 1):
                print(f"\n  Claim #{j}:")
                print(f"    Type: {claim['claim_type']}")
                print(f"    Original: \"{claim['original_wording']}\"")
                print(f"    Normalized: \"{claim['normalized_assertion']}\"")
                if claim.get("explicit_date"):
                    print(f"    Date: {claim['explicit_date']}")
                if claim.get("explicit_location"):
                    print(f"    Location: {claim['explicit_location']}")
                if claim.get("explicit_quantity"):
                    print(f"    Quantity: {claim['explicit_quantity']}")
                if claim.get("qualifications"):
                    print(f"    Qualifications: {claim['qualifications']}")

            # Run checks
            print(f"\n  Checks:")
            input_passed = True
            for check_name, check_fn in test_input["checks"]:
                try:
                    passed = check_fn(data)
                except Exception as exc:
                    passed = False
                    print(f"    [FAIL] {check_name} — check error: {exc}")
                    continue

                icon = "[PASS]" if passed else "[FAIL]"
                print(f"    {icon} {check_name}")
                if not passed:
                    input_passed = False
                    all_passed = False

            results_summary.append({
                "input": test_input["label"],
                "status": "PASS" if input_passed else "PARTIAL_FAIL",
                "claims_count": len(data["claims"]),
            })

    # -- Summary --
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for r in results_summary:
        icon = "[PASS]" if r["status"] == "PASS" else "[FAIL]"
        print(f"  {icon} {r['input']} — {r['status']}")
        if "claims_count" in r:
            print(f"      Claims: {r['claims_count']}")

    print()
    if all_passed:
        print("[SUCCESS] ALL LIVE VALIDATION CHECKS PASSED")
    else:
        print("[WARNING] SOME CHECKS FAILED — see details above")

    return all_passed


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    passed = asyncio.run(run_validation())
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
