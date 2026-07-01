"""Datenmodelle für den Tracker."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

CONDITION_NEW = "new"
CONDITION_USED = "used"

CHANNEL_ONLINE = "online"
CHANNEL_STORE = "store"


@dataclass(frozen=True)
class Offer:
    source: str
    title: str
    price: float
    url: str
    in_stock: bool
    condition: str = CONDITION_NEW
    channel: str = CHANNEL_ONLINE
    ean: str | None = None
    merchant: str | None = None
    store_name: str | None = None
    distance_km: float | None = None
    product_name: str | None = None

    def key(self) -> str:
        """Stabiler Schlüssel inkl. Preis, damit Preisänderungen neue Alarme auslösen."""
        parts = [
            self.source,
            self.channel,
            self.condition,
            self.merchant or "",
            self.store_name or "",
            self.url,
            str(round(self.price or 0, 2)),
        ]
        raw = "|".join(parts)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def describe(self) -> str:
        cond = "Neu" if self.condition == CONDITION_NEW else "Gebraucht"
        where = self.merchant or self.source

        if self.channel == CHANNEL_STORE and self.store_name:
            dist = f" (~{self.distance_km:.0f} km)" if self.distance_km is not None else ""
            where = f"{where} – Filiale {self.store_name}{dist}"

        return f"{where}: {self.price:.2f} € [{cond}]"
