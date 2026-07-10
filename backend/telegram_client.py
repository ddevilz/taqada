"""Telegram Bot API client — outbound send + webhook management.

Uses direct HTTPS calls via httpx (no python-telegram-bot dependency, kept minimal).
Webhook auth uses the `secret_token` param of setWebhook + `X-Telegram-Bot-Api-Secret-Token`
header on inbound POSTs (official Telegram approach).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger("taqada.telegram")

_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()

_BASE = "https://api.telegram.org"


def enabled() -> bool:
    return bool(_TOKEN)


def webhook_secret() -> str:
    return _WEBHOOK_SECRET


def _url(method: str) -> str:
    return f"{_BASE}/bot{_TOKEN}/{method}"


async def _post(method: str, payload: dict, timeout: float = 10.0) -> dict:
    if not enabled():
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(_url(method), json=payload)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "status_code": r.status_code, "text": r.text}


async def send_message(chat_id: int | str, text: str, disable_web_page_preview: bool = False) -> dict:
    """Send a plain-text message. Telegram limit: 4096 chars per message."""
    payload = {
        "chat_id": chat_id,
        "text": text[:4090],
        "disable_web_page_preview": disable_web_page_preview,
    }
    return await _post("sendMessage", payload)


async def set_webhook(url: str) -> dict:
    """Register the webhook URL. Returns Telegram's response dict."""
    payload = {
        "url": url,
        "secret_token": _WEBHOOK_SECRET,
        "allowed_updates": ["message"],
    }
    return await _post("setWebhook", payload)


async def get_me() -> dict:
    return await _post("getMe", {})


async def get_webhook_info() -> dict:
    return await _post("getWebhookInfo", {})


_bot_username_cache: Optional[str] = None


async def bot_username() -> Optional[str]:
    """Return the bot username (cached). Needed for deep-link start URLs."""
    global _bot_username_cache
    if _bot_username_cache:
        return _bot_username_cache
    if not enabled():
        return None
    resp = await get_me()
    if resp.get("ok"):
        _bot_username_cache = resp.get("result", {}).get("username")
    return _bot_username_cache


def status() -> dict:
    return {
        "enabled": enabled(),
        "webhook_configured": bool(_WEBHOOK_SECRET),
        "bot_username": _bot_username_cache,
    }
