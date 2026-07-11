"""Twilio WhatsApp client — outbound send + inbound signature verification.

Reference:
- WhatsApp messaging: https://www.twilio.com/docs/whatsapp/api
- Request signature validation: https://www.twilio.com/docs/usage/webhooks/webhooks-security
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from twilio.request_validator import RequestValidator
from twilio.rest import Client

log = logging.getLogger("taqada.twilio")

_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()

_client: Optional[Client] = None


def enabled() -> bool:
    return bool(_ACCOUNT_SID and _AUTH_TOKEN and _WHATSAPP_FROM)


def _get_client() -> Optional[Client]:
    global _client
    if not enabled():
        return None
    if _client is None:
        _client = Client(_ACCOUNT_SID, _AUTH_TOKEN)
    return _client


def send_whatsapp(to_e164: str, text: str) -> dict:
    """Send a WhatsApp message via Twilio. Raises on any SDK/API error —
    caller (messaging.py) is responsible for catching and logging."""
    client = _get_client()
    if client is None:
        raise RuntimeError("twilio not configured (missing TWILIO_* env vars)")
    msg = client.messages.create(
        from_=f"whatsapp:{_WHATSAPP_FROM}",
        to=f"whatsapp:{to_e164}",
        body=text,
    )
    return {"sid": msg.sid, "status": msg.status}


def verify_signature(url: str, params: dict, signature: str) -> bool:
    """Return True if the X-Twilio-Signature header is valid for this exact
    URL + form params. False (not raise) if unconfigured or invalid."""
    if not _AUTH_TOKEN:
        return False
    validator = RequestValidator(_AUTH_TOKEN)
    try:
        return validator.validate(url, params, signature)
    except Exception as e:  # noqa: BLE001
        log.warning("twilio verify_signature error: %s", e)
        return False


def status() -> dict:
    return {"enabled": enabled(), "from_number": _WHATSAPP_FROM or None}
