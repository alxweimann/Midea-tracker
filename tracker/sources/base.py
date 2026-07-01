"""Gemeinsame Infrastruktur für alle Quellen-Adapter."""

from __future__ import annotations

import json
import logging
import random
import re
import time

import requests

log = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

DEFAULT_TIMEOUT = 10
BROWSER_GOTO_MS = 12000
BROWSER_SELECTOR_MS = 5000


def browser_headers(extra: dict | None = None) -> dict:
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra:
        headers.update(extra)
    return headers


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(browser_headers())
    return s


def http_get(
    url: str,
    *,
    session: requests.Session | None = None,
    headers: dict | None = None,
    params: dict | None = None,
    retries: int = 1,
    timeout: int = DEFAULT_TIMEOUT,
) -> requests.Response | None:
    sess = session or get_session()

    for attempt in range(retries):
        try:
            resp = sess.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp

            log.warning("GET %s -> HTTP %s (Versuch %d)", url, resp.status_code, attempt + 1)

            if resp.status_code in (403, 404, 451):
                break

        except requests.RequestException as exc:
            log.warning("GET %s fehlgeschlagen: %s (Versuch %d)", url, exc, attempt + 1)

        if attempt < retries - 1:
            time.sleep(min(2**attempt + random.random(), 3))

    return None


def fetch_page(url: str, *, wait_selector: str | None = None) -> tuple[str | None, str]:
    resp = http_get(url)

    if resp is not None and resp.status_code == 200 and not _looks_like_challenge(resp.text):
        return resp.text, "direct"

    html = fetch_html_via_browser(url, wait_selector=wait_selector)

    if html and not _looks_like_challenge(html):
        return html, "browser"

    return (html or (resp.text if resp is not None else None)), "blocked"


def http_get_json(url: str, **kwargs) -> dict | list | None:
    resp = http_get(url, **kwargs)
    if resp is None:
        return None

    try:
        return resp.json()
    except ValueError:
        log.warning("Antwort von %s ist kein gültiges JSON.", url)
        return None


_STEALTH_INIT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['de-DE','de','en-US','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = window.chrome || {runtime: {}};
const _q = navigator.permissions && navigator.permissions.query;
if (_q) { navigator.permissions.query = (p) => (
  p && p.name === 'notifications'
    ? Promise.resolve({state: Notification.permission})
    : _q(p)
); }
"""

_CHALLENGE_MARKERS = (
    "just a moment",
    "attention required",
    "/cdn-cgi/",
    "captcha",
    "are you a human",
    "enable javascript and cookies",
    "verifying you are human",
)


def _looks_like_challenge(html: str | None) -> bool:
    if not html or len(html) < 12000:
        return True

    low = html.lower()
    return any(marker in low for marker in _CHALLENGE_MARKERS)


def fetch_html_via_browser(
    url: str,
    *,
    wait_selector: str | None = None,
    timeout_ms: int = BROWSER_GOTO_MS,
    stealth: bool = True,
) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.info("Playwright nicht installiert – Browser-Fallback für %s übersprungen.", url)
        return None

    ua = random.choice(_USER_AGENTS)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            ctx = browser.new_context(
                user_agent=ua,
                locale="de-DE",
                timezone_id="Europe/Berlin",
                viewport={"width": 1366, "height": 768},
                extra_http_headers={
                    "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
                    "sec-ch-ua": '"Chromium";v="124", "Not:A-Brand";v="99"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                },
            )

            if stealth:
                ctx.add_init_script(_STEALTH_INIT)

            page = ctx.new_page()
            page.set_default_timeout(BROWSER_SELECTOR_MS)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=BROWSER_SELECTOR_MS)
                except Exception:
                    pass

            html = page.content()

            if stealth and _looks_like_challenge(html):
                for _ in range(2):
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass

                    page.wait_for_timeout(1500)
                    html = page.content()

                    if not _looks_like_challenge(html):
                        break

            browser.close()
            return html

    except Exception as exc:
        log.warning("Browser-Fallback für %s fehlgeschlagen: %s", url, exc)
        return None


def fetch_json_via_browser(
    url: str,
    *,
    referer: str | None = None,
    headers: dict | None = None,
    timeout_ms: int = BROWSER_GOTO_MS,
) -> dict | list | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.info("Playwright nicht installiert – JSON-Browser-Fallback für %s übersprungen.", url)
        return None

    ua = random.choice(_USER_AGENTS)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            ctx = browser.new_context(
                user_agent=ua,
                locale="de-DE",
                timezone_id="Europe/Berlin",
                viewport={"width": 1366, "height": 768},
            )
            ctx.add_init_script(_STEALTH_INIT)

            page = ctx.new_page()
            page.set_default_timeout(BROWSER_SELECTOR_MS)

            if referer:
                try:
                    page.goto(referer, wait_until="domcontentloaded", timeout=timeout_ms)
                    if _looks_like_challenge(page.content()):
                        page.wait_for_timeout(1500)
                except Exception:
                    pass

            try:
                result = page.evaluate(
                    """async ({url, headers}) => {
                        try {
                            const r = await fetch(url, {headers, credentials: 'include'});
                            return {status: r.status, body: await r.text()};
                        } catch (e) {
                            return {status: 0, body: ''};
                        }
                    }""",
                    {"url": url, "headers": headers or {}},
                )
            finally:
                browser.close()

        if not result or result.get("status") != 200:
            log.info("JSON-Browser-Fallback %s -> HTTP %s", url, result and result.get("status"))
            return None

        try:
            return json.loads(result["body"])
        except (ValueError, TypeError):
            log.warning("JSON-Browser-Fallback: Antwort von %s ist kein gültiges JSON.", url)
            return None

    except Exception as exc:
        log.warning("JSON-Browser-Fallback für %s fehlgeschlagen: %s", url, exc)
        return None


_PRICE_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[,.](\d{2}))?")


def parse_price(text: str) -> float | None:
    if not text:
        return None

    cleaned = text.replace("\xa0", " ")
    m = _PRICE_RE.search(cleaned)

    if not m:
        return None

    whole = m.group(1).replace(".", "").replace(" ", "")
    cents = m.group(2) or "00"

    try:
        return float(f"{whole}.{cents}")
    except ValueError:
        return None