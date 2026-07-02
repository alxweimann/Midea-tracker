"""OBI Storefinder Probe.

Lädt den OBI-Storefinder-Endpunkt und zeigt Struktur + Beispielmärkte.
Nur Entwicklungswerkzeug.
"""

from __future__ import annotations

import json

import requests

URL = "https://www.obi.de/api/disc/store/locator/country/de"


def main() -> int:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
        "Referer": "https://www.obi.de/",
    }

    response = requests.get(URL, headers=headers, timeout=30)

    print("URL:", URL)
    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("content-type"))
    print()

    response.raise_for_status()

    data = response.json()

    print("Root-Typ:", type(data).__name__)

    if isinstance(data, dict):
        print("Root-Keys:", sorted(data.keys()))
        print()
        print(json.dumps(data, indent=2, ensure_ascii=False)[:12000])
    elif isinstance(data, list):
        print("Anzahl:", len(data))
        print()
        print(json.dumps(data[:5], indent=2, ensure_ascii=False)[:12000])
    else:
        print(repr(data))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
