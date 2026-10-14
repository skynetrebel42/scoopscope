"""Search provider interfaces and data models."""

from app.search.models import (
    ClaimLinkedQuery,
    EvidencePassage,
    RawSearchResult,
    RetrievedSource,
    SearchResultHit,
    SourceDependence,
    SourceFetchState,
)
from app.search.provider import SearchProvider, SearchProviderError
from app.search.serper_provider import SerperSearchProvider

__all__ = [
    "ClaimLinkedQuery",
    "EvidencePassage",
    "RawSearchResult",
    "RetrievedSource",
    "SearchResultHit",
    "SearchProvider",
    "SearchProviderError",
    "SerperSearchProvider",
    "SourceDependence",
    "SourceFetchState",
]
