# ScoopScope — Evidence Search & Safe Retrieval Design Contract

**Document Version:** 1.0  
**Status:** Approved Specification (Milestone 2A)  
**Implementation Target:** Milestone 2B  

---

## 1. Core Principle & Evidence Cardinal Rule

> **A search engine result or snippet is NEVER verified evidence.**
> 
> A search result only proves that a search engine indexed a string of text associated with a URL. It does not prove the page currently contains that text, that the context supports the claim, or that the publisher is an independent primary source.
>
> **Invariant:** Future investigation verdicts and findings MUST cite only passages extracted from actual sources in `retrieved` status that have been safely fetched, parsed, and examined. If evidence cannot be retrieved, the claim status is strictly **`unresolved`**, never false.

---

## 2. Replaceable `SearchProvider` Interface

All search engine integrations must sit behind a runtime-replaceable Python `Protocol`. Application code, query planners, and evidence orchestrators must depend strictly on the protocol, never concrete provider implementations.

```python
from typing import Protocol, runtime_checkable
from pydantic import BaseModel, Field


class RawSearchResult(BaseModel):
    """Raw result returned by an external search engine."""
    title: str
    url: str
    snippet: str
    rank: int = Field(ge=1, description="1-based search result position")
    engine: str = Field(description="Search provider identifier, e.g. 'serper', 'mock'")


@runtime_checkable
class SearchProvider(Protocol):
    """Abstract search provider protocol for swappable search backends."""

    async def search(self, query: str, max_results: int = 5) -> list[RawSearchResult]:
        """Execute query against search backend and return ranked results.
        
        Args:
            query: Plaintext search query string.
            max_results: Upper bound on returned items (bounded by provider budget).

        Returns:
            List of raw search hits.
            
        Raises:
            SearchProviderError: On upstream rate limit, network failure, or credential issue.
        """
        ...
```

### Supported & Planned Implementations
1. `MockSearchProvider`: In-memory deterministic fixture provider for all automated unit/integration tests (zero external network, zero billing).
2. `SerperSearchProvider`: Planned provider calling Serper (Google Search API) using bounded timeouts and retries.
3. Alternative providers (e.g., SearXNG, Bing) can be introduced by fulfilling `SearchProvider` without modifying domain logic.

---

## 3. Four-Tier Distinct Data Records

To prevent conflating search hits with examined evidence, the pipeline maintains four strictly separated record layers:

```
[ Claim ] ──> [ 1. ClaimLinkedQuery ] ──> [ 2. SearchResultHit ] ──> [ 3. RetrievedSource ] ──> [ 4. EvidencePassage ]
```

### 3.1. `ClaimLinkedQuery`
The query generated to find evidence for a specific claim.
```python
class ClaimLinkedQuery(BaseModel):
    query_id: str
    claim_id: str                      # Foreign key to ExtractedClaim
    query_text: str                    # Target query string
    query_intent: str                  # e.g., 'primary_assertion', 'date_check', 'counter_evidence'
    generated_at: str                  # ISO 8601 UTC timestamp
```

### 3.2. `SearchResultHit`
The raw hit returned by the search provider. Marked explicitly as `snippet_only`.
```python
class SearchResultHit(BaseModel):
    result_id: str
    query_id: str                      # Foreign key to ClaimLinkedQuery
    claim_id: str                      # Foreign key to ExtractedClaim
    url: str                           # Candidate URL
    title: str
    snippet: str                       # Engine snippet (UNEXAMINED)
    rank: int
    engine: str
    is_snippet_only: bool = True       # Always True; NEVER counts as examined evidence
```

### 3.3. `RetrievedSource`
The full HTTP fetch audit record. Documents whether the destination was accessible and safely fetched.
```python
from enum import Enum

class SourceFetchState(str, Enum):
    RETRIEVED = "retrieved"                    # Safely fetched, verified text/html, body extracted
    INACCESSIBLE = "inaccessible"              # Network error, 4xx/5xx, timeout, robots.txt, paywall
    EXTRACTION_FAILED = "extraction_failed"    # HTTP 200, but text extraction yielded empty/unparseable text
    SSRF_BLOCKED = "ssrf_blocked"              # Destination resolved to private/forbidden IP or unsafe redirect

class RetrievedSource(BaseModel):
    source_id: str
    initial_url: str                           # URL requested from search hit
    final_url: str | None = None               # Post-redirect destination URL
    redirect_count: int = 0
    resolved_ip: str | None = None             # Public IP connected to (SSRF audit)
    status: SourceFetchState
    http_status_code: int | None = None
    content_type: str | None = None
    response_size_bytes: int = 0
    fetched_at: str                            # ISO 8601 UTC timestamp
    error_message: str | None = None
    extracted_text: str | None = None          # Cleaned plaintext (delimit as untrusted data)
```

### 3.4. `EvidencePassage`
An exact, verifiable quote extracted directly from the parsed body of a `RETRIEVED` source.
```python
class SourceDependence(str, Enum):
    PRIMARY = "primary"                        # First-hand reporting, government doc, data release
    SECONDARY_INDEPENDENT = "secondary_indep"  # Independent reporting citing own sources
    REPUBLICATION_WIRE = "republication_wire"  # Syndicated AP/Reuters copy or direct re-post
    UNKNOWN = "unknown"                        # Source dependence cannot be conclusively determined

class EvidencePassage(BaseModel):
    passage_id: str
    source_id: str                             # Foreign key to RetrievedSource (MUST be in RETRIEVED state)
    claim_id: str                              # Foreign key to ExtractedClaim
    source_url: str                            # Final canonical URL
    exact_passage: str                         # Verbatim excerpt from source body
    context_surrounding: str | None = None     # Paragraph context for disambiguation
    publication_date: str | None = None        # Date article/document was published (ISO 8601 or null)
    event_date: str | None = None              # Date the reported event occurred (ISO 8601 or null)
    source_dependence: SourceDependence = SourceDependence.UNKNOWN
    retrieved_at: str                          # ISO 8601 UTC timestamp
```

---

## 4. Source & Passage Lifecycle States

Every evidence candidate must transition through an explicit state machine:

| State | Definition | Permitted Role in Investigation Finding |
|---|---|---|
| `snippet_only` | Hit exists in search results; body unread | **Cannot support any verdict.** May only be used by orchestrator to prioritize which URLs to fetch. |
| `retrieved` | Safely fetched; status 200; HTML/text parsed | **Permitted to support findings.** Verbatim passages may be cited as verified evidence. |
| `inaccessible` | Blocked by network, timeout, HTTP 4xx/5xx, robots.txt, or SSRF gate | Recorded in audit trail. Triggers fallback or marks evidence as missing (`unresolved`). |
| `extraction_failed` | Connected, but content was DRM-locked, purely client-rendered canvas/JS, or unreadable | Recorded in audit trail. Treated as inaccessible evidence. |

---

## 5. Provenance & Anti-Circular Reporting Fields

Per AGENTS.md Evidence Rule #3 ("Repeated coverage of one original source is not independent corroboration"):
- **`source_dependence`**: Distinguishes primary documentation from syndication or aggregation.
- If Source A and Source B both copy a single wire dispatch without independent verification, they count as **one** evidence stream, not two corroborating sources.
- Where source lineage cannot be verified from the examined passage, `source_dependence` is explicitly recorded as `UNKNOWN`.
- **Publication Date vs Event Date**: Explicitly separated to prevent anachronistic verification (e.g. evaluating a 2025 event using a 2021 statute).

---

## 6. Resource, Concurrency & Retry Budgets

To prevent runaway crawler loops, unbounded latency, and billing exhaustion:

| Budget Dimension | Limit per Claim | Limit per User Submission |
|---|---|---|
| Search queries | Max 2 queries | Max 6 queries total |
| Search hits collected | Max 5 hits per query | Max 15 hits total |
| Full pages fetched | Max 3 pages | Max 6 pages total |
| Connect timeout | 10 seconds | N/A (per attempt) |
| Read / stream timeout | 20 seconds | N/A (per attempt) |
| Total fetch timeout | 30 seconds max per page | 90 seconds overall fetch phase |
| HTTP redirects | Max 3 redirects per page | N/A |
| Page response size | Max 1 MB (1,048,576 bytes) | N/A |
| HTTP fetch retries | Max 1 retry (502/503/timeout only) | 0 retries on 4xx, redirects, or SSRF blocks |

---

## 7. Restriction of Findings to Examined Evidence

1. **Strict Citation Requirement**: An investigation finding or claim assessment must only reference `passage_id` items linked to a `RetrievedSource` whose status is `RETRIEVED`.
2. **Missing Evidence Rule**: If no relevant passages can be extracted from accessible sources, the claim status must be set to `UNRESOLVED` (AGENTS.md Rule #4: "Insufficient or inaccessible evidence means unresolved, never false").
3. **Contradiction Preservation**: If retrieved passages conflict, both passages must be retained in the structured findings. The finding must describe the disagreement and must NOT average, discard, or smooth over the conflict (AGENTS.md Rule #2).
4. **No Truth Scores**: The system must never emit percentage probability scores, truth meters, or certainty scores (AGENTS.md Rule #6).

---

## 8. Safe-Fetch Requirements (SSRF & Ingestion Security)

Before any live HTTP fetching is implemented in Milestone 2B, the fetch client must implement the following non-negotiable security boundaries:

1. **Private/Internal Network Blocking (SSRF)**:
   - Forbid connections to loopback (`127.0.0.0/8`, `::1`).
   - Forbid RFC 1918 private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
   - Forbid link-local (`169.254.0.0/16`, `fe80::/10`).
   - Forbid Carrier-Grade NAT (`100.64.0.0/10`) and multicast addresses.
2. **DNS Rebinding Protection**:
   - Resolve hostname to IP address prior to opening connection.
   - Verify the resolved IP address against the network blocklist.
   - Establish connection directly to the verified IP, passing the original hostname in SNI and `Host` header.
3. **Redirect Hop Verification**:
   - Limit redirects to at most 3 hops.
   - At each redirect hop, extract the new target URL, resolve its hostname, and verify the resolved IP against the blocklist before making the subsequent request.
4. **MIME & Content-Type Gate**:
   - Inspect the `Content-Type` header upon receiving response headers.
   - Immediately abort connection if the content type is not `text/html`, `text/plain`, or `application/xhtml+xml` (reject PDFs, binaries, executables, images, video).
5. **Streaming Size Ceiling**:
   - Abort if `Content-Length > 1,048,576` bytes (1 MB).
   - If `Content-Length` is absent, stream the response in chunks and abort if cumulative bytes exceed 1 MB.
6. **Untrusted Data Isolation**:
   - All retrieved text injected into LLM evaluation prompts must be enclosed within `<untrusted_source_content>` boundaries.
   - System prompts must explicitly instruct the LLM that content within source boundaries is strictly untrusted data, never instructions.
7. **Robots.txt Adherence**:
   - Check `robots.txt` disallow rules where feasible before fetching content.
