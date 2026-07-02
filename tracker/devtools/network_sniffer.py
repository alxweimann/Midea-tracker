"""Playwright Network Sniffer.

Zeichnet interessante Netzwerkaufrufe einer Produktseite auf.
Nur als Entwicklungswerkzeug gedacht.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

KEYWORDS = [
    "availability",
    "available",
    "bestand",
    "stock",
    "inventory",
    "pickup",
    "collect",
    "store",
    "market",
    "markt",
    "locator",
    "fulfillment",
    "article",
    "quantity",
    "cart",
    "delivery",
]


def _interesting_url(url: str) -> bool:
    low = url.lower()

    ignore_hosts = [
        "google",
        "googletagmanager",
        "doubleclick",
        "facebook",
        "kameleoon",
        "usercentrics",
        "bazaarvoice",
    ]

    host = urlparse(url).netloc.lower()
    if any(marker in host for marker in ignore_hosts):
        return False

    return any(marker in low for marker in KEYWORDS)


def _find_keywords(text: str) -> list[str]:
    low = text.lower()
    return sorted({kw for kw in KEYWORDS if kw in low})


def _short(text: str, limit: int = 1500) -> str:
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _safe_json_preview(text: str) -> object:
    try:
        data = json.loads(text)
    except Exception:
        return _short(text, 800)

    if isinstance(data, dict):
        return {
            key: data.get(key)
            for key in list(data.keys())[:20]
        }

    if isinstance(data, list):
        return data[:3]

    return data


def _try_click(page: Page, selectors: list[str], label: str) -> bool:
    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.count() > 0 and element.is_visible(timeout=1500):
                element.click(timeout=3000)
                print(f"Aktion: {label} via {selector}")
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue

    print(f"Aktion nicht gefunden: {label}")
    return False


def _try_fill(page: Page, selectors: list[str], value: str, label: str) -> bool:
    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.count() > 0 and element.is_visible(timeout=1500):
                element.fill(value, timeout=3000)
                print(f"Aktion: {label}='{value}' via {selector}")
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    print(f"Eingabe nicht gefunden: {label}")
    return False


def _accept_cookies(page: Page) -> None:
    _try_click(
        page,
        [
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Akzeptieren')",
            "button:has-text('Zustimmen')",
            "button:has-text('OK')",
            "[data-testid*='accept']",
            "[id*='accept']",
        ],
        "Cookies akzeptieren",
    )


def _obi_select_store(page: Page, postal_code: str) -> None:
    print()
    print("OBI-Flow: Markt-Auswahl versuchen")
    print()

    _try_click(
        page,
        [
            "button:has-text('Markt auswählen')",
            "button:has-text('Markt ändern')",
            "a:has-text('Markt auswählen')",
            "a:has-text('Markt ändern')",
            "[data-testid*='store']",
            "[data-testid*='market']",
            "[class*='store'] button",
            "[class*='market'] button",
        ],
        "Marktauswahl öffnen",
    )

    _try_fill(
        page,
        [
            "input[placeholder*='PLZ']",
            "input[placeholder*='Postleitzahl']",
            "input[placeholder*='Ort']",
            "input[type='search']",
            "input[type='text']",
        ],
        postal_code,
        "PLZ/Ort",
    )

    try:
        page.keyboard.press("Enter")
        print("Aktion: Enter nach PLZ")
        page.wait_for_timeout(3000)
    except Exception:
        pass

    _try_click(
        page,
        [
            "button:has-text('Auswählen')",
            "button:has-text('Als Markt auswählen')",
            "button:has-text('Übernehmen')",
            "button:has-text('Speichern')",
            "button:has-text('Zum Markt')",
            "text=Ludwigshafen",
            "text=Frankenthal",
            "text=Mannheim",
        ],
        "Markt auswählen",
    )

    page.wait_for_timeout(8000)


def sniff(url: str, output_name: str, postal_code: str | None = None) -> None:
    entries: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            viewport={"width": 1440, "height": 1100},
            locale="de-DE",
            timezone_id="Europe/Berlin",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        def on_request(request):
            if request.resource_type not in ("xhr", "fetch", "document"):
                return

            interested = _interesting_url(request.url)

            entries.append(
                {
                    "type": "request",
                    "method": request.method,
                    "resource": request.resource_type,
                    "url": request.url,
                    "interesting": interested,
                    "keywords": _find_keywords(request.url),
                    "post_data": _short(request.post_data or "", 1200),
                }
            )

            prefix = ">>>*" if interested else ">>> "
            print(f"{prefix} {request.method} {request.url}")

        def on_response(response):
            try:
                ctype = response.headers.get("content-type", "")
            except Exception:
                ctype = ""

            is_json = "json" in ctype.lower()
            interested = is_json or _interesting_url(response.url)

            if not interested:
                return

            body = ""
            preview: object = ""

            try:
                body = response.text()
                preview = _safe_json_preview(body)
            except Exception:
                pass

            keywords = sorted(set(_find_keywords(response.url) + _find_keywords(body)))

            entries.append(
                {
                    "type": "response",
                    "status": response.status,
                    "content_type": ctype,
                    "url": response.url,
                    "interesting": bool(keywords),
                    "keywords": keywords,
                    "preview": preview,
                    "body_short": _short(body, 2500),
                }
            )

            marker = "<<<*" if keywords else "<<< "
            kw = f" [{', '.join(keywords)}]" if keywords else ""
            print(f"{marker} {response.status} {response.url}{kw}")

        page.on("request", on_request)
        page.on("response", on_response)

        print()
        print("Lade:", url)
        print()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(6000)
        except Exception as exc:
            print(f"Seitenaufruf fehlgeschlagen/timeout: {exc}")

        _accept_cookies(page)

        if output_name.lower().startswith("obi") and postal_code:
            _obi_select_store(page, postal_code)

        page.wait_for_timeout(6000)

        browser.close()

    out = LOG_DIR / f"{output_name}.json"

    out.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    hits = [e for e in entries if e.get("keywords")]

    print()
    print(f"{len(entries)} Einträge gespeichert.")
    print(f"{len(hits)} Einträge mit Keywords.")
    print(out)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("name")
    parser.add_argument("url")
    parser.add_argument(
        "--postal-code",
        default="67071",
        help="PLZ für Store-Auswahl, Default: 67071",
    )

    args = parser.parse_args()

    sniff(args.url, args.name, postal_code=args.postal_code)


if __name__ == "__main__":
    main()