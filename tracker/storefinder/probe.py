"""API-Prober für Händler.

Testet bekannte API-Endpunkte und schreibt Statuscodes und Content-Type
ins Log. Damit können wir schnell erkennen, welche APIs öffentlich
erreichbar sind und welche geblockt werden.
"""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

TESTS = {
    "OBI robots": "https://www.obi.de/robots.txt",
    "OBI": "https://www.obi.de/api/",
    "Hornbach": "https://www.hornbach.de/",
    "Hornbach API": "https://www.hornbach.de/api/",
    "Bauhaus": "https://www.bauhaus.info/",
    "MediaMarkt": "https://www.mediamarkt.de/api/",
    "Saturn": "https://www.saturn.de/api/",
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36"
    )
}


def probe() -> None:
    print()
    print("=" * 60)
    print("Store/API Probe")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)

    for name, url in TESTS.items():
        try:
            r = session.get(url, timeout=15, allow_redirects=True)

            print(
                f"{name:15} "
                f"{r.status_code:3} "
                f"{r.headers.get('content-type','-')}"
            )

        except Exception as exc:
            print(f"{name:15} ERROR {exc}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    probe()
