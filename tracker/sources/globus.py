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


def _looks_relevant(text: str, product: Product) -> bool:
    low = text.lower()
    if any(bad in low for bad in product.title_must_exclude):
        return False
    return all(req in low for req in product.title_must_include)


def _is_buyable_text(text: str) -> bool:
    low = text.lower()

    negative = [
        "nicht verfügbar",
        "derzeit nicht verfügbar",
        "ausverkauft",
        "online nicht verfügbar",
        "nicht lieferbar",
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

    for element in soup.find_all(["article", "li", "div"]):
        text = element.get_text(" ", strip=True)
        if "portasplit" in text.lower() or "midea" in text.lower():
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
            title = el.get_text(" ", strip=True)
            if title:
                return title

    text = soup.get_text(" ", strip=True)
    m = re.search(r"(Midea.{0,120}?PortaSplit.{0,80})", text, flags=re.I)
    if m:
        return m.group(1).strip()

    return product.name


def fetch_offers(cfg: Config, product: Product) -> list[Offer]:
    url = product.url_for("globus")
    if not url:
        log.info("globus: keine Produkt-URL für '%s' konfiguriert – übersprungen.", product.name)
        return []

    html, how = fetch_page(url)
    if not html:
        log.info("globus: keine Seite geladen.")
        return []

    offers: list[Offer] = []
    blocks = _extract_candidate_blocks(html)

    log.debug("globus: html_länge=%d", len(html))
    log.debug("globus: kandidat_blöcke=%d", len(blocks))
    log.debug("globus: enthält_portasplit=%s", "portasplit" in html.lower())
    log.debug("globus: enthält_midea=%s", "midea" in html.lower())

    for block in blocks:
        text = BeautifulSoup(block, "html.parser").get_text(" ", strip=True)

        if not _looks_relevant(text, product):
            continue

        price = parse_price(text)
        if price is None:
            continue

        offer_url = _extract_url(block, url)
        title = _extract_title(block, product)
        in_stock = _is_buyable_text(text)

        offers.append(
            Offer(
                source="globus",
                title=title,
                price=price,
                url=offer_url,
                in_stock=in_stock,
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=product.eans[0] if product.eans else None,
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