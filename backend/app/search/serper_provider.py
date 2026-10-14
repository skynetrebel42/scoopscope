"""Serper (Google Search) implementation of SearchProvider protocol.

Per AGENTS.md and docs/evidence-search-design.md:
- Uses official Serper endpoint (https://google.serper.dev/search).
- Enforces strict query budgets (max 5 hits per query).
- Limits search API attempts to at most 2 requests (1 initial attempt + at most 1 retry on 5xx/timeout).
- Never logs or exposes raw API keys.
- Raises SearchProviderError with actionable diagnostic messages.
- Does not default or fall back to mock search in production.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
import httpx

from app.search.models import RawSearchResult
from app.search.provider import SearchProvider, SearchProviderError

logger = logging.getLogger(__name__)

SERPER_SEARCH_URL = "https://google.serper.dev/search"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_QUERY_HITS = 5
MAX_SEARCH_ATTEMPTS = 2  # At most 2 requests including retries


class SerperSearchProvider(SearchProvider):
    """Concrete SearchProvider implementation using Serper API."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        custom_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._timeout_seconds = timeout_seconds
        self._custom_client = custom_client

    async def search(self, query: str, max_results: int = 5) -> list[RawSearchResult]:
        """Execute a search query via Serper Google Search API.

        Args:
            query: Plaintext search query string.
            max_results: Max hits to request (capped at 5).

        Returns:
            List of RawSearchResult objects.

        Raises:
            SearchProviderError: On missing credentials, API refusal, or persistent network failure.
        """
        if not self._api_key:
            raise SearchProviderError(
                "Serper API key is not configured. Please add SERPER_API_KEY to your backend/.env file."
            )

        trimmed_query = query.strip()
        if not trimmed_query:
            return []

        # Bound hits per query to strict budget (max 5)
        num_hits = max(1, min(max_results, MAX_QUERY_HITS))

        headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
            "User-Agent": "ScoopScope-SerperClient/0.1",
        }
        payload = {
            "q": trimmed_query,
            "num": num_hits,
        }

        attempts = 0
        last_error_detail = ""

        while attempts < MAX_SEARCH_ATTEMPTS:
            attempts += 1
            try:
                if self._custom_client is not None:
                    response = await self._custom_client.post(
                        SERPER_SEARCH_URL,
                        json=payload,
                        headers=headers,
                        timeout=self._timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                        response = await client.post(
                            SERPER_SEARCH_URL,
                            json=payload,
                            headers=headers,
                        )

                # Process HTTP status
                if response.status_code == 200:
                    return self._parse_serper_response(response.json())

                # Non-200 responses
                if response.status_code == 401:
                    raise SearchProviderError(
                        "Serper authentication failed (401 Unauthorized). The configured SERPER_API_KEY is invalid."
                    )
                if response.status_code == 403:
                    raise SearchProviderError(
                        "Serper request refused (403 Forbidden). Your Serper account may have exhausted its credit balance."
                    )
                if response.status_code == 429:
                    raise SearchProviderError(
                        "Serper rate limit exceeded (429 Too Many Requests). Please retry after a brief pause."
                    )
                if response.status_code == 400:
                    try:
                        err_json = response.json()
                        msg = err_json.get("message", "Bad Request")
                    except Exception:
                        msg = response.text[:200]
                    raise SearchProviderError(f"Serper request rejected (400 Bad Request): {msg}")

                # 5xx server error -> retry once if under MAX_SEARCH_ATTEMPTS
                last_error_detail = f"HTTP {response.status_code} server error"
                if attempts < MAX_SEARCH_ATTEMPTS:
                    logger.warning(
                        "Serper upstream server error (%s). Retrying (attempt %d of %d)...",
                        last_error_detail,
                        attempts + 1,
                        MAX_SEARCH_ATTEMPTS,
                    )
                    await asyncio.sleep(1.0)
                    continue

                raise SearchProviderError(f"Serper service error: {last_error_detail}")

            except (httpx.TimeoutException, TimeoutError) as exc:
                last_error_detail = f"Timeout after {self._timeout_seconds}s ({exc})"
                if attempts < MAX_SEARCH_ATTEMPTS:
                    logger.warning(
                        "Serper search timed out. Retrying (attempt %d of %d)...",
                        attempts + 1,
                        MAX_SEARCH_ATTEMPTS,
                    )
                    await asyncio.sleep(1.0)
                    continue
                raise SearchProviderError(
                    f"Serper search timed out after {MAX_SEARCH_ATTEMPTS} attempts: {last_error_detail}"
                ) from exc
            except httpx.RequestError as exc:
                last_error_detail = f"Network connection error ({exc})"
                if attempts < MAX_SEARCH_ATTEMPTS:
                    logger.warning(
                        "Serper network error. Retrying (attempt %d of %d)...",
                        attempts + 1,
                        MAX_SEARCH_ATTEMPTS,
                    )
                    await asyncio.sleep(1.0)
                    continue
                raise SearchProviderError(
                    f"Could not connect to Serper search API: {last_error_detail}"
                ) from exc

        raise SearchProviderError(f"Serper search failed after {attempts} attempts: {last_error_detail}")

    def _parse_serper_response(self, data: dict[str, Any]) -> list[RawSearchResult]:
        """Convert Serper JSON response to standardized RawSearchResult models."""
        results: list[RawSearchResult] = []
        organic = data.get("organic", [])
        if not isinstance(organic, list):
            return results

        for idx, item in enumerate(organic):
            if not isinstance(item, dict):
                continue

            link = str(item.get("link") or "").strip()
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            position = item.get("position")

            if not link or not link.startswith(("http://", "https://")):
                continue

            # Ensure non-empty title for RawSearchResult model validation
            display_title = title if title else link
            rank = int(position) if isinstance(position, int) and position >= 1 else (idx + 1)

            results.append(
                RawSearchResult(
                    title=display_title,
                    url=link,
                    snippet=snippet,
                    rank=rank,
                    engine="serper",
                )
            )
            if len(results) >= MAX_QUERY_HITS:
                break

        return results
