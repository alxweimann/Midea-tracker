"""Playwright-Fallback für OBI."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from playwright.async_api import async_playwright

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ObiBrowserResult:
    online_available: bool
    in_cart: bool
    few_left: bool
    market_only: bool
    price: str | None
    title: str | None
    reason: str


KEYWORDS_POSITIVE = (
    "online verfügbar",
    "lieferbar",
    "nur noch wenige lieferbar",
)

KEYWORDS_NEGATIVE = (
    "nur im markt",
    "im markt erhältlich",
    "verfügbarkeit im markt",
)

COOKIE_BUTTONS = (
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Akzeptieren')",
    "button:has-text('Zustimmen')",
)


async def _probe(url: str) -> ObiBrowserResult:
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

        await page.goto(
            url,
            wait_until="networkidle",
            timeout=90000,
        )

        for selector in COOKIE_BUTTONS:
            try:
                await page.locator(selector).click(timeout=2000)
                break
            except Exception:
                pass

        await page.wait_for_timeout(5000)

        body = (await page.locator("body").inner_text()).lower()

        online = any(x in body for x in KEYWORDS_POSITIVE)
        market_only = any(x in body for x in KEYWORDS_NEGATIVE)

        in_cart = False
        try:
            in_cart = await page.get_by_role(
                "button",
                name="In den Warenkorb",
            ).is_visible(timeout=1000)
        except Exception:
            pass

        few_left = "nur noch wenige" in body

        title = await page.title()

        price = None
        try:
            price = (
                await page.locator(
                    '[itemprop="price"]'
                ).first.get_attribute("content")
            )
        except Exception:
            pass

        await browser.close()

        ok = (
            online
            and in_cart
            and not market_only
        )

        reason = (
            f"online={online}, "
            f"cart={in_cart}, "
            f"few_left={few_left}, "
            f"market_only={market_only}"
        )

        return ObiBrowserResult(
            online_available=ok,
            in_cart=in_cart,
            few_left=few_left,
            market_only=market_only,
            price=price,
            title=title,
            reason=reason,
        )


def probe(url: str) -> ObiBrowserResult:
    """Synchroner Wrapper."""

    result = asyncio.run(_probe(url))

    log.info("OBI Browser Probe: %s", result.reason)

    return result
