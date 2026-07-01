"""Baumarkt-Adapter für OBI, Bauhaus und Hornbach."""

from __future__ import annotations

import logging

from ..config import Config, Product, Store
from ..matching import haversine_km
from ..models import CHANNEL_ONLINE, CHANNEL_STORE, CONDITION_NEW, Offer
from .base import fetch_page
from .buyability import assess_buyability
from .jsonld import extract_products

log = logging.getLogger(__name__)

_LABEL = {
    "obi": "OBI",
    "bauhaus": "BAUHAUS",
    "hornbach": "Hornbach",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _html(url: str) -> str | None:
    html, how = fetch_page(url, wait_selector="script[type='application/ld+json']")
    if how == "blocked":
        log.info("Baumarkt-Seite: Bot-Wall nicht überwunden (geblockt).")
    return html


def _distance(cfg: Config, store: Store) -> float | None:
    if store.distance_km is not None:
        return store.distance_km
    if store.lat is None or store.lon is None:
        return None
    return haversine_km(cfg.location.latitude, cfg.location.longitude, store.lat, store.lon)


def _store_available_text(text: str) -> bool:
    low = text.lower()

    negative = [
        "nicht verfügbar",
        "derzeit nicht verfügbar",
        "ausverkauft",
        "nicht vorrätig",
        "online nicht verfügbar",
        "keine marktabholung",
    ]
    if any(marker in low for marker in negative):
        return False

    positive = [
        "reservieren",
        "abholen",
        "marktabholung",
        "im markt verfügbar",
        "verfügbar im markt",
        "verfügbarkeit im markt",
        "sofort abholbereit",
        "abholbereit",
    ]
    return any(marker in low for marker in positive)


def _store_offers_from_text(
    cfg: Config,
    product: Product,
    chain: str,
    title: str,
    price: float,
    url: str,
    html: str,
) -> list[Offer]:
    offers: list[Offer] = []
    label = _LABEL.get(chain, chain.capitalize())
    low = _clean_text(html).lower()

    if not _store_available_text(low):
        return offers

    for store in cfg.stores_for(chain):
        store_name = store.name.lower()
        if store_name not in low:
            continue

        offers.append(
            Offer(
                source=chain,
                title=title,
                price=price,
                url=url,
                in_stock=True,
                condition=CONDITION_NEW,
                channel=CHANNEL_STORE,
                ean=product.eans[0] if product.eans else None,
                merchant=label,
                store_name=store.name,
                distance_km=_distance(cfg, store),
                product_name=product.name,
            )
        )

    return offers


def fetch_offers(cfg: Config, product: Product, chain: str = "obi") -> list[Offer]:
    url = product.url_for(chain)
    if not url:
        log.info("%s: keine Produkt-URL für '%s' konfiguriert – übersprungen.", chain, product.name)
        return []

    html = _html(url)
    if not html:
        return []

    product_ean = product.eans[0] if product.eans else None
    label = _LABEL.get(chain, chain.capitalize())
    offers: list[Offer] = []

    for prod in extract_products(html):
        if prod["price"] is None:
            continue

        buyable, signals = assess_buyability(html, jsonld_in_stock=prod["in_stock"])

        title = prod["title"] or product.name
        price = prod["price"]

        log.info(
            "%s: availability=%s -> online_bestellbar=%s %s",
            chain,
            prod.get("availability_raw"),
            buyable,
            signals,
        )

        offers.append(
            Offer(
                source=chain,
                title=title,
                price=price,
                url=url,
                in_stock=buyable,
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=prod["ean"] or product_ean,
                merchant=label,
            )
        )

        offers.extend(
            _store_offers_from_text(
                cfg=cfg,
                product=product,
                chain=chain,
                title=title,
                price=price,
                url=url,
                html=html,
            )
        )

    unique: dict[tuple[str, str, str, float], Offer] = {}
    for offer in offers:
        if offer.price is not None:
            unique[(offer.channel, offer.store_name or "", offer.url, offer.price)] = offer

    result = list(unique.values())
    store_count = sum(1 for offer in result if offer.channel == CHANNEL_STORE)
    online_count = sum(1 for offer in result if offer.channel == CHANNEL_ONLINE)

    log.info("%s: %d online + %d Filial-Angebote extrahiert.", chain, online_count, store_count)
    return result