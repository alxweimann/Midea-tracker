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


def _matches_product_text(text: str, product: Product) -> bool:
    low = text.lower()
    if any(bad in low for bad in product.title_must_exclude):
        return False
    return all(req in low for req in product.title_must_include)


def _is_buyable_text(text: str) -> bool:
    low = text.lower()

    negative = [
        "nicht verfügbar",
        "derzeit nicht verfügbar",
        "online nicht verfügbar",
        "ausverkauft",
        "nicht lieferbar",
        "zurzeit nicht lieferbar",
        "keine online-bestellung",
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


def _extract_blocks(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[str] = []

    for element in soup.find_all(["article", "li", "div", "section"]):
        text = element.get_text(" ", strip=True)
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

    for selector in ["h1", "h2", "h3", "[class*=title]", "[class*=name]"]:
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


def _offers_from_jsonld(html: str, product: Product, url: str) -> list[Offer]:
    offers: list[Offer] = []

    for prod in extract_products(html):
        if prod["price"] is None:
            continue

        title = prod["title"] or product.name
        ean = prod["ean"] or (product.eans[0] if product.eans else None)
        check_text = f"{title} {ean or ''}"

        if not _matches_product_text(check_text, product):
            continue

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

    return offers


def _offers_from_blocks(html: str, product: Product, fallback_url: str) -> list[Offer]:
    offers: list[Offer] = []

    for block in _extract_blocks(html):
        text = BeautifulSoup(block, "html.parser").get_text(" ", strip=True)

        if not _matches_product_text(text, product):
            continue

        price = parse_price(text)
        if price is None:
            continue

        offers.append(
            Offer(
                source="toom",
                title=_extract_title(block, product),
                price=price,
                url=_extract_url(block, fallback_url),
                in_stock=_is_buyable_text(text),
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=product.eans[0] if product.eans else None,
                merchant="toom Baumarkt",
            )
        )

    return offers


def fetch_offers(cfg: Config, product: Product) -> list[Offer]:
    url = product.url_for("toom")
    if not url:
        log.info("toom: keine Produkt-URL für '%s' konfiguriert – übersprungen.", product.name)
        return []

    html, how = fetch_page(url, wait_selector="body")
    if not html:
        log.info("toom: keine Seite geladen.")
        return []

    offers = _offers_from_jsonld(html, product, url)
    if not offers:
        offers = _offers_from_blocks(html, product, url)

    unique: dict[tuple[str, float], Offer] = {}
    for offer in offers:
        if offer.price is not None:
            unique[(offer.url, offer.price)] = offer

    result = list(unique.values())
    log.info("toom: %d Angebote extrahiert (%s).", len(result), how)
    return result