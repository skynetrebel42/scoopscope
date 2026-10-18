"""Deterministic jurisdiction classification and ambiguity detection for ScoopScope.

Milestone 4C (Decision 010):
- Classifies source URLs deterministically based on hostname into official government tiers.
- Never uses LLMs to guess or fabricate government jurisdiction credentials.
- Detects civic inquiry ambiguity between City of Los Angeles and Los Angeles County.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import TypedDict


class JurisdictionInfo(TypedDict):
    code: str
    label: str


# ---------------------------------------------------------------------------
# Official Domain Sets
# ---------------------------------------------------------------------------

LA_CITY_DOMAINS: set[str] = {
    "lacity.gov",
    "lacity.org",
    "lapdonline.org",
    "ladwp.com",
    "lafd.org",
    "lacontroller.org",
}

LA_COUNTY_DOMAINS: set[str] = {
    "lacounty.gov",
    "lasd.org",
    "lavote.gov",
}

LA_REGIONAL_DOMAINS: set[str] = {
    "metro.net",
    "lausd.net",
    "lahsa.org",
    "aqmd.gov",
    "mwdh2o.com",
}


def _matches_domain_set(host: str, domain_set: set[str]) -> bool:
    """Check if host exactly matches or is a subdomain of any domain in domain_set."""
    for dom in domain_set:
        if host == dom or host.endswith("." + dom):
            return True
    return False


def classify_source_jurisdiction(url: str | None) -> JurisdictionInfo | None:
    """Classify a source URL deterministically into a verified official jurisdiction.

    Returns:
        {"code": "la_city", "label": "City of LA Official"}
        {"code": "la_county", "label": "LA County Official"}
        {"code": "la_regional", "label": "LA Regional Agency"}
        {"code": "ca_state", "label": "CA State Official"}
        {"code": "us_gov", "label": "Government Official"}
        or None if not a recognized government/official domain.
    """
    if not url or not isinstance(url, str):
        return None

    cleaned_url = url.strip()
    if not cleaned_url:
        return None

    try:
        parsed = urllib.parse.urlparse(cleaned_url)
        hostname = parsed.hostname
        if not hostname and parsed.netloc:
            hostname = parsed.netloc.split(":")[0]
        if not hostname:
            return None

        host = hostname.lower().strip(".")
        if host.startswith("www."):
            host = host[4:]

        if not host:
            return None

        # 1. City of Los Angeles official domains
        if _matches_domain_set(host, LA_CITY_DOMAINS):
            return {"code": "la_city", "label": "City of LA Official"}

        # 2. Los Angeles County official domains
        if _matches_domain_set(host, LA_COUNTY_DOMAINS):
            return {"code": "la_county", "label": "LA County Official"}

        # 3. LA Regional / Joint agencies (evaluated before *.gov because aqmd.gov is regional)
        if _matches_domain_set(host, LA_REGIONAL_DOMAINS):
            return {"code": "la_regional", "label": "LA Regional Agency"}

        # 4. California State official domains (*.ca.gov)
        if host == "ca.gov" or host.endswith(".ca.gov"):
            return {"code": "ca_state", "label": "CA State Official"}

        # 5. US Government / Other Government official domains (*.gov, *.mil)
        if host == "gov" or host.endswith(".gov") or host == "mil" or host.endswith(".mil"):
            return {"code": "us_gov", "label": "Government Official"}

        # 6. Non-government, commercial, news, or third-party domains
        return None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# LA Ambiguity Detection
# ---------------------------------------------------------------------------

LA_REFERENCE_PATTERN = re.compile(r"(?:\b(?:la|los\s+angeles)\b|\bl\.a\.(?!\w))", re.IGNORECASE)

EXPLICIT_CITY_PATTERNS = [
    re.compile(r"\bcity\s+of\s+(?:la|l\.a\.|los\s+angeles)(?!\w)", re.IGNORECASE),
    re.compile(r"(?:\bla|\bl\.a\.)\s+city\b", re.IGNORECASE),
    re.compile(r"\bmayor\b", re.IGNORECASE),
    re.compile(r"\blapd\b", re.IGNORECASE),
    re.compile(r"\bladwp\b", re.IGNORECASE),
    re.compile(r"\blafd\b", re.IGNORECASE),
    re.compile(r"\blacontroller\b", re.IGNORECASE),
    re.compile(r"\bcity\s+council\b", re.IGNORECASE),
    re.compile(r"\bcity\s+attorney\b", re.IGNORECASE),
    re.compile(r"\blacity\b", re.IGNORECASE),
]

EXPLICIT_COUNTY_PATTERNS = [
    re.compile(r"(?:\bla|\bl\.a\.|los\s+angeles)\s+county\b", re.IGNORECASE),
    re.compile(r"\bcounty\s+of\s+(?:la|l\.a\.|los\s+angeles)(?!\w)", re.IGNORECASE),
    re.compile(r"\blasd\b", re.IGNORECASE),
    re.compile(r"\bsheriff\b", re.IGNORECASE),
    re.compile(r"\bboard\s+of\s+supervisors\b", re.IGNORECASE),
    re.compile(r"\bsupervisor\b", re.IGNORECASE),
    re.compile(r"\bdistrict\s+attorney\b", re.IGNORECASE),
    re.compile(r"\bunincorporated\b", re.IGNORECASE),
    re.compile(r"\blacounty\b", re.IGNORECASE),
    re.compile(r"\blavote\b", re.IGNORECASE),
]


def detect_la_jurisdiction_ambiguity(text: str | None) -> bool:
    """Detect if inquiry refers ambiguously to 'LA' or 'Los Angeles' without specifying City vs County.

    Returns True if:
      - The text contains 'LA', 'L.A.', or 'Los Angeles' as a distinct token/phrase, AND
      - Does NOT contain explicit City markers (e.g. 'City of LA', 'LAPD', 'LADWP', 'City Council')
        or County markers (e.g. 'LA County', 'LASD', 'Board of Supervisors', 'unincorporated').

    Returns False otherwise.
    """
    if not text or not isinstance(text, str):
        return False

    cleaned = text.strip()
    if not cleaned:
        return False

    # Must contain a reference to LA / Los Angeles
    if not LA_REFERENCE_PATTERN.search(cleaned):
        return False

    # If explicit City markers are present, not ambiguous
    for pattern in EXPLICIT_CITY_PATTERNS:
        if pattern.search(cleaned):
            return False

    # If explicit County markers are present, not ambiguous
    for pattern in EXPLICIT_COUNTY_PATTERNS:
        if pattern.search(cleaned):
            return False

    return True
