"""Quellen-Adapter.

Jeder Adapter implementiert ``fetch_offers(cfg, product) -> list[Offer]`` und
ist über ``get_source(name)`` auffindbar. Adapter sind voneinander isoliert:
Fehler in einer Quelle dürfen die anderen nicht abbrechen.
"""

from __future__ import annotations

from collections.abc import Callable

from ..config import Config, Product
from ..models import Offer
from . import amazon, baumarkt, geizhals, idealo, mediamarkt

SourceFn = Callable[[Config, Product], list[Offer]]

SOURCES: dict[str, SourceFn] = {
    "geizhals": geizhals.fetch_offers,
    "idealo": idealo.fetch_offers,
    "mediamarkt": lambda cfg, product: mediamarkt.fetch_offers(cfg, product, chain="mediamarkt"),
    "saturn": lambda cfg, product: mediamarkt.fetch_offers(cfg, product, chain="saturn"),
    "obi": lambda cfg, product: baumarkt.fetch_offers(cfg, product, chain="obi"),
    "bauhaus": lambda cfg, product: baumarkt.fetch_offers(cfg, product, chain="bauhaus"),
    "hornbach": lambda cfg, product: baumarkt.fetch_offers(cfg, product, chain="hornbach"),
    "amazon": amazon.fetch_offers,
}


def get_source(name: str) -> SourceFn | None:
    return SOURCES.get(name)