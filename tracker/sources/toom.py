"""toom-Baumarkt-Adapter für Midea PortaSplit."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..config import Config, Product, Store
from ..matching import haversine_km
from ..models import CHANNEL_ONLINE, CHANNEL_STORE, CONDITION_NEW, Offer
from .base import fetch_page, parse_price
from .jsonld import extract_products

log = logging.getLogger(__name__)

BASE_URL = "https://toom.de"

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
    "hot air stop",
]

_DEVICE_MARKERS = [
    "klimagerät",
    "klimaanlage",
    "split-klimaanlage",
    "split klimaanlage",
    "mobiles klimagerät",
    "mobile split",
    "12000",
    "12.000",
    "btu",
]


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _is_accessory(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _ACCESSORY_MARKERS)


def _looks_like_device(text: str) -> bool:
    low = text.lower()

    if "portasplit" not in low:
        return False

    if _is_accessory(low):
        return False

    return any(marker in low for marker in _DEVICE_MARKERS)


def _matches_product_text(text: str, product: Product) -> bool:
    low = text.lower()

    if any(bad in low for bad in product.title_must_exclude):
        return False

    if not all(req in low for req in product.title_must_include):
        return False

    return _looks_like_device(low)


def _is_online_buyable_text(text: str) -> bool:
    low = text.lower()

    negative = [
        "nicht verfügbar",
        "derzeit nicht verfügbar",
        "online nicht verfügbar",
        "ausverkauft",
        "nicht lieferbar",
        "zurzeit nicht lieferbar",
        "keine online-bestellung",
        "keine lieferung nach hause",
    ]
    if any(marker in low for marker in negative):
        return False

    positive = [
        "in den warenkorb",
        "online bestellen",
        "lieferbar",
        "lieferung nach hause",
    ]
    return any(marker in low for marker in positive)


def _is_store_available_text(text: str) -> bool:
    low = text.lower()

    negative = [
        "nicht verfügbar",
        "derzeit nicht verfügbar",
        "ausverkauft",
        "nicht vorrätig",
    ]
    if any(marker in low for marker in negative):
        return False

    positive = [
        "verfügbar in",
        "abholen",
        "reservieren",
        "marktabholung",
        "im markt verfügbar",
    ]
    return any(marker in low for marker in positive)


def _distance(cfg: Config, store: Store) -> float | None:
    if store.distance_km is not None:
        return store.distance_km
    if store.lat is None or store.lon is None:
        return None
    return haversine_km(cfg.location.latitude, cfg.location.longitude, store.lat, store.lon)


def _extract_blocks(html: str) -> list[str]:
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

    for selector in ["h1", "h2", "h3", "[class*=title]", "[class*=name]"]:
        el = soup.select_one(selector)
        if el:
            title = _clean_text(el.get_text(" ", strip=True))
            if title:
                return title

    text = _clean_text(soup.get_text(" ", strip=True))

    m = re.search(
        r"(Midea.{0,140}?PortaSplit.{0,140})",
        text,
        flags=re.I,
    )
    if m:
        return _clean_text(m.group(1))

    return product.name


def _offer_is_plausible(title: str, text: str, price: float | None, product: Product) -> bool:
    combined = _clean_text(f"{title} {text}")

    if not _matches_product_text(combined, product):
        log.debug("toom: verworfen, Text passt nicht zum Gerät | Titel=%s", title)
        return False

    if price is None:
        log.debug("toom: verworfen, kein Preis | Titel=%s", title)
        return False

    if price < 500:
        log.debug("toom: verworfen, Preis zu niedrig für PortaSplit | Titel=%s | Preis=%.2f", title, price)
        return False

    return True


def _store_offers_from_text(
    cfg: Config,
    product: Product,
    title: str,
    price: float,
    url: str,
    text: str,
) -> list[Offer]:
    offers: list[Offer] = []
    low = text.lower()

    if not _is_store_available_text(text):
        return offers

    for store in cfg.stores_for("toom"):
        if store.name.lower() not in low:
            continue

        offers.append(
            Offer(
                source="toom",
                title=title,
                price=price,
                url=url,
                in_stock=True,
                condition=CONDITION_NEW,
                channel=CHANNEL_STORE,
                ean=None,
                merchant="toom Baumarkt",
                store_name=store.name,
                distance_km=_distance(cfg, store),
                product_name=product.name,
            )
        )

    return offers


def _offers_from_jsonld(cfg: Config, html: str, product: Product, url: str) -> list[Offer]:
    offers: list[Offer] = []

    for prod in extract_products(html):
        title = _clean_text(prod["title"] or product.name)
        price = prod["price"]
        ean = prod["ean"]

        check_text = f"{title} {ean or ''}"

        if not _offer_is_plausible(title, check_text, price, product):
            continue

        online_buyable = bool(prod["in_stock"]) or _is_online_buyable_text(html)

        offers.append(
            Offer(
                source="toom",
                title=title,
                price=price,
                url=url,
                in_stock=online_buyable,
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=ean,
                merchant="toom Baumarkt",
            )
        )

        offers.extend(_store_offers_from_text(cfg, product, title, price, url, html))

    return offers


def _offers_from_blocks(cfg: Config, html: str, product: Product, fallback_url: str) -> list[Offer]:
    offers: list[Offer] = []

    for block in _extract_blocks(html):
        soup = BeautifulSoup(block, "html.parser")
        text = _clean_text(soup.get_text(" ", strip=True))
        title = _extract_title(block, product)
        price = parse_price(text)
        url = _extract_url(block, fallback_url)

        if not _offer_is_plausible(title, text, price, product):
            continue

        offers.append(
            Offer(
                source="toom",
                title=title,
                price=price,
                url=url,
                in_stock=_is_online_buyable_text(text),
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=None,
                merchant="toom Baumarkt",
            )
        )

        offers.extend(_store_offers_from_text(cfg, product, title, price, url, text))

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

    offers = _offers_from_jsonld(cfg, html, product, url)
    if not offers:
        offers = _offers_from_blocks(cfg, html, product, url)

    unique: dict[tuple[str, str, str, float], Offer] = {}
    for offer in offers:
        if offer.price is not None:
            unique[(offer.channel, offer.store_name or "", offer.url, offer.price)] = offer

    result = list(unique.values())
    log.info("toom: %d Angebote extrahiert (%s).", len(result), how)
    return result