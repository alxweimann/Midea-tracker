"""OBI Availability Probe.

Testet den gefundenen OBI-Verfügbarkeits-Endpunkt direkt.
Nur Entwicklungswerkzeug.
"""

from __future__ import annotations

import argparse
import json
from urllib.parse import urlencode

import requests

BASE_URL = "https://www.obi.de/api/pdp/v1/availability"


def fetch_availability(article_id: str, postal_code: str, quantity: int = 1) -> dict | list | None:
    params = {
        "postalCode": postal_code,
        "quantity": str(quantity),
        "lang": "de-DE",
    }

    url = f"{BASE_URL}/{article_id}?{urlencode(params)}"

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

    response = requests.get(url, headers=headers, timeout=20)

    print()
    print("URL:", url)
    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("content-type"))
    print()

    try:
        data = response.json()
    except ValueError:
        print(response.text[:2000])
        return None

    print(json.dumps(data, indent=2, ensure_ascii=False)[:8000])
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article-id", default="8620890")
    parser.add_argument("--postal-code", default="67071")
    parser.add_argument("--quantity", type=int, default=1)

    args = parser.parse_args()

    fetch_availability(
        article_id=args.article_id,
        postal_code=args.postal_code,
        quantity=args.quantity,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())