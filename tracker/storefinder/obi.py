"""OBI-Storefinder.

Extrahiert OBI-Märkte aus der öffentlichen Marktübersicht.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import StoreFinderResult
from ..sources.base import fetch_page

log = logging.getLogger(__name__)

CHAIN = "obi"
BASE_URL = "https://www.obi.de"
MARKET_OVERVIEW_URL = "https://www.obi.de/markt"


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _extract_postal_code(text: str) -> str:
    match = re.search(r"\b(\d{5})\b", text)
    return match.group(1) if match else ""


def _store_id_from_url(url: str) -> str:
    clean = url.rstrip("/")
    return clean.rsplit("/", 1)[-1]


def _looks_like_market_link(href: str) -> bool:
    if not href:
        return False

    href = href.split("?", 1)[0].rstrip("/")

    if not href.startswith("/markt/"):
        return False

    slug = href.rsplit("/", 1)[-1]

    if not slug:
        return False

    excluded = {
        "services",
        "service",
        "partner",
        "angebote",
        "prospekt",
        "gartenplaner",
        "kontakt",
    }

    return slug not in excluded


def _name_from_url(url: str) -> str:
    slug = _store_id_from_url(url)
    return "OBI " + slug.replace("-", " ").title()


def fetch_stores() -> list[StoreFinderResult]:
    html, how = fetch_page(MARKET_OVERVIEW_URL, wait_selector="body")
    if not html:
        log.info("obi-storefinder: keine Marktübersicht geladen.")
        return []

    soup = BeautifulSoup(html, "html.parser")
    stores: dict[str, StoreFinderResult] = {}

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if not _looks_like_market_link(href):
            continue

        store_url = urljoin(BASE_URL, href)
        raw_text = _clean_text(link.get_text(" ", strip=True))

        name = raw_text
        if not name or len(name) < 3:
            name = _name_from_url(store_url)

        postal_code = _extract_postal_code(raw_text)
        store_id = _store_id_from_url(store_url)

        result = StoreFinderResult(
            chain=CHAIN,
            id=store_id,
            name=name,
            city=name.replace("OBI Markt", "").replace("OBI", "").strip(),
            postal_code=postal_code,
            store_url=store_url,
        )

        stores[result.key()] = result

    result = sorted(stores.values(), key=lambda s: (s.city or s.name, s.name))
    log.info("obi-storefinder: %d Märkte extrahiert (%s).", len(result), how)
    return result
