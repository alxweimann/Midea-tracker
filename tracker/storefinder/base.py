"""Gemeinsame Storefinder-Datenstrukturen."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoreFinderResult:
    chain: str
    name: str
    id: str = ""
    city: str = ""
    postal_code: str = ""
    street: str = ""
    lat: float | None = None
    lon: float | None = None
    store_url: str | None = None

    def key(self) -> str:
        return f"{self.chain}:{self.id or self.name}".lower()
