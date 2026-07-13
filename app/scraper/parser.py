"""
HTML parsing layer.

Takes raw HTML (produced by extractor.py) and turns it into structured
Python data using BeautifulSoup. Contains no networking code.
"""
from typing import Dict, List

from bs4 import BeautifulSoup

from app.scraper.utils import (
    clean_text,
    normalize_url,
    is_valid_url,
    remove_duplicates,
    remove_empty_values,
)


def parse_html(html: str, base_url: str) -> Dict:
    """
    Parse raw HTML and extract structured page data.

    Returns a dict with keys:
        title, description, headings, paragraphs, links, images
    """
    soup = BeautifulSoup(html, "lxml")

    return {
        "title": _extract_title(soup),
        "description": _extract_meta_description(soup),
        "headings": _extract_headings(soup),
        "paragraphs": _extract_paragraphs(soup),
        "links": _extract_links(soup, base_url),
        "images": _extract_images(soup, base_url),
    }


def _extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return clean_text(soup.title.string)
    return ""


def _extract_meta_description(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if not meta:
        meta = soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        return clean_text(meta["content"])
    return ""


def _extract_headings(soup: BeautifulSoup) -> Dict[str, List[str]]:
    headings = {}
    for level in ("h1", "h2", "h3"):
        tags = soup.find_all(level)
        texts = remove_empty_values(tag.get_text() for tag in tags)
        headings[level] = remove_duplicates(texts)
    return headings


def _extract_paragraphs(soup: BeautifulSoup) -> List[str]:
    tags = soup.find_all("p")
    texts = remove_empty_values(tag.get_text() for tag in tags)
    return remove_duplicates(texts)


def _extract_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    raw_links = [a.get("href", "") for a in soup.find_all("a")]
    normalized = [
        normalize_url(base_url, link) for link in raw_links if link and not link.startswith("#")
    ]
    valid_links = [link for link in normalized if is_valid_url(link)]
    return remove_duplicates(valid_links)


def _extract_images(soup: BeautifulSoup, base_url: str) -> List[str]:
    raw_images = [img.get("src", "") for img in soup.find_all("img")]
    normalized = [normalize_url(base_url, src) for src in raw_images if src]
    valid_images = [src for src in normalized if is_valid_url(src)]
    return remove_duplicates(valid_images)
