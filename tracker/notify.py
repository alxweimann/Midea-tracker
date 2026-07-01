"""Telegram-Benachrichtigung."""

from __future__ import annotations

import html
import logging
import sys
from collections import defaultdict

import requests

from .config import Secrets
from .models import CHANNEL_STORE, CONDITION_NEW, Offer

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT = 20


def send_telegram(text: str, secrets: Secrets) -> bool:
    if not secrets.telegram_configured:
        log.warning("Telegram nicht konfiguriert – überspringe Versand.")
        return False

    url = TELEGRAM_API.format(token=secrets.telegram_bot_token)

    try:
        resp = requests.post(
            url,
            json={
                "chat_id": secrets.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Telegram-Versand fehlgeschlagen: %s", exc)
        return False

    return True


def _price_badge(o: Offer) -> str:
    name = (o.product_name or o.title or "").lower()
    price = float(o.price or 0)

    if "cool" in name or "8.000" in name or "8000" in name:
        if price <= 600:
            return "🟢 Hammerpreis"
        if price <= 700:
            return "🟡 Sehr gut"
        if price <= 800:
            return "🟠 Okay"
        return "🔴 Zu teuer"

    if price <= 800:
        return "🟢 Hammerpreis"
    if price <= 900:
        return "🟡 Sehr gut"
    if price <= 1000:
        return "🟠 Okay"
    return "🔴 Zu teuer"


def _offer_line(o: Offer) -> list[str]:
    cond = "Neu" if o.condition == CONDITION_NEW else "Gebraucht"
    where = html.escape(o.merchant or o.source.capitalize())
    badge = _price_badge(o)

    loc = ""
    if o.channel == CHANNEL_STORE and o.store_name:
        dist = f", ~{o.distance_km:.0f} km" if o.distance_km is not None else ""
        loc = f" Filiale {html.escape(o.store_name)}{dist}"

    return [
        f"• {badge}",
        f"  💶 {o.price:.2f} € – {where} [{cond}]{loc}",
        f'  🔗 <a href="{html.escape(o.url)}">Zum Angebot</a>',
    ]


def format_offers(offers: list[Offer]) -> str:
    by_product: dict[str, list[Offer]] = defaultdict(list)

    for o in offers:
        by_product[o.product_name or o.title].append(o)

    lines: list[str] = []

    for product_name, group in by_product.items():
        n = len(group)

        lines.append(
            f"🚨 <b>{html.escape(product_name)} verfügbar!</b> "
            f"({n} neue{'s' if n == 1 else ''} Angebot{'e' if n != 1 else ''})"
        )
        lines.append("")

        for o in sorted(group, key=lambda x: x.price):
            lines.extend(_offer_line(o))
            lines.append("")

    return "\n".join(lines).rstrip()


def format_heartbeat(summary, now) -> str:
    ts = now.strftime("%d.%m.%Y %H:%M UTC")

    lines = [
        f"✅ Tracker aktiv – {ts}",
        f"Quellen mit Daten: {summary.sources_with_data}/{summary.attempts}",
        f"Bestellbar im Budget: {summary.buyable_count}",
    ]

    if summary.best_by_product:
        lines.append("")
        lines.append("Günstigster Preis je Gerät:")

        for name, (price, merchant) in sorted(summary.best_by_product.items()):
            lines.append(
                f"• {html.escape(name)}: {price:.2f} € ({html.escape(merchant)})"
            )
    else:
        lines.append("")
        lines.append("Aktuell kein Preis für die beobachteten Geräte gefunden.")

    return "\n".join(lines)


def format_outage(summary) -> str:
    return (
        "⚠️ Tracker: Totalausfall\n\n"
        f"Keine einzige Quelle lieferte Daten ({summary.attempts} Abrufversuche).\n"
        "Vermutlich sind die Shops gerade alle geblockt oder es gibt ein Problem.\n"
        "Solange dieser Zustand anhält, kann eine echte Verfügbarkeit übersehen werden."
    )


def _self_test() -> int:
    logging.basicConfig(level=logging.INFO)
    secrets = Secrets.from_env()

    ok = send_telegram(
        "✅ Testnachricht vom Midea PortaSplit Tracker – Benachrichtigungen funktionieren.",
        secrets,
    )

    print("Gesendet." if ok else "Fehlgeschlagen.")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_self_test())

    print("Nutze: python -m tracker.notify --test")
