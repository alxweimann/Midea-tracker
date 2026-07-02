"""toom-Storefinder.

Lädt die öffentliche toom-Marktübersicht und extrahiert Filialdaten best effort.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import StoreFinderResult
from ..sources.base import fetch_page

log = logging.getLogger(__name__)

CHAIN = "toom"
BASE_URL = "https://toom.de"
MARKET_OVERVIEW_URL = "https://toom.de/uebersicht-maerkte/"


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _extract_postal_code(text: str) -> str:
    match = re.search(r"\b(\d{5})\b", text)
    return match.group(1) if match else ""


def _extract_city(text: str, name: str, text: str) -> str:
    if name:
        return name

    postal_code = _extract_postal_code(text)
    if not postal_code:
        return ""

    idx = text.find(postal_code)
    if idx < 0:
        return ""

    after = text[idx + len(postal_code):].strip()
    return after.split(" ")[0] if after else ""


def _store_id_from_url(url: str) -> str:
    clean = url.rstrip("/")
    return clean.rsplit("/", 1)[-1]


def _looks_like_market_link(href: str) -> bool:
    return "/markt/" in href


def fetch_stores() -> list[StoreFinderResult]:
    html, how = fetch_page(MARKET_OVERVIEW_URL, wait_selector="body")
    if not html:
        log.info("toom-storefinder: keine Marktübersicht geladen.")
        return []

    soup = BeautifulSoup(html, "html.parser")
    stores: dict[str, StoreFinderResult] = {}

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if not _looks_like_market_link(href):
            continue

        store_url = urljoin(BASE_URL, href)
        raw_text = _clean_text(link.get_text(" ", strip=True))

        slug = _store_id_from_url(store_url)
        name = raw_text or slug.replace("-", " ").title()

        postal_code = _extract_postal_code(raw_text)
        city = _extract_city(raw_text, name, raw_text)

        result = StoreFinderResult(
            chain=CHAIN,
            id=slug,
            name=name,
            city=city,
            postal_code=postal_code,
            store_url=store_url,
        )

        stores[result.key()] = result

    result = sorted(stores.values(), key=lambda s: (s.city or s.name, s.name))
    log.info("toom-storefinder: %d Märkte extrahiert (%s).", len(result), how)
    return result
