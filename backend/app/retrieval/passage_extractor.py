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


import json

# Root/stem aliases for geographic demonyms and irregular forms
ROOT_ALIASES = {
    "argentinian": "argentin",
    "argentine": "argentin",
    "argentina": "argentin",
    "european": "europ",
    "europe": "europ",
    "americans": "america",
    "american": "america",
    "america": "america",
    "british": "brit",
    "britain": "brit",
    "chinese": "chin",
    "china": "chin",
    "canadian": "canad",
    "canada": "canad",
    "australian": "austral",
    "australia": "austral",
}

BOILERPLATE_PATTERNS = [
    r"cookie\s*policy",
    r"privacy\s*policy",
    r"terms\s*of\s*(?:service|use)",
    r"all\s*rights\s*reserved",
    r"subscribe\s*now",
    r"sign\s*in\s*to",
    r"follow\s*us\s*on",
    r"share\s*this\s*article",
    r"navigation\s*menu",
    r"skip\s*to\s*content",
    r"leave\s*a\s*comment",
    r"advertisement",
    r"related\s*stories",
    r"more\s*from\s*",
    r"for\s+more\s+information,?\s+(?:please\s+)?(?:visit|contact|see|call|email)",
    r"click\s+here\s+to",
    r"subscribe\s+to\s+(?:our|the)",
    r"read\s+more\s+(?:below|here|at)",
    r"photo\s+(?:credit|by|courtesy)\s*:",
    r"image\s+(?:credit|by|courtesy)\s*:",
    r"sign\s+up\s+for\s+(?:our\s+)?newsletter",
]


def stem_word(word: str) -> str:
    """Deterministic stem / root normalizer for search and passage matching.
    
    Normalizes demonyms, plurals, inflectional tenses, and derivational suffixes:
    e.g. 'argentinian' -> 'argentin', 'europe'/'european' -> 'europ',
         'bans'/'banned'/'banning' -> 'ban', 'chemicals'/'chemical' -> 'chemic'.
    """
    w = word.strip().lower()
    if not w:
        return ""
    if w in ROOT_ALIASES:
        return ROOT_ALIASES[w]

    # Normalize chemical / chemicals -> chemic
    if w.startswith("chemic"):
        return "chemic"

    # Derivational rules
    if w.endswith("icals"):
        w = w[:-5] + "ic"
    elif w.endswith("ical"):
        w = w[:-4] + "ic"

    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        stem = w[:-3]
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "lsz":
            stem = stem[:-1]
        return stem
    if w.endswith("ed") and len(w) > 4:
        stem = w[:-2]
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "lsz":
            stem = stem[:-1]
        elif stem.endswith("i"):
            stem = stem[:-1] + "y"
        return stem
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    if w.endswith("ian") and len(w) > 5:
        return w[:-3]
    if w.endswith("ine") and len(w) > 5:
        return w[:-3]
    if w.endswith("ic") and len(w) > 4:
        return w[:-2]

    return w


def extract_subject_terms_from_claim(claim_text: str, location: str | None = None) -> list[str]:
    """Extract primary subject/entity terms from claim text and location for anchoring."""
    subjects: set[str] = set()
    if location:
        for t in re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", location):
            if t.lower() not in STOPWORDS:
                subjects.add(t.lower())

    # Find capitalized words (proper nouns/entities) in the claim
    cap_words = re.findall(r"\b[A-Z][a-zA-Z0-9_\-]{2,}\b", claim_text)
    for c in cap_words:
        if c.lower() not in STOPWORDS:
            subjects.add(c.lower())

    # If no proper nouns were found, collect the first 2-3 substantive content nouns
    if not subjects:
        tokens = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", claim_text.lower())
        substantive = [t for t in tokens if t not in STOPWORDS]
        for t in substantive[:3]:
            subjects.add(t)

    return list(subjects)


HTML_URL_ARTIFACT_PATTERNS = [
    r'">',
    r'href\s*=',
    r'https?://',
    r'\b[a-zA-Z0-9_\-]+\.com/',
    r'status/1\d+',
    r'</?[a-zA-Z][^>]*>',
]

TAG_CLOUD_METADATA_PATTERNS = [
    r"\bRelated\s+Topics\s*:",
    r"\bTags\s*:",
    r"\bShare\s+(?:via\s+Email|on\s+(?:Facebook|Twitter|X|LinkedIn|Reddit))",
    r"\bCategories\s*:",
    r"\bFiled\s+under\s*:",
]

CAMEL_TAG_EXCEPTIONS = {"iphone", "ipad", "ipod", "imac", "macos", "ios", "mcdonald", "mcgee"}

BROAD_GEO_GOV_WORDS = {
    "california", "state", "city", "county", "america", "american", "united", "states",
    "government", "dept", "department", "office", "council", "board", "commission",
    "federal", "national", "public", "official", "agency", "policy", "news", "report",
    "update", "today", "yesterday", "article", "newsletter", "times", "post", "gazette",
    "senate", "senator", "assembly", "governor", "mayor", "president", "representative",
    "congress", "legislation", "bill", "law", "act",
}


def is_substantive_passage(text: str) -> bool:
    """Check if a paragraph is substantive content rather than a headline, boilerplate, or metadata."""
    clean = text.strip()
    words = clean.split()
    if len(clean) < 35 or len(words) < 6:
        return False

    # Check for raw HTML / URL leftovers
    clean_lower = clean.lower()
    if '">' in clean or 'href=' in clean_lower or 'http://' in clean_lower or 'https://' in clean_lower or 'com/' in clean_lower or 'status/1' in clean:
        return False

    for pat in HTML_URL_ARTIFACT_PATTERNS:
        if re.search(pat, clean, flags=re.IGNORECASE):
            return False

    # Check for tag-cloud and social metadata blocks
    for pat in TAG_CLOUD_METADATA_PATTERNS:
        if re.search(pat, clean, flags=re.IGNORECASE):
            return False

    # Check for camelCase-mashed tag lists like 'electionsChloe'
    for m in re.finditer(r"\b([a-z]{3,})([A-Z][a-z]{2,})\b", clean):
        if m.group(0).lower() not in CAMEL_TAG_EXCEPTIONS:
            return False

    # Check for standard boilerplate
    for pattern in BOILERPLATE_PATTERNS:
        if re.search(pattern, clean, flags=re.IGNORECASE):
            return False

    # Filter out bare headlines (short lines lacking sentence punctuation)
    has_sentence_end = bool(re.search(r"[.!?:]", clean))
    if not has_sentence_end and len(words) < 14:
        return False

    return True


def normalize_date_string(date_str: str) -> str | None:
    """Standardize extracted date string to ISO YYYY-MM-DD or clean date representation."""
    if not date_str:
        return None
    s = date_str.strip()
    # ISO date match YYYY-MM-DD
    m_iso = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if m_iso:
        return m_iso.group(1)
    # MM/DD/YYYY
    m_slash = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m_slash:
        m, d, y = m_slash.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    # Month D, YYYY or Month D YYYY
    m_text = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$", s)
    if m_text:
        mon_name, d, y = m_text.groups()
        months = {
            "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
            "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
            "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10,
            "november": 11, "nov": 11, "december": 12, "dec": 12,
        }
        mon = months.get(mon_name.lower())
        if mon:
            return f"{y}-{mon:02d}-{int(d):02d}"
    return s[:30]


def extract_dates_from_html(
    html_content: str, text_content: str | None = None
) -> tuple[str | None, str | None, str | None]:
    """Extract defensible publication date, modified date, and provenance from HTML content.
    
    Checks in priority order:
    1. JSON-LD datePublished / dateCreated / dateModified
    2. HTML meta tags (article:published_time, pubdate, dc.date, etc.)
    3. HTML <time datetime="..."> tags
    4. Explicit article bylines in text (e.g. 'Published December 11, 2022', 'Updated: Aug 27, 2026')
    
    Negative Rules:
    - Never infers publication dates from HTTP Date headers.
    - Never infers publication dates from URL path years.
    """
    if not html_content and not text_content:
        return (None, None, None)

    content_to_scan = html_content or text_content or ""
    pub_date: str | None = None
    mod_date: str | None = None
    date_prov: str | None = None

    # 1. JSON-LD scripts
    json_ld_matches = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content_to_scan,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for raw_json in json_ld_matches:
        try:
            data = json.loads(raw_json.strip())
            # Search dictionary or list recursively
            items = data if isinstance(data, list) else [data]
            if isinstance(data, dict) and "@graph" in data and isinstance(data["@graph"], list):
                items.extend(data["@graph"])

            for item in items:
                if not isinstance(item, dict):
                    continue
                if not pub_date:
                    for key in ("datePublished", "dateCreated", "publishDate"):
                        val = item.get(key)
                        if val and isinstance(val, str):
                            norm = normalize_date_string(val)
                            if norm:
                                pub_date = norm
                                date_prov = f"json-ld:{key}"
                                break
                if not mod_date:
                    for key in ("dateModified", "modifiedDate", "dateUpdated"):
                        val = item.get(key)
                        if val and isinstance(val, str):
                            norm = normalize_date_string(val)
                            if norm:
                                mod_date = norm
                                break
        except Exception:
            continue

    if pub_date:
        return (pub_date, mod_date, date_prov)

    # 2. HTML <meta> tags
    meta_tags = re.findall(r"<meta\s+[^>]*>", content_to_scan, flags=re.IGNORECASE)
    for m in meta_tags:
        prop_match = re.search(r'(?:property|name|itemprop)=["\']([^"\']+)["\']', m, flags=re.IGNORECASE)
        content_match = re.search(r'content=["\']([^"\']+)["\']', m, flags=re.IGNORECASE)
        if prop_match and content_match:
            prop = prop_match.group(1).lower()
            val = content_match.group(1).strip()
            norm = normalize_date_string(val)
            if not norm:
                continue

            if not pub_date and prop in (
                "article:published_time",
                "og:published_time",
                "pubdate",
                "dc.date",
                "dc.date.issued",
                "date",
                "sailthru.date",
                "parsely-pub-date",
                "rnews:datepublished",
            ):
                pub_date = norm
                date_prov = f"meta:{prop}"
            elif not mod_date and prop in (
                "article:modified_time",
                "og:updated_time",
                "dc.date.modified",
                "rnews:datemodified",
            ):
                mod_date = norm

    if pub_date:
        return (pub_date, mod_date, date_prov)

    # 3. HTML <time> tags
    time_matches = re.findall(r'<time\s+[^>]*datetime=["\']([^"\']+)["\'][^>]*>', content_to_scan, flags=re.IGNORECASE)
    for t_val in time_matches:
        norm = normalize_date_string(t_val)
        if norm:
            pub_date = norm
            date_prov = "html:time"
            break

    if pub_date:
        return (pub_date, mod_date, date_prov)

    # 4. Explicit article bylines in text
    scan_text = text_content or content_to_scan
    byline_pub = re.search(
        r'(?:published|posted|date)\s*(?:on|:)?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})',
        scan_text,
        flags=re.IGNORECASE,
    )
    if byline_pub:
        norm = normalize_date_string(byline_pub.group(1))
        if norm:
            pub_date = norm
            date_prov = "byline:published"

    byline_mod = re.search(
        r'(?:updated|modified)\s*(?:on|:)?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})',
        scan_text,
        flags=re.IGNORECASE,
    )
    if byline_mod:
        norm = normalize_date_string(byline_mod.group(1))
        if norm:
            mod_date = norm

    return (pub_date, mod_date, date_prov)


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


def extract_best_sentences_from_paragraph(
    para_text: str,
    para_start: int,
    keyword_stems: set[str],
) -> tuple[int, int, str]:
    """If paragraph exceeds 280 chars, find the 1-2 contiguous sentences with the highest keyword score.
    Returns (start_offset, end_offset, exact_passage) strictly matching body[start_offset:end_offset].
    """
    if len(para_text) <= 280:
        return para_start, para_start + len(para_text), para_text

    # Extract sentences with their precise start/end offsets inside para_text
    sentence_spans: list[tuple[int, int, str]] = []
    for m in re.finditer(r'([^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$)', para_text):
        s_raw = m.group(0)
        s_text = s_raw.strip()
        if not s_text:
            continue
        rel_start = m.start()
        while rel_start < m.end() and para_text[rel_start].isspace():
            rel_start += 1
        rel_end = rel_start + len(s_text)
        if para_text[rel_start:rel_end] == s_text:
            sentence_spans.append((rel_start, rel_end, s_text))

    if len(sentence_spans) <= 1:
        return para_start, para_start + len(para_text), para_text

    def score_sentence(s: str) -> int:
        words = set(re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", s.lower()))
        stems = {stem_word(w) for w in words if stem_word(w)}
        return len(stems.intersection(keyword_stems))

    scores = [score_sentence(s[2]) for s in sentence_spans]

    best_cand: tuple[int, int, int] | None = None  # (score, rel_start, rel_end)

    # 1-sentence options
    for i, s_score in enumerate(scores):
        cand = (s_score, sentence_spans[i][0], sentence_spans[i][1])
        if best_cand is None or cand[0] > best_cand[0]:
            best_cand = cand

    # 2 contiguous sentences options
    for i in range(len(scores) - 1):
        pair_score = scores[i] + scores[i + 1]
        pair_start = sentence_spans[i][0]
        pair_end = sentence_spans[i + 1][1]
        if best_cand is None or pair_score > best_cand[0]:
            best_cand = (pair_score, pair_start, pair_end)

    if best_cand is None:
        return para_start, para_start + len(para_text), para_text

    c_start, c_end = best_cand[1], best_cand[2]
    trimmed_passage = para_text[c_start:c_end]
    abs_start = para_start + c_start
    abs_end = para_start + c_end
    return abs_start, abs_end, trimmed_passage


def extract_candidate_passages(
    source: RetrievedSource,
    claim_id: str,
    claim_text: str,
    location: str | None = None,
    date: str | None = None,
    max_passages: int = 2,
    deadline: float | None = None,
    override_query: str | None = None,
) -> list[EvidencePassage]:
    """Extract verifiable verbatim candidate passages from a RETRIEVED source.

    Guarantees:
    - Passages are exact substrings of source.extracted_text.
    - Start and end character offsets match source.extracted_text exactly.
    - Preserves provenance links (source_id, claim_id, source_url, timestamps).
    - Unknown dates and source dependence are preserved as None/UNKNOWN.
    - Defensible dates are extracted from HTML/byline metadata, never HTTP Date headers or URL years.
    - Filters out bare headlines, navigation boilerplate, and off-topic paragraphs lacking subject anchoring.
    - When paragraphs exceed 280 chars, trims to the 1-2 highest-scoring contiguous sentences while
      preserving surrounding paragraph context.
    """
    if source.status != SourceFetchState.RETRIEVED or not source.extracted_text:
        return []

    if deadline is not None and time.monotonic() > deadline:
        raise TimeoutError("Passage extraction exceeded monotonic deadline")

    body = source.extracted_text

    # Extract defensible publication dates from raw HTML or text bylines
    pub_date, mod_date, date_prov = extract_dates_from_html(
        html_content=source.raw_text or "",
        text_content=source.extracted_text or "",
    )

    effective_text = override_query.strip() if (override_query and override_query.strip()) else claim_text

    # Extract primary specific proper nouns (people, organizations, specific entities)
    cap_words = re.findall(r"\b[A-Z][a-zA-Z0-9_\-]{2,}\b", effective_text)
    primary_entity_tokens = [
        c.lower() for c in cap_words
        if c.lower() not in STOPWORDS and c.lower() not in BROAD_GEO_GOV_WORDS
    ]
    primary_entity_stems = {stem_word(w) for w in primary_entity_tokens if stem_word(w)}

    # Stem and keyword sets
    keywords = extract_keywords_from_claim(effective_text, location, date)
    keyword_stems = {stem_word(k) for k in keywords if stem_word(k)}

    subject_terms = extract_subject_terms_from_claim(effective_text, location)
    subject_stems = {stem_word(s) for s in subject_terms if stem_word(s)}

    # Find paragraphs with exact offsets in body
    raw_paras_with_offsets: list[tuple[int, int, str]] = []
    current_idx = 0
    raw_paras = body.split("\n\n")

    for p in raw_paras:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("Passage extraction exceeded monotonic deadline")
        p_start = body.find(p, current_idx)
        if p_start == -1:
            p_start = current_idx
        p_end = p_start + len(p)
        current_idx = p_end + 2  # account for \n\n delimiter
        if p.strip():
            raw_paras_with_offsets.append((p_start, p_end, p))

    if not raw_paras_with_offsets:
        raw_paras_with_offsets = [(0, len(body), body)]

    # Filter out boilerplate and bare headlines
    substantive_paras: list[tuple[int, int, str]] = []
    for s, e, p in raw_paras_with_offsets:
        if is_substantive_passage(p):
            substantive_paras.append((s, e, p))

    # If no paragraphs pass strict substantive filter (e.g. short test fixtures), fall back gracefully
    if not substantive_paras:
        substantive_paras = [(s, e, p) for (s, e, p) in raw_paras_with_offsets if len(p.strip()) >= 20]
    if not substantive_paras and raw_paras_with_offsets:
        substantive_paras = raw_paras_with_offsets

    # Score paragraphs based on stemmed keyword overlap and subject anchoring
    scored_paragraphs: list[tuple[int, int, int, str, str]] = []
    for start, end, text in substantive_paras:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("Passage extraction exceeded monotonic deadline")

        words = set(re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower()))
        p_stems = {stem_word(w) for w in words if stem_word(w)}

        # Tight subject anchoring:
        # If specific primary entities (e.g. Gavin Newsom, Karen Bass) exist in effective query/claim,
        # paragraph MUST match at least one primary entity stem.
        if primary_entity_stems:
            matched_primary = p_stems.intersection(primary_entity_stems)
            if not matched_primary:
                # Off-topic paragraph lacking primary entity anchor
                continue
        elif subject_stems:
            matched_subjects = p_stems.intersection(subject_stems)
            if not matched_subjects:
                # Off-topic paragraph lacking primary subject anchor
                continue

        matched_stems = p_stems.intersection(keyword_stems)
        score = len(matched_stems)

        if score >= 2:
            relevance_note = f"Keyword match ({score} claim terms: {', '.join(sorted(matched_stems)[:4])})"
        elif score == 1:
            relevance_note = f"Sparse keyword match (1 term: {list(matched_stems)[0]}); relevance is unverified"
        else:
            relevance_note = "Lead context passage"

        scored_paragraphs.append((score, start, end, text, relevance_note))

    # If subject anchoring excluded all paragraphs, do not pick off-topic paragraphs
    if not scored_paragraphs:
        return []

    # Sort descending by score, preserving document offset as tie-breaker
    scored_paragraphs.sort(key=lambda x: x[0], reverse=True)

    passages: list[EvidencePassage] = []
    canonical_url = source.final_url or source.initial_url

    for score, start, end, text, note in scored_paragraphs[:max_passages]:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("Passage extraction exceeded monotonic deadline")

        # Form surrounding context (entire paragraph plus up to 200 characters before and after)
        ctx_start = max(0, start - 200)
        ctx_end = min(len(body), end + 200)
        surrounding_context = body[ctx_start:ctx_end].strip()

        # If paragraph is long (>280 chars), extract 1-2 key supporting sentences
        p_start, p_end, exact_span = extract_best_sentences_from_paragraph(
            para_text=text,
            para_start=start,
            keyword_stems=keyword_stems,
        )

        passage = EvidencePassage(
            passage_id=f"psg_{uuid.uuid4().hex[:12]}",
            source_id=source.source_id,
            claim_id=claim_id,
            source_url=canonical_url,
            exact_passage=exact_span,
            context_surrounding=surrounding_context,
            publication_date=pub_date,
            updated_date=mod_date,
            date_provenance=date_prov,
            event_date=None,
            source_dependence=SourceDependence.UNKNOWN,
            retrieved_at=source.fetched_at,
            start_offset=p_start,
            end_offset=p_end,
            relevance_note=note,
            relevance_explanation=None,
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
