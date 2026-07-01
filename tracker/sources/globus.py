"""Globus-Baumarkt-Adapter für Midea PortaSplit."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..config import Config, Product
from ..models import CHANNEL_ONLINE, CONDITION_NEW, Offer
from .base import fetch_page, parse_price

log = logging.getLogger(__name__)

BASE_URL = "https://www.globus-baumarkt.de"


_ACCESSORY_MARKERS = [
    "fensterabdichtung",
    "zubehör",
    "air-block",
    "air block",
    "sail",
    "schlauch",
    "adapter",
    "dichtung",
    "ersatzteil",
]


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _looks_relevant(text: str, product: Product) -> bool:
    low = text.lower()

    if any(bad in low for bad in product.title_must_exclude):
        return False

    if any(marker in low for marker in _ACCESSORY_MARKERS):
        return False

    if not all(req in low for req in product.title_must_include):
        return False

    return "klima" in low or "btu" in low or "split" in low


def _is_buyable_text(text: str) -> bool:
    low = text.lower()

    negative = [
        "nicht verfügbar",
        "derzeit nicht verfügbar",
        "ausverkauft",
        "online nicht verfügbar",
        "nicht lieferbar",
        "keine lieferung",
    ]
    if any(marker in low for marker in negative):
        return False

    positive = [
        "in den warenkorb",
        "online kaufen",
        "lieferbar",
        "verfügbar",
        "reservieren",
        "abholen",
    ]
    return any(marker in low for marker in positive)


def _extract_candidate_blocks(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[str] = []

    for element in soup.find_all(["article", "li", "div", "section"]):
        text = _clean_text(element.get_text(" ", strip=True))
        low = text.lower()

        if "portasplit" in low or ("midea" in low and "klima" in low):
            blocks.append(str(element))

    return blocks


def _extract_url(block_html: str, fallback_url: str) -> str:
    soup = BeautifulSoup(block_html, "html.parser")
    link = soup.find("a", href=True)
    if not link:
        return fallback_url
    return urljoin(BASE_URL, str(link["href"]))


def _extract_title(block_html: str, product: Product) -> str:
    soup = BeautifulSoup(block_html, "html.parser")

    for selector in ["h1", "h2", "h3", ".product-title", "[class*=title]", "[class*=name]"]:
        el = soup.select_one(selector)
        if el:
            title = _clean_text(el.get_text(" ", strip=True))
            if title:
                return title

    text = _clean_text(soup.get_text(" ", strip=True))
    m = re.search(r"(Midea.{0,140}?PortaSplit.{0,140})", text, flags=re.I)
    if m:
        return _clean_text(m.group(1))

    return product.name


def fetch_offers(cfg: Config, product: Product) -> list[Offer]:
    url = product.url_for("globus")
    if not url:
        log.info("globus: keine Produkt-URL für '%s' konfiguriert – übersprungen.", product.name)
        return []

    html, how = fetch_page(url, wait_selector="body")
    if not html:
        log.info("globus: keine Seite geladen.")
        return []

    offers: list[Offer] = []

    for block in _extract_candidate_blocks(html):
        text = _clean_text(BeautifulSoup(block, "html.parser").get_text(" ", strip=True))

        if not _looks_relevant(text, product):
            continue

        price = parse_price(text)
        if price is None or price < 500:
            continue

        offers.append(
            Offer(
                source="globus",
                title=_extract_title(block, product),
                price=price,
                url=_extract_url(block, url),
                in_stock=_is_buyable_text(text),
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=None,
                merchant="Globus Baumarkt",
            )
        )

    unique: dict[tuple[str, float], Offer] = {}
    for offer in offers:
        if offer.price is not None:
            unique[(offer.url, offer.price)] = offer

    result = list(unique.values())
    log.info("globus: %d Angebote extrahiert (%s).", len(result), how)
    return result