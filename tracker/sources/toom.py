"""toom-Baumarkt-Adapter für Midea PortaSplit."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..config import Config, Product
from ..models import CHANNEL_ONLINE, CONDITION_NEW, Offer
from .base import fetch_page, parse_price
from .jsonld import extract_products

log = logging.getLogger(__name__)

BASE_URL = "https://toom.de"


def _is_buyable_text(text: str) -> bool:
    low = text.lower()

    negative = [
        "nicht verfügbar",
        "derzeit nicht verfügbar",
        "online nicht verfügbar",
        "ausverkauft",
        "nicht lieferbar",
        "zurzeit nicht lieferbar",
    ]
    if any(marker in low for marker in negative):
        return False

    positive = [
        "in den warenkorb",
        "online bestellen",
        "lieferbar",
        "verfügbar",
        "reservieren",
        "abholen",
        "marktabholung",
    ]
    return any(marker in low for marker in positive)


def _title_from_html(html: str, product: Product) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for selector in ["h1", "h2", "[class*=product][class*=title]", "[class*=title]"]:
        el = soup.select_one(selector)
        if el:
            title = el.get_text(" ", strip=True)
            if title:
                return title

    text = soup.get_text(" ", strip=True)
    m = re.search(r"(Midea.{0,120}?PortaSplit.{0,120})", text, flags=re.I)
    if m:
        return m.group(1).strip()

    return product.name


def _fallback_offer_from_html(html: str, product: Product, url: str) -> Offer | None:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    low = text.lower()
    if not all(req in low for req in product.title_must_include):
        return None

    if any(bad in low for bad in product.title_must_exclude):
        return None

    price = parse_price(text)
    if price is None:
        return None

    return Offer(
        source="toom",
        title=_title_from_html(html, product),
        price=price,
        url=urljoin(BASE_URL, url),
        in_stock=_is_buyable_text(text),
        condition=CONDITION_NEW,
        channel=CHANNEL_ONLINE,
        ean=product.eans[0] if product.eans else None,
        merchant="toom Baumarkt",
    )


def fetch_offers(cfg: Config, product: Product) -> list[Offer]:
    url = product.url_for("toom")
    if not url:
        log.info("toom: keine Produkt-URL für '%s' konfiguriert – übersprungen.", product.name)
        return []

    html, how = fetch_page(url, wait_selector="script[type='application/ld+json']")
    if not html:
        log.info("toom: keine Seite geladen.")
        return []

    offers: list[Offer] = []

    for prod in extract_products(html):
        if prod["price"] is None:
            continue

        title = prod["title"] or product.name
        ean = prod["ean"] or (product.eans[0] if product.eans else None)

        offers.append(
            Offer(
                source="toom",
                title=title,
                price=prod["price"],
                url=url,
                in_stock=bool(prod["in_stock"]) or _is_buyable_text(html),
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=ean,
                merchant="toom Baumarkt",
            )
        )

    if not offers:
        fallback = _fallback_offer_from_html(html, product, url)
        if fallback:
            offers.append(fallback)

    log.info("toom: %d Angebote extrahiert (%s).", len(offers), how)
    return offers