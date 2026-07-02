"""OBI API-Adapter.

Nutzt den öffentlichen OBI-PDP-Verfügbarkeits-Endpunkt.
Prüft mehrere deutsche PLZ, damit nicht nur der Heimatstandort überwacht wird.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import requests

from ..config import Config, Product
from ..models import CHANNEL_ONLINE, CHANNEL_STORE, CONDITION_NEW, Offer

log = logging.getLogger(__name__)

SOURCE = "obi_api"
BASE_URL = "https://www.obi.de/api/pdp/v1/availability"

# Pragmatische Deutschland-Abdeckung.
# Später ersetzen wir das durch echte OBI-Märkte aus dem Storefinder.
PROBE_POSTAL_CODES = [
    "67071",  # Ludwigshafen
    "68159",  # Mannheim
    "69115",  # Heidelberg
    "60311",  # Frankfurt
    "70173",  # Stuttgart
    "76133",  # Karlsruhe
    "55116",  # Mainz
    "50667",  # Köln
    "40213",  # Düsseldorf
    "44135",  # Dortmund
    "20095",  # Hamburg
    "10115",  # Berlin
    "80331",  # München
    "90402",  # Nürnberg
    "01067",  # Dresden
    "04109",  # Leipzig
]


def _article_id(product: Product) -> str | None:
    url = product.url_for("obi_api") or product.url_for("obi")
    if not url:
        return None

    parts = [part for part in url.split("/") if part]
    for part in parts:
        if part.isdigit() and len(part) >= 6:
            return part

    return None


def _availability_url(article_id: str, postal_code: str, quantity: int = 1) -> str:
    params = {
        "postalCode": postal_code,
        "quantity": str(quantity),
        "lang": "de-DE",
    }
    return f"{BASE_URL}/{article_id}?{urlencode(params)}"


def _get_json(url: str, article_id: str) -> dict | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
        "Referer": f"https://www.obi.de/p/{article_id}/midea-mobile-split-klimaanlage-portasplit",
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        log.warning("obi_api: Abruf fehlgeschlagen: %s", exc)
        return None


def _extract_price(_: dict) -> float | None:
    # Das Availability-JSON enthält nicht zuverlässig den Produktpreis.
    # Der klassische OBI-HTML/JSON-LD-Adapter kann den Preis weiter liefern.
    return None


def _is_nonempty_list(value) -> bool:
    return isinstance(value, list) and len(value) > 0


def _store_offer_from_pickup(
    product: Product,
    article_id: str,
    postal_code: str,
    item: dict,
) -> Offer:
    store = item.get("store") or item.get("pickupStore") or item

    store_name = (
        store.get("name")
        or store.get("storeName")
        or store.get("displayName")
        or f"OBI Markt PLZ {postal_code}"
    )

    store_id = (
        store.get("id")
        or store.get("storeId")
        or store.get("marketId")
        or store.get("number")
    )

    url = product.url_for("obi") or product.url_for("obi_api") or f"https://www.obi.de/p/{article_id}"

    return Offer(
        source=SOURCE,
        title=product.name,
        price=_extract_price(item),
        url=url,
        in_stock=True,
        condition=CONDITION_NEW,
        channel=CHANNEL_STORE,
        ean=product.eans[0] if product.eans else None,
        merchant="OBI",
        store_name=f"{store_name}" + (f" ({store_id})" if store_id else ""),
        product_name=product.name,
    )


def _online_offer_from_delivery(
    product: Product,
    article_id: str,
    postal_code: str,
    item: dict,
) -> Offer:
    url = product.url_for("obi") or product.url_for("obi_api") or f"https://www.obi.de/p/{article_id}"

    return Offer(
        source=SOURCE,
        title=product.name,
        price=_extract_price(item),
        url=url,
        in_stock=True,
        condition=CONDITION_NEW,
        channel=CHANNEL_ONLINE,
        ean=product.eans[0] if product.eans else None,
        merchant=f"OBI API PLZ {postal_code}",
        product_name=product.name,
    )


def _postal_codes(cfg: Config) -> list[str]:
    codes = []

    if cfg.location.postal_code:
        codes.append(str(cfg.location.postal_code))

    codes.extend(PROBE_POSTAL_CODES)

    # Reihenfolge behalten, Duplikate entfernen.
    return list(dict.fromkeys(codes))


def fetch_offers(cfg: Config, product: Product) -> list[Offer]:
    article_id = _article_id(product)
    if not article_id:
        log.info("obi_api: keine OBI-Artikelnummer für '%s' gefunden.", product.name)
        return []

    offers: list[Offer] = []
    checked = 0
    postal_codes = _postal_codes(cfg)

    for postal_code in postal_codes:
        checked += 1
        url = _availability_url(article_id, postal_code)

        data = _get_json(url, article_id)
        if not isinstance(data, dict):
            continue

        delivery_items = data.get("deliveryDataPerSeller") or []
        pickup_stores = data.get("pickupStores") or []

        if not _is_nonempty_list(delivery_items) and not _is_nonempty_list(pickup_stores):
            continue

        for item in delivery_items:
            if isinstance(item, dict):
                offers.append(_online_offer_from_delivery(product, article_id, postal_code, item))

        for item in pickup_stores:
            if isinstance(item, dict):
                offers.append(_store_offer_from_pickup(product, article_id, postal_code, item))

    log.info(
        "obi_api: %d PLZ geprüft, %d verfügbare Angebote gefunden.",
        checked,
        len(offers),
    )

    return offers
