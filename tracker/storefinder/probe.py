"""API-Prober für Händler."""

from __future__ import annotations

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36"
    )
}

BASES = {
    "OBI": "https://www.obi.de",
    "Hornbach": "https://www.hornbach.de",
    "Bauhaus": "https://www.bauhaus.info",
    "MediaMarkt": "https://www.mediamarkt.de",
    "Saturn": "https://www.saturn.de",
}

PATHS = [
    "/robots.txt",
    "/api",
    "/api/",
    "/api/v1",
    "/api/v2",
    "/api/graphql",
    "/graphql",
    "/graphql/",
    "/rest",
    "/rest/v1",
    "/storefinder",
    "/store-finder",
    "/stores",
    "/markets",
    "/maerkte",
    "/filialen",
]


def probe() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)

    for shop, base in BASES.items():

        print()
        print("=" * 80)
        print(shop)
        print("=" * 80)

        for path in PATHS:

            url = base + path

            try:
                r = session.get(
                    url,
                    timeout=15,
                    allow_redirects=False,
                )

                ctype = r.headers.get("content-type", "-").split(";")[0]

                print(
                    f"{r.status_code:3} "
                    f"{ctype:25} "
                    f"{path}"
                )

            except Exception as exc:
                print(f"ERR {path} -> {exc}")


if __name__ == "__main__":
    probe()
