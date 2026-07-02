"""JSON-Cache für Storefinder-Ergebnisse."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path

from .base import StoreFinderResult

log = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_PATH = CACHE_DIR / "stores.json"
DEFAULT_TTL_SECONDS = 24 * 60 * 60


class StoreCache:
    def __init__(
        self,
        path: Path = CACHE_PATH,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds

    def is_fresh(self) -> bool:
        if not self.path.exists():
            return False

        age = time.time() - self.path.stat().st_mtime
        return age <= self.ttl_seconds

    def load(self) -> dict[str, list[StoreFinderResult]]:
        if not self.path.exists():
            return {}

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Storefinder-Cache konnte nicht gelesen werden: %s", exc)
            return {}

        result: dict[str, list[StoreFinderResult]] = {}

        for chain, stores in raw.items():
            result[chain] = [
                StoreFinderResult(
                    chain=str(item.get("chain") or chain),
                    id=str(item.get("id") or ""),
                    name=str(item.get("name") or ""),
                    city=str(item.get("city") or ""),
                    postal_code=str(item.get("postal_code") or ""),
                    street=str(item.get("street") or ""),
                    lat=item.get("lat"),
                    lon=item.get("lon"),
                    store_url=item.get("store_url"),
                )
                for item in stores or []
            ]

        return result

    def save(self, stores_by_chain: dict[str, list[StoreFinderResult]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        raw = {
            chain: [store.__dict__ for store in stores]
            for chain, stores in stores_by_chain.items()
        }

        self.path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def save_cache(stores: list[StoreFinderResult]) -> None:
    stores_by_chain: dict[str, list[StoreFinderResult]] = defaultdict(list)

    for store in stores:
        stores_by_chain[store.chain].append(store)

    StoreCache().save(dict(stores_by_chain))


def load_cache() -> dict[str, list[StoreFinderResult]]:
    return StoreCache().load()
