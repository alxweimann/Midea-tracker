"""Baumarkt-Adapter für OBI, Bauhaus und Hornbach (gemeinsamer Code).

Diese Shops blocken einfache Requests mit HTTP 403, betten aber strukturierte
Produktdaten (JSON-LD) ein. Wir versuchen daher zuerst einen normalen Request
und fallen bei Block auf eine echte Browser-Session (Playwright/Chromium)
zurück. Geliefert wird die Online-Verfügbarkeit; Filialabholung kann später
ergänzt werden.
"""

from __future__ import annotations

import logging

from ..config import Config, Product
from ..models import CHANNEL_ONLINE, CONDITION_NEW, Offer
from .base import fetch_page
from .buyability import assess_buyability
from .jsonld import extract_products

log = logging.getLogger(__name__)

_LABEL = {
    "obi": "OBI",
    "bauhaus": "BAUHAUS",
    "hornbach": "Hornbach",
    "globus": "Globus Baumarkt",
}


def _html(url: str) -> str | None:
    html, how = fetch_page(url, wait_selector="script[type='application/ld+json']")
    if how == "blocked":
        log.info("Baumarkt-Seite: Bot-Wall nicht überwunden (geblockt).")
    return html


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
        # Strikte Kaufbarkeit: strukturiertes InStock (kein InStoreOnly) UND
        # kein negativer Marker auf der Seite.
        buyable, signals = assess_buyability(html, jsonld_in_stock=prod["in_stock"])
        log.info(
            "%s: availability=%s -> bestellbar=%s %s",
            chain, prod.get("availability_raw"), buyable, signals,
        )
        offers.append(
            Offer(
                source=chain,
                title=prod["title"] or product.name,
                price=prod["price"],
                url=url,
                in_stock=buyable,
                condition=CONDITION_NEW,
                channel=CHANNEL_ONLINE,
                ean=prod["ean"] or product_ean,
                merchant=label,
            )
        )

    log.info("%s: %d Angebote extrahiert.", chain, len(offers))
    return offers
