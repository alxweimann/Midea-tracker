"""Produktabgleich und Geo-Distanz."""

from __future__ import annotations

import logging
from math import asin, cos, radians, sin, sqrt

from .config import Location, Product
from .models import CHANNEL_STORE, CONDITION_USED, Offer

log = logging.getLogger(__name__)


def matches_product(offer: Offer, product: Product) -> bool:
    """Stellt sicher, dass das Angebot wirklich das gesuchte Gerät ist."""
    if offer.ean and product.eans:
        return offer.ean in product.eans

    title = (offer.title or "").lower()
    if not title:
        return False
    if any(bad in title for bad in product.title_must_exclude):
        return False
    return all(req in title for req in product.title_must_include)


def explain_buyable_rejection(
    offer: Offer,
    product: Product,
    location: Location,
) -> list[str]:
    """Gibt alle Gründe zurück, warum ein Angebot nicht als kaufbar zählt."""
    reasons: list[str] = []

    if not matches_product(offer, product):
        reasons.append("Produkt passt nicht zu EAN/Titel-Regeln")

    if not offer.in_stock:
        reasons.append("nicht auf Lager / nicht wirklich bestellbar")

    if offer.price is None:
        reasons.append("kein Preis erkannt")
    elif offer.price > product.max_price:
        reasons.append(f"Preis {offer.price:.2f} € über Limit {product.max_price:.2f} €")

    if offer.condition == CONDITION_USED and not product.allow_used:
        reasons.append("gebraucht, aber Gebrauchtangebote sind deaktiviert")

    if offer.channel == CHANNEL_STORE:
        if offer.distance_km is None:
            reasons.append("Filialangebot ohne Distanzangabe")
        elif offer.distance_km > location.radius_km:
            reasons.append(
                f"Filiale {offer.distance_km:.1f} km entfernt, Limit {location.radius_km:.1f} km"
            )

    return reasons


def log_offer_decision(
    offer: Offer,
    product: Product,
    location: Location,
) -> None:
    """Schreibt eine kompakte Debug-Auswertung für ein einzelnes Angebot."""
    reasons = explain_buyable_rejection(offer, product, location)

    price = "unbekannt" if offer.price is None else f"{offer.price:.2f} €"
    distance = "n/a" if offer.distance_km is None else f"{offer.distance_km:.1f} km"

    if reasons:
        log.debug(
            "ANGEBOT VERWORFEN | Produkt=%s | Quelle=%s | Händler=%s | Titel=%s | "
            "Preis=%s | EAN=%s | Lager=%s | Kanal=%s | Distanz=%s | Gründe=%s | URL=%s",
            product.name,
            offer.source,
            offer.merchant,
            offer.title,
            price,
            offer.ean,
            offer.in_stock,
            offer.channel,
            distance,
            "; ".join(reasons),
            offer.url,
        )
    else:
        log.debug(
            "ANGEBOT AKZEPTIERT | Produkt=%s | Quelle=%s | Händler=%s | Titel=%s | "
            "Preis=%s | EAN=%s | Lager=%s | Kanal=%s | Distanz=%s | URL=%s",
            product.name,
            offer.source,
            offer.merchant,
            offer.title,
            price,
            offer.ean,
            offer.in_stock,
            offer.channel,
            distance,
            offer.url,
        )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def is_buyable(offer: Offer, product: Product, location: Location) -> bool:
    """Der zentrale "nur wirklich bestellbar"-Filter."""
    reasons = explain_buyable_rejection(offer, product, location)
    return not reasons
