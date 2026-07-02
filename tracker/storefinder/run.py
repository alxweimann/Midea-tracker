"""Storefinder Runner."""

from __future__ import annotations

import argparse
import logging

from .cache import save_cache
from .obi import fetch_stores as fetch_obi
from .toom import fetch_stores as fetch_toom

log = logging.getLogger(__name__)


def refresh() -> int:
    all_stores = []

    for fetcher in (
        fetch_toom,
        fetch_obi,
    ):
        try:
            stores = fetcher()
            all_stores.extend(stores)
        except Exception as exc:
            log.exception("%s fehlgeschlagen: %s", fetcher.__module__, exc)

    save_cache(all_stores)

    print(f"Storefinder aktualisiert ({len(all_stores)} Märkte)")
    print()

    by_chain: dict[str, int] = {}
    for store in all_stores:
        by_chain[store.chain] = by_chain.get(store.chain, 0) + 1

    for chain in sorted(by_chain):
        print(f"{chain}: {by_chain[chain]} Märkte")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.refresh:
        return refresh()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
