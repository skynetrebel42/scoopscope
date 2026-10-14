"""SearchProvider protocol definition.

Per docs/evidence-search-design.md:
Search integration sits behind a replaceable provider interface so providers
(Serper, Mock, etc.) can be swapped without changing calling code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.search.models import RawSearchResult


class SearchProviderError(Exception):
    """Raised when a search provider encounters an upstream failure or invalid configuration."""


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol for pluggable search engines.
    
    Implementations must return RawSearchResult objects with rank, url, title,
    snippet, and engine identifier.
    """

    async def search(self, query: str, max_results: int = 5) -> list[RawSearchResult]:
        """Execute query against search backend and return ranked results.
        
        Args:
            query: Plaintext search query string.
            max_results: Maximum number of results to return (bounded by budget).

        Returns:
            List of raw search hits.
            
        Raises:
            SearchProviderError: On upstream rate limit, network failure, or configuration error.
        """
        ...
