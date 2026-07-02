"""Testprogramm für Storefinder."""

from __future__ import annotations

import argparse
import logging

from .cache import StoreCache
from .toom import fetch_stores as fetch_toom


def main() -> int:
    parser = argparse.ArgumentParser(description="Storefinder-Test")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Store-Liste neu laden und Cache aktualisieren",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    cache = StoreCache()

    if not args.refresh and cache.is_fresh():
        stores = cache.load()
        print(f"Cache geladen: {sum(len(v) for v in stores.values())} Märkte")
        return 0

    stores = {
        "toom": fetch_toom(),
    }

    cache.save(stores)

    total = sum(len(v) for v in stores.values())

    print(f"Storefinder aktualisiert ({total} Märkte)\n")

    for chain, markets in stores.items():
        print(f"{chain}: {len(markets)} Märkte")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
