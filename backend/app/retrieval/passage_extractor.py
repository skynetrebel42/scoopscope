"""Passage extraction and HTML text cleaning with strict provenance tracking.

Per AGENTS.md, docs/evidence-search-design.md, and Milestone 2C:
- Extracts readable plaintext from HTML without executing scripts or CSS.
- Candidate passages are strictly exact substrings of the retained extracted text.
- Offsets (start_offset, end_offset) and exact string matching are verified programmatically.
- Preserves URLs, retrieval timestamps, and fetch audit IDs.
- Defaults publication_date, event_date, and source_dependence to unknown unless verified.
- Deduplicates URLs while keeping distinct URLs separate.
- Does NOT use an LLM to invent, summarize, or alter candidate passages.
"""

from __future__ import annotations

from html.parser import HTMLParser
import html
import re
import urllib.parse
import uuid

from app.search.models import (
    EvidencePassage,
    RetrievedSource,
    SourceDependence,
    SourceFetchState,
)

# Non-content tags to ignore completely
IGNORE_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "head",
    "template",
    "iframe",
    "object",
    "embed",
    "select",
    "button",
}

# Block-level tags that imply paragraph breaks
BLOCK_TAGS = {
    "p",
    "div",
    "article",
    "section",
    "main",
    "header",
    "footer",
    "nav",
    "aside",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "blockquote",
    "tr",
    "br",
    "hr",
}

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves",
}


class HTMLTextExtractor(HTMLParser):
    """Safe HTML to plaintext converter without executing scripts or styles."""

    def __init__(self) -> None:
        super().__init__()
        self._ignore_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORE_TAGS:
            self._ignore_depth += 1
        elif tag_lower in BLOCK_TAGS:
            self._chunks.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in IGNORE_TAGS:
            self._ignore_depth = max(0, self._ignore_depth - 1)
        elif tag_lower in BLOCK_TAGS:
            self._chunks.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0:
            self._chunks.append(data)

    def get_text(self) -> str:
        raw_text = "".join(self._chunks)
        # Decode entities and normalize spaces
        unescaped = html.unescape(raw_text)
        # Split into paragraphs and normalize each paragraph
        paragraphs: list[str] = []
        for block in unescaped.split("\n\n"):
            normalized_block = re.sub(r"[ \t\r\f\v]+", " ", block).strip()
            # If paragraph has substantive content, keep it
            if normalized_block:
                paragraphs.append(normalized_block)

        return "\n\n".join(paragraphs)


def clean_html_to_text(html_content: str) -> str:
    """Safely convert raw HTML into clean readable paragraphs."""
    if not html_content:
        return ""
    parser = HTMLTextExtractor()
    try:
        parser.feed(html_content)
        parser.close()
        return parser.get_text()
    except Exception:
        # Fallback regex strip if parser hits deeply malformed markup
        stripped = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html_content)
        stripped = re.sub(r"<[^>]+>", " ", stripped)
        unescaped = html.unescape(stripped)
        return re.sub(r"\s+", " ", unescaped).strip()


def deduplicate_urls(urls: list[str]) -> list[str]:
    """Deduplicate URLs preserving first-seen order, normalizing fragments and trailing slashes."""
    seen: set[str] = set()
    deduped: list[str] = []

    for raw_url in urls:
        trimmed = raw_url.strip()
        if not trimmed:
            continue
        try:
            parsed = urllib.parse.urlparse(trimmed)
            # Normalize: lowercase scheme and host, strip fragment
            normalized = urllib.parse.urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/") if parsed.path != "/" else "/",
                parsed.params,
                parsed.query,
                "",  # remove fragment
            ))
        except Exception:
            normalized = trimmed

        if normalized not in seen:
            seen.add(normalized)
            deduped.append(trimmed)

    return deduped


def extract_keywords_from_claim(claim_text: str, location: str | None = None, date: str | None = None) -> list[str]:
    """Extract distinct non-stopword alphanumeric tokens from claim text."""
    combined = f"{claim_text} {location or ''} {date or ''}"
    tokens = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", combined.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for t in tokens:
        if t not in STOPWORDS and t not in seen:
            seen.add(t)
            keywords.append(t)
    return keywords


def extract_candidate_passages(
    source: RetrievedSource,
    claim_id: str,
    claim_text: str,
    location: str | None = None,
    date: str | None = None,
    max_passages: int = 2,
) -> list[EvidencePassage]:
    """Extract verifiable verbatim candidate passages from a RETRIEVED source.

    Guarantees:
    - Passages are exact substrings of source.extracted_text.
    - Start and end character offsets match source.extracted_text exactly.
    - Preserves provenance links (source_id, claim_id, source_url, timestamps).
    - Unknown dates and source dependence are preserved as None/UNKNOWN.
    """
    if source.status != SourceFetchState.RETRIEVED or not source.extracted_text:
        return []

    body = source.extracted_text
    keywords = extract_keywords_from_claim(claim_text, location, date)
    keyword_set = set(keywords)

    # Find paragraphs with exact offsets in body
    paragraphs: list[tuple[int, int, str]] = []
    current_idx = 0
    raw_paras = body.split("\n\n")

    for p in raw_paras:
        # Locate paragraph start in body starting from current_idx
        p_start = body.find(p, current_idx)
        if p_start == -1:
            p_start = current_idx
        p_end = p_start + len(p)
        current_idx = p_end + 2  # account for \n\n delimiter
        if len(p.strip()) >= 20:  # ignore tiny boilerplate lines
            paragraphs.append((p_start, p_end, p))

    if not paragraphs:
        # Fallback to entire body if no paragraphs were split
        paragraphs = [(0, len(body), body)]

    # Score paragraphs based on keyword overlap
    scored_paragraphs: list[tuple[int, int, int, str, str]] = []
    for start, end, text in paragraphs:
        words = set(re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower()))
        matched = words.intersection(keyword_set)
        score = len(matched)
        if score >= 2:
            relevance_note = f"Keyword match ({score} claim terms: {', '.join(sorted(matched)[:4])})"
        elif score == 1:
            relevance_note = f"Sparse keyword match (1 term: {list(matched)[0]}); relevance is unverified"
        else:
            relevance_note = "No direct claim keyword match; lead context passage"
        scored_paragraphs.append((score, start, end, text, relevance_note))

    # Sort descending by score, preserving original document order as tie-breaker
    scored_paragraphs.sort(key=lambda x: x[0], reverse=True)

    passages: list[EvidencePassage] = []
    canonical_url = source.final_url or source.initial_url

    for score, start, end, text, note in scored_paragraphs[:max_passages]:
        # Form surrounding context (up to 200 characters before and after)
        ctx_start = max(0, start - 200)
        ctx_end = min(len(body), end + 200)
        surrounding_context = body[ctx_start:ctx_end].strip()

        exact_span = body[start:end]

        passage = EvidencePassage(
            passage_id=f"psg_{uuid.uuid4().hex[:12]}",
            source_id=source.source_id,
            claim_id=claim_id,
            source_url=canonical_url,
            exact_passage=exact_span,
            context_surrounding=surrounding_context,
            publication_date=None,
            event_date=None,
            source_dependence=SourceDependence.UNKNOWN,
            retrieved_at=source.fetched_at,
            start_offset=start,
            end_offset=end,
            relevance_note=note,
        )
        passages.append(passage)

    return passages


def verify_passage_provenance(passage: EvidencePassage, source: RetrievedSource) -> bool:
    """Programmatically verify that an EvidencePassage is an exact excerpt of source text."""
    if passage.source_id != source.source_id:
        return False
    if source.status != SourceFetchState.RETRIEVED or source.extracted_text is None:
        return False
    if passage.exact_passage not in source.extracted_text:
        return False
    if passage.start_offset is not None and passage.end_offset is not None:
        if source.extracted_text[passage.start_offset:passage.end_offset] != passage.exact_passage:
            return False
    return True
