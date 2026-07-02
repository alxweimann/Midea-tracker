"""OBI Availability Store Probe.

Probiert verschiedene Store-Parameter gegen die OBI Availability API aus.
Nur Entwicklungswerkzeug.
"""

from __future__ import annotations

import json
import requests

ARTICLE_ID = "8620890"
POSTAL_CODE = "67071"

# Markt Ludwigshafen (kann später beliebig geändert werden)
STORE_ID = "143"
STORE_NUMBER = "143"

BASE_URL = (
    f"https://www.obi.de/api/pdp/v1/availability/"
    f"{ARTICLE_ID}?postalCode={POSTAL_CODE}&quantity=1&lang=de-DE"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.obi.de/",
}


TESTS = [
    {
        "name": "baseline",
        "params": {},
        "headers": {},
    },
    {
        "name": "storeId",
        "params": {"storeId": STORE_ID},
        "headers": {},
    },
    {
        "name": "storeNumber",
        "params": {"storeNumber": STORE_NUMBER},
        "headers": {},
    },
    {
        "name": "marketId",
        "params": {"marketId": STORE_ID},
        "headers": {},
    },
    {
        "name": "preferredStore",
        "params": {"preferredStore": STORE_ID},
        "headers": {},
    },
    {
        "name": "pickupStoreId",
        "params": {"pickupStoreId": STORE_ID},
        "headers": {},
    },
    {
        "name": "header-storeId",
        "params": {},
        "headers": {"x-store-id": STORE_ID},
    },
    {
        "name": "header-marketId",
        "params": {},
        "headers": {"x-market-id": STORE_ID},
    },
    {
        "name": "header-preferredStore",
        "params": {},
        "headers": {"x-preferred-store": STORE_ID},
    },
]


def main() -> int:
    print()
    print("=== OBI Availability Store Probe ===")
    print()

    for test in TESTS:
        params = test["params"]
        headers = HEADERS | test["headers"]

        print("=" * 80)
        print("TEST:", test["name"])
        print("PARAMS:", params)
        print("HEADERS:", test["headers"])
        print()

        response = requests.get(
            BASE_URL,
            params=params,
            headers=headers,
            timeout=30,
        )

        print("STATUS:", response.status_code)
        print("URL:")
        print(response.url)
        print()

        try:
            data = response.json()
        except Exception:
            print(response.text[:2000])
            print()
            continue

        print(json.dumps(data, indent=2, ensure_ascii=False))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
