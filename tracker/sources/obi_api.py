"""OBI API-Adapter.

Nutzt den öffentlichen OBI-PDP-Verfügbarkeits-Endpunkt.
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


def _article_id(product: Product) -> str | None:
    url = product.url_for("obi")
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


def _as_float(value) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_price(data: dict) -> float | None:
    text = str(data)
    # Preis ist im Availability-JSON nicht garantiert enthalten.
    # Deshalb vorerst None; der klassische OBI-Adapter liefert ggf. Preis aus JSON-LD.
    return None


def _store_offer_from_pickup(product: Product, article_id: str, item: dict) -> Offer | None:
    store = item.get("store") or item.get("pickupStore") or item
    availability = item.get("availability") or item.get("pickupAvailability") or {}

    store_name = (
        store.get("name")
        or store.get("storeName")
        or store.get("displayName")
        or "OBI Markt"
    )

    store_id = (
        store.get("id")
        or store.get("storeId")
        or store.get("marketId")
        or store.get("number")
    )

    quantity = (
        availability.get("quantity")
        or availability.get("stock")
        or item.get("quantity")
        or item.get("stock")
    )

    url = product.url_for("obi") or f"https://www.obi.de/p/{article_id}"

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


def _online_offer_from_delivery(product: Product, article_id: str, item: dict) -> Offer:
    url = product.url_for("obi") or f"https://www.obi.de/p/{article_id}"

    return Offer(
        source=SOURCE,
        title=product.name,
        price=_extract_price(item),
        url=url,
        in_stock=True,
        condition=CONDITION_NEW,
        channel=CHANNEL_ONLINE,
        ean=product.eans[0] if product.eans else None,
        merchant="OBI",
        product_name=product.name,
    )


def fetch_offers(cfg: Config, product: Product) -> list[Offer]:
    article_id = _article_id(product)
    if not article_id:
        log.info("obi_api: keine OBI-Artikelnummer für '%s' gefunden.", product.name)
        return []

    postal_code = cfg.location.postal_code or "00000"
    url = _availability_url(article_id, postal_code)

    data = _get_json(url, article_id)
    if not isinstance(data, dict):
        return []

    delivery_items = data.get("deliveryDataPerSeller") or []
    pickup_stores = data.get("pickupStores") or []

    offers: list[Offer] = []

    for item in delivery_items:
        if isinstance(item, dict):
            offers.append(_online_offer_from_delivery(product, article_id, item))

    for item in pickup_stores:
        if isinstance(item, dict):
            offer = _store_offer_from_pickup(product, article_id, item)
            if offer:
                offers.append(offer)

    log.info(
        "obi_api: %d Online + %d Filial-Angebote aus Availability-API.",
        len(delivery_items),
        len(pickup_stores),
    )

    return offers