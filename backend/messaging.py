"""Channel router: picks WhatsApp (Twilio) or Telegram or demo based on env.

Auto-selection order:
1. If TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_WHATSAPP_FROM are set → 'whatsapp'
2. Else if TELEGRAM_BOT_TOKEN is set → 'telegram'
3. Else → 'demo' (log only)
"""
from __future__ import annotations

import logging
import os

import telegram_client

log = logging.getLogger("taqada.messaging")


def _twilio_configured() -> bool:
    return all(
        os.environ.get(k, "").strip()
        for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")
    )


def active_channel() -> str:
    if _twilio_configured():
        return "whatsapp"
    if telegram_client.enabled():
        return "telegram"
    return "demo"


def status() -> dict:
    return {
        "active": active_channel(),
        "whatsapp": {"configured": _twilio_configured()},
        "telegram": telegram_client.status(),
    }


async def send_chase(debtor: dict, text: str) -> dict:
    """Send an outbound chase message via the active channel. Best-effort — a
    send failure MUST NOT raise; caller logs the chase event regardless.

    Returns dict: {channel, delivered, target, error?}
    """
    channel = active_channel()

    if channel == "telegram":
        chat_id = debtor.get("telegram_chat_id")
        if not chat_id:
            return {
                "channel": "telegram",
                "delivered": False,
                "target": None,
                "error": "debtor not linked to Telegram — share the /start deep-link first",
            }
        try:
            resp = await telegram_client.send_message(chat_id, text)
            if resp.get("ok"):
                return {"channel": "telegram", "delivered": True, "target": str(chat_id)}
            return {
                "channel": "telegram",
                "delivered": False,
                "target": str(chat_id),
                "error": resp.get("description") or str(resp)[:200],
            }
        except Exception as e:  # noqa: BLE001
            log.warning("telegram send failed: %s", e)
            return {"channel": "telegram", "delivered": False, "target": str(chat_id), "error": str(e)}

    if channel == "whatsapp":
        # Twilio not yet implemented — placeholder for future.
        return {
            "channel": "whatsapp",
            "delivered": False,
            "target": debtor.get("phone_whatsapp"),
            "error": "whatsapp send not implemented in this build",
        }

    return {"channel": "demo", "delivered": False, "target": debtor.get("phone_whatsapp")}
