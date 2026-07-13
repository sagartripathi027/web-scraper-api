# app/scraper/utils.py
"""
Small, reusable utility helpers used by the scraping and parsing layers.
"""
import re
from collections import Counter
from typing import Iterable, List
from urllib.parse import urljoin, urlparse, urlunparse

# A minimal English stopword list used for keyword frequency extraction.
STOPWORDS = {
    "the", "is", "at", "which", "on", "a", "an", "and", "or", "but", "in",
    "with", "to", "for", "of", "as", "by", "that", "this", "it", "from",
    "be", "are", "was", "were", "will", "would", "can", "could", "should",
    "has", "have", "had", "not", "no", "yes", "you", "your", "we", "our",
    "they", "their", "he", "she", "his", "her", "its", "i", "me", "my",
    "if", "so", "do", "does", "did", "than", "then", "there", "here",
    "about", "into", "over", "after", "before", "up", "down", "out",
    "all", "any", "each", "more", "most", "other", "some", "such", "only",
    "own", "same", "too", "very", "just", "also", "when", "where", "who",
    "what", "how", "why",
}


def clean_text(text: str) -> str:
    """Collapse whitespace/newlines and strip leading/trailing spaces."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def remove_empty_values(items: Iterable[str]) -> List[str]:
    """Remove None / empty-string / whitespace-only entries from a list."""
    return [item for item in (clean_text(i) for i in items) if item]


def remove_duplicates(items: Iterable[str]) -> List[str]:
    """Remove duplicates while preserving original order."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def normalize_url(base_url: str, link: str) -> str:
    """Resolve a possibly-relative link against the page's base URL."""
    try:
        return urljoin(base_url, link)
    except Exception:
        return link


def is_valid_url(url: str) -> bool:
    """Basic sanity check that a string looks like a valid http(s) URL."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def normalize_stored_url(url: str) -> str:
    """
    Normalize a URL for duplicate-detection / storage comparison.

    Currently handles:
    - Trailing slash differences, e.g.
      "https://example.com" and "https://example.com/" normalize to the
      same value.
    - Lowercasing the scheme and host (case-insensitive per RFC 3986),
      leaving path/query/fragment untouched.

    This value is used purely for comparison/storage keys - the original
    URL entered by the user is still what gets scraped and displayed.
    """
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path)
    return urlunparse(normalized)


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    Very simple frequency-based keyword extraction.

    Steps:
    1. Lowercase and strip punctuation.
    2. Split into words.
    3. Remove stopwords and short words.
    4. Count frequency and return the top_n most common words.
    """
    if not text:
        return []

    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    filtered = [w for w in words if w not in STOPWORDS]

    if not filtered:
        return []

    counter = Counter(filtered)
    most_common = counter.most_common(top_n)
    return [word for word, _ in most_common]