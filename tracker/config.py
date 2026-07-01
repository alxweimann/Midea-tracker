"""Laden und Validieren der Konfiguration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
STORES_PATH = ROOT / "stores.yaml"


@dataclass
class Product:
    name: str
    eans: list[str]
    title_must_include: list[str]
    title_must_exclude: list[str]
    max_price: float
    allow_used: bool
    urls: dict[str, str] = field(default_factory=dict)

    def url_for(self, source: str) -> str:
        return (self.urls.get(source) or "").strip()


@dataclass
class Location:
    postal_code: str
    city: str
    latitude: float
    longitude: float
    radius_km: float


@dataclass
class Store:
    chain: str
    id: str
    name: str
    lat: float | None = None
    lon: float | None = None
    distance_km: float | None = None


@dataclass
class Config:
    products: list[Product]
    location: Location
    sources: dict[str, bool]
    source_modes: dict[str, list[str]] = field(default_factory=dict)
    stores: dict[str, list[Store]] = field(default_factory=dict)
    heartbeat_enabled: bool = True
    heartbeat_hour_utc: int = 6

    @property
    def product(self) -> Product:
        return self.products[0]

    def enabled_sources(self, mode: str = "all") -> list[str]:
        enabled = [name for name, on in self.sources.items() if on]

        if mode == "all":
            return enabled

        selected = self.source_modes.get(mode, [])
        return [name for name in selected if name in enabled]

    def stores_for(self, chain: str) -> list[Store]:
        return self.stores.get(chain, [])


@dataclass
class Secrets:
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @classmethod
    def from_env(cls) -> "Secrets":
        return cls(
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
        )

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


def _parse_product(p: dict, fallback_urls: dict[str, str] | None = None) -> Product:
    urls = {k: str(v) for k, v in (p.get("urls") or fallback_urls or {}).items()}
    return Product(
        name=p["name"],
        eans=[str(e) for e in p.get("eans", [])],
        title_must_include=[s.lower() for s in p.get("title_must_include", [])],
        title_must_exclude=[s.lower() for s in p.get("title_must_exclude", [])],
        max_price=float(p["max_price"]),
        allow_used=bool(p.get("allow_used", False)),
        urls=urls,
    )


def load_config(config_path: Path = CONFIG_PATH, stores_path: Path = STORES_PATH) -> Config:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    if data.get("products"):
        products = [_parse_product(p) for p in data["products"]]
    else:
        legacy_urls = dict(data.get("source_urls", {}))
        products = [_parse_product(data["product"], fallback_urls=legacy_urls)]

    if not products:
        raise ValueError("config.yaml enthält keine Produkte.")

    loc = data["location"]
    location = Location(
        postal_code=str(loc["postal_code"]),
        city=loc["city"],
        latitude=float(loc["latitude"]),
        longitude=float(loc["longitude"]),
        radius_km=float(loc["radius_km"]),
    )

    stores: dict[str, list[Store]] = {}
    if stores_path.exists():
        sdata = yaml.safe_load(stores_path.read_text(encoding="utf-8")) or {}
        for chain, entries in sdata.items():
            stores[chain] = [
                Store(
                    chain=chain,
                    id=str(e.get("id") or "").strip(),
                    name=str(e.get("name") or e.get("id") or "?"),
                    lat=e.get("lat"),
                    lon=e.get("lon"),
                    distance_km=e.get("distance_km"),
                )
                for e in (entries or [])
            ]

    hb = data.get("heartbeat") or {}

    return Config(
        products=products,
        location=location,
        sources=dict(data.get("sources", {})),
        source_modes={
            name: [str(source) for source in sources]
            for name, sources in (data.get("source_modes") or {}).items()
        },
        stores=stores,
        heartbeat_enabled=bool(hb.get("enabled", True)),
        heartbeat_hour_utc=int(hb.get("hour_utc", 6)),
    )