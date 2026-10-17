"""Safe source retrieval package."""

from app.retrieval.safe_fetcher import (
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_OVERALL_TIMEOUT_SECONDS,
    SafeAsyncHTTPTransport,
    SafeFetcher,
    SafeFetchError,
    SafeNetworkBackend,
    SSRFBlockedError,
    is_public_ip,
    validate_url_syntax,
)
from app.retrieval.passage_extractor import (
    clean_html_to_text,
    clean_text_content,
    deduplicate_urls,
    extract_candidate_passages,
    is_substantive_passage,
    verify_passage_provenance,
)

__all__ = [
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DEFAULT_OVERALL_TIMEOUT_SECONDS",
    "SafeAsyncHTTPTransport",
    "SafeFetcher",
    "SafeFetchError",
    "SafeNetworkBackend",
    "SSRFBlockedError",
    "clean_html_to_text",
    "clean_text_content",
    "deduplicate_urls",
    "extract_candidate_passages",
    "is_public_ip",
    "is_substantive_passage",
    "validate_url_syntax",
    "verify_passage_provenance",
]
