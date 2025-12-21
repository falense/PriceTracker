"""
Auto-generated extractor for finn.no

Converted from JSON pattern on 2025-12-21
Original confidence: 0.78
"""

import json
import re
from decimal import Decimal
from html import unescape
from typing import Optional, Any

from bs4 import BeautifulSoup

from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    "domain": "finn.no",
    "generated_at": "2025-12-21",
    "generator": "JSON pattern",
    "version": "1.1",
    "confidence": 0.78,
    "fields": [
        "price",
        "title",
        "availability",
        "image",
        "article_number",
        "model_number",
        "currency",
    ],
    "notes": "FINN recommerce items via advertising JSON with meta fallbacks",
}


def _load_advertising_state(soup: BeautifulSoup) -> Optional[dict[str, Any]]:
    script = soup.select_one("script#advertising-initial-state")
    if not script:
        return None
    raw = script.string or script.get_text()
    if not raw:
        return None
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            return json.loads(unescape(raw))
        except json.JSONDecodeError:
            return None


def _get_targeting_entries(state: dict[str, Any]) -> list[Any]:
    targeting = BaseExtractor.extract_json_field(state, "config.adServer.gam.targeting")
    return targeting if isinstance(targeting, list) else []


def _get_targeting_value(
    targeting: list[Any],
    keys: list[str],
    index: Optional[int] = None,
) -> Optional[str]:
    key_set = {key.lower() for key in keys}
    for entry in targeting:
        if not isinstance(entry, dict):
            continue
        entry_key = entry.get("key") or entry.get("name")
        if not entry_key:
            continue
        if str(entry_key).lower() in key_set:
            value = entry.get("value")
            if isinstance(value, list) and value:
                return str(value[0])
            if value is not None:
                return str(value)

    if index is None or index >= len(targeting):
        return None
    entry = targeting[index]
    if isinstance(entry, dict):
        value = entry.get("value")
        if isinstance(value, list) and value:
            return str(value[0])
        if value is not None:
            return str(value)
    return None


def _extract_availability_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    text = BaseExtractor.clean_text(text)
    if not text:
        return None
    if re.search(r"\b(reservert|reservasjon)\b", text, re.IGNORECASE):
        return "Reserved"
    if re.search(r"\b(solgt|utsolgt)\b", text, re.IGNORECASE):
        return "Sold"
    return "Available"


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.

    Primary: advertising JSON targeting
    Confidence: 0.85
    """
    state = _load_advertising_state(soup)
    if state:
        targeting = _get_targeting_entries(state)
        value = _get_targeting_value(targeting, ["price", "pris", "amount"], index=2)
        if value:
            return BaseExtractor.clean_price(value)

    elem = soup.select_one("meta[property='og:price:amount']")
    if elem and elem.get("content"):
        return BaseExtractor.clean_price(elem.get("content"))

    elem = soup.select_one("meta[property='product:price:amount']")
    if elem and elem.get("content"):
        return BaseExtractor.clean_price(elem.get("content"))

    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract title.

    Primary: Open Graph title meta tag
    Confidence: 0.95
    """
    elem = soup.select_one("meta[property='og:title']")
    if elem and elem.get("content"):
        return BaseExtractor.clean_text(elem.get("content"))

    elem = soup.select_one("title")
    if elem:
        return BaseExtractor.clean_text(elem.get_text())

    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract image.

    Primary: Open Graph image
    Confidence: 0.95
    """
    elem = soup.select_one("meta[property='og:image']")
    if elem and elem.get("content"):
        value = str(elem.get("content")).strip()
        if value.startswith("http"):
            return value

    state = _load_advertising_state(soup)
    if state:
        targeting = _get_targeting_entries(state)
        value = _get_targeting_value(targeting, ["image", "img", "images"], index=4)
        if value:
            value = str(value).strip()
            if value.startswith("http"):
                return value
            if value and not value.startswith("/"):
                return f"https://images.finncdn.no/dynamic/1280w/{value}"

    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract availability.

    Primary: availability indicator in title/description
    Confidence: 0.60
    """
    elem = soup.select_one("meta[property='og:title']")
    if elem and elem.get("content"):
        value = _extract_availability_from_text(elem.get("content"))
        if value:
            return value

    elem = soup.select_one("meta[name='description']")
    if elem and elem.get("content"):
        value = _extract_availability_from_text(elem.get("content"))
        if value:
            return value

    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract article_number (Finn item ID).

    Primary: advertising JSON targeting
    Confidence: 0.85
    """
    state = _load_advertising_state(soup)
    if state:
        targeting = _get_targeting_entries(state)
        value = _get_targeting_value(
            targeting,
            ["item_id", "itemid", "finn_item_id", "id"],
            index=1,
        )
        if value:
            return value.strip()

    elem = soup.select_one("meta[property='og:url']")
    url = elem.get("content") if elem else None
    if not url:
        canonical = soup.select_one("link[rel='canonical']")
        url = canonical.get("href") if canonical else None

    if url:
        match = re.search(r"/item/(\d+)", url)
        if match:
            return match.group(1)

    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract model_number (manufacturer part number).

    No reliable source found on Finn listings.
    """
    return None

def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract currency code.
    
    Returns:
        Currency code (e.g., 'NOK', 'USD', 'EUR')
    
    Confidence: 1.0 (hardcoded default)
    """
    return "NOK"

