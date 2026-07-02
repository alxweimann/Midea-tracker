"""Playwright Network Sniffer.

Zeichnet alle interessanten Netzwerkaufrufe einer Produktseite auf.
Nur als Entwicklungswerkzeug gedacht.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def sniff(url: str, output_name: str) -> None:
    entries = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
        )

        page = browser.new_page(
            viewport={"width": 1400, "height": 1000}
        )

        def on_request(request):
            if request.resource_type not in (
                "xhr",
                "fetch",
                "document",
            ):
                return

            entries.append(
                {
                    "type": "request",
                    "method": request.method,
                    "resource": request.resource_type,
                    "url": request.url,
                }
            )

            print(f">>> {request.method} {request.url}")

        def on_response(response):
            try:
                ctype = response.headers.get("content-type", "")
            except Exception:
                ctype = ""

            if (
                "json" not in ctype.lower()
                and "graphql" not in response.url.lower()
            ):
                return

            body = ""

            try:
                body = response.text()[:500]
            except Exception:
                pass

            entries.append(
                {
                    "type": "response",
                    "status": response.status,
                    "content_type": ctype,
                    "url": response.url,
                    "body": body,
                }
            )

            print(f"<<< {response.status} {response.url}")

        page.on("request", on_request)
        page.on("response", on_response)

        print()
        print("Lade:", url)
        print()

        page.goto(
            url,
            wait_until="networkidle",
            timeout=90000,
        )

        page.wait_for_timeout(5000)

        browser.close()

    out = LOG_DIR / f"{output_name}.json"

    out.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print(f"{len(entries)} Einträge gespeichert.")
    print(out)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("name")
    parser.add_argument("url")

    args = parser.parse_args()

    sniff(args.url, args.name)


if __name__ == "__main__":
    main()
