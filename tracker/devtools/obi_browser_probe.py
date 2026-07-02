"""Browser-Probe für die OBI-Produktseite.

Öffnet die Produktseite mit Playwright und protokolliert alle
Verfügbarkeits-Texte, damit wir anschließend einen stabilen
Scanner bauen können.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

URL = "https://www.obi.de/p/8620890/midea-mobile-split-klimaanlage-portasplit"

KEYWORDS = [
    "verfüg",
    "liefer",
    "abhol",
    "markt",
    "bestand",
    "online",
    "warenkorb",
    "ausverkauft",
    "sofort",
    "stück",
]


async def main() -> None:
    out_dir = Path("tracker/devtools/logs")
    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = await browser.new_page(
            viewport={"width": 1440, "height": 1100},
            locale="de-DE",
        )

        print()
        print("Lade:", URL)

        await page.goto(URL, wait_until="networkidle", timeout=90000)

        # Cookie-Banner
        cookie_selectors = [
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Akzeptieren')",
            "button:has-text('Zustimmen')",
        ]

        for selector in cookie_selectors:
            try:
                await page.locator(selector).click(timeout=2500)
                print("Cookies akzeptiert:", selector)
                break
            except Exception:
                pass

        await page.wait_for_timeout(5000)

        text = await page.locator("body").inner_text()

        matches = []

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            lower = line.lower()

            if any(keyword in lower for keyword in KEYWORDS):
                matches.append(line)

        screenshot = out_dir / "obi_browser_probe.png"
        await page.screenshot(path=str(screenshot), full_page=True)

        logfile = out_dir / "obi_browser_probe.txt"
        logfile.write_text(
            "\n".join(matches),
            encoding="utf-8",
        )

        print()
        print("=" * 80)
        print("Treffer:", len(matches))
        print("=" * 80)

        for line in matches:
            print(line)

        print()
        print("Screenshot:", screenshot)
        print("Log:", logfile)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
