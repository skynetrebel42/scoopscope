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
import time
import urllib.parse
import uuid

from app.search.models import (
    EvidencePassage,
    RetrievedSource,
    SourceDependence,
    SourceFetchState,
)

# Non-content container tags whose inner text should be ignored completely
IGNORE_CONTAINER_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "head",
    "template",
    "iframe",
    "object",
    "select",
    "button",
}

# Standard HTML5 void elements that cannot have end tags or child text
HTML5_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
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
    "table",
    "tbody",
    "thead",
    "tfoot",
}

# Table cell tags that require boundaries to avoid merging adjacent cell values
TABLE_CELL_TAGS = {
    "td",
    "th",
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
    """Safe HTML to plaintext converter without executing scripts or styles.
    
    Adheres to:
    - convert_charrefs=True: HTMLParser automatically decodes character references
      once during parsing. No second unescape is performed, preserving literal source text.
    - Void elements never increment ignore depth.
    - Table cell boundaries insert spaces so distinct numbers/values do not merge.
    """

    def __init__(self, deadline: float | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self._ignore_depth = 0
        self._chunks: list[str] = []
        self._deadline = deadline
        self._tag_counter = 0

    def _check_deadline(self) -> None:
        if self._deadline is not None:
            self._tag_counter += 1
            if self._tag_counter % 25 == 0 and time.monotonic() > self._deadline:
                raise TimeoutError("HTML parsing exceeded monotonic deadline")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._check_deadline()
        tag_lower = tag.lower()
        # Void elements cannot have children; never increment ignore depth
        if tag_lower in IGNORE_CONTAINER_TAGS and tag_lower not in HTML5_VOID_TAGS:
            self._ignore_depth += 1
        elif tag_lower in BLOCK_TAGS:
            self._chunks.append("\n\n")
        elif tag_lower in TABLE_CELL_TAGS:
            self._chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        self._check_deadline()
        tag_lower = tag.lower()
        if tag_lower in IGNORE_CONTAINER_TAGS and tag_lower not in HTML5_VOID_TAGS:
            self._ignore_depth = max(0, self._ignore_depth - 1)
        elif tag_lower in BLOCK_TAGS:
            self._chunks.append("\n\n")
        elif tag_lower in TABLE_CELL_TAGS:
            self._chunks.append(" ")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0:
            self._chunks.append(data)

    def get_text(self) -> str:
        # Note: HTMLParser(convert_charrefs=True) has already unescaped entities once.
        # Do NOT call html.unescape() a second time here, as it would double-decode
        # literal source text like &amp;lt; into <.
        if self._deadline is not None and time.monotonic() > self._deadline:
            raise TimeoutError("HTML text normalization exceeded monotonic deadline")
        raw_text = "".join(self._chunks)
        paragraphs: list[str] = []
        for block in raw_text.split("\n\n"):
            if self._deadline is not None and time.monotonic() > self._deadline:
                raise TimeoutError("HTML text normalization exceeded monotonic deadline")
            normalized_block = re.sub(r"[ \t\r\f\v]+", " ", block).strip()
            if normalized_block:
                paragraphs.append(normalized_block)

        return "\n\n".join(paragraphs)


def clean_html_to_text(html_content: str, deadline: float | None = None) -> str:
    """Safely convert raw HTML into clean readable paragraphs with cooperative deadline enforcement."""
    if not html_content:
        return ""
    if deadline is not None and time.monotonic() > deadline:
        raise TimeoutError("HTML parsing exceeded monotonic deadline")
    parser = HTMLTextExtractor(deadline=deadline)
    try:
        # Feed in chunks to enforce deadline cooperatively on large documents
        chunk_size = 16384
        for i in range(0, len(html_content), chunk_size):
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError("HTML parsing exceeded monotonic deadline")
            parser.feed(html_content[i:i + chunk_size])
        parser.close()
        return parser.get_text()
    except TimeoutError:
        raise
    except Exception:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("HTML fallback parsing exceeded monotonic deadline")
        # Fallback regex strip if parser hits deeply malformed markup
        stripped = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html_content)
        stripped = re.sub(r"<[^>]+>", " ", stripped)
        return re.sub(r"\s+", " ", stripped).strip()


def clean_text_content(
    content: str, content_type: str | None = None, deadline: float | None = None
) -> str:
    """MIME-aware content cleaner with cooperative deadline enforcement.
    
    - For text/plain: preserves angle-bracketed text and literal text directly,
      normalizing paragraph spacing without HTML tag stripping.
    - For HTML/XHTML: safely parses DOM tree, strips scripts/styles, respects void tags,
      preserves cell boundaries, and unescapes entities exactly once.
    """
    if not content:
        return ""
    if deadline is not None and time.monotonic() > deadline:
        raise TimeoutError("Text cleaning exceeded monotonic deadline")
    ct = (content_type or "").lower()
    if "text/plain" in ct:
        # Plain text: normalize whitespace and paragraph breaks without HTML stripping
        paragraphs: list[str] = []
        for block in content.split("\n\n"):
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError("Text cleaning exceeded monotonic deadline")
            normalized_block = re.sub(r"[ \t\r\f\v]+", " ", block).strip()
            if normalized_block:
                paragraphs.append(normalized_block)
        return "\n\n".join(paragraphs) if paragraphs else content.strip()

    return clean_html_to_text(content, deadline=deadline)


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
    deadline: float | None = None,
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

    if deadline is not None and time.monotonic() > deadline:
        raise TimeoutError("Passage extraction exceeded monotonic deadline")

    body = source.extracted_text
    keywords = extract_keywords_from_claim(claim_text, location, date)
    keyword_set = set(keywords)

    # Find paragraphs with exact offsets in body
    paragraphs: list[tuple[int, int, str]] = []
    current_idx = 0
    raw_paras = body.split("\n\n")

    for p in raw_paras:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("Passage extraction exceeded monotonic deadline")
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
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("Passage extraction exceeded monotonic deadline")
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
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("Passage extraction exceeded monotonic deadline")
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
