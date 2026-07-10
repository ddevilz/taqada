"""Razorpay Payment Links integration.

Creates hosted payment links per invoice, verifies webhook signatures, and
falls back to a mock upi:// deep link if the Razorpay API key is missing or
the API call fails (so demos work offline).

Reference:
- Payment Links API: https://razorpay.com/docs/payments/payment-links/apis/
- Webhook verification: https://razorpay.com/docs/webhooks/validate-test/
"""
from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Optional

import razorpay

log = logging.getLogger("taqada.razorpay")

_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()

_client: Optional[razorpay.Client] = None


def enabled() -> bool:
    return bool(_KEY_ID and _KEY_SECRET)


def webhook_configured() -> bool:
    return bool(_WEBHOOK_SECRET)


def _get_client() -> Optional[razorpay.Client]:
    global _client
    if not enabled():
        return None
    if _client is None:
        _client = razorpay.Client(auth=(_KEY_ID, _KEY_SECRET))
    return _client


def create_payment_link(invoice: dict, debtor: dict) -> dict:
    """Create a Razorpay Payment Link for an invoice.

    Returns dict with keys: provider, link_id (or None), short_url, status.
    On failure or when Razorpay is not configured, returns provider='mock_upi'
    with a upi:// deep link so the demo still works.
    """
    from aging import upi_deep_link  # local import to avoid cycles

    client = _get_client()
    if client is None:
        return {
            "provider": "mock_upi",
            "link_id": None,
            "short_url": upi_deep_link(invoice),
            "status": "created",
        }

    amount_paise = int(round(float(invoice["amount_inr"]) * 100))
    # Razorpay reference_id must be <=40 chars and unique per link create.
    ref_id = f"tq-{invoice['id'][:8]}-{invoice['invoice_number']}"[:40]

    customer = {"name": debtor.get("name") or "Debtor"}
    contact = (debtor.get("phone_whatsapp") or "").lstrip("+")
    if contact:
        customer["contact"] = contact

    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "reference_id": ref_id,
        "description": f"Invoice {invoice['invoice_number']} · Taqada",
        "customer": customer,
        "notify": {"sms": False, "email": False},  # we send via WhatsApp
        "reminder_enable": False,
        "notes": {
            "invoice_id": invoice["id"],
            "invoice_number": invoice["invoice_number"],
            "debtor_id": invoice.get("debtor_id", ""),
        },
    }

    try:
        link = client.payment_link.create(payload)
        return {
            "provider": "razorpay",
            "link_id": link.get("id"),
            "short_url": link.get("short_url"),
            "status": link.get("status", "created"),
        }
    except Exception as e:  # noqa: BLE001
        log.warning("Razorpay create_payment_link failed for %s: %s", invoice.get("invoice_number"), e)
        return {
            "provider": "mock_upi",
            "link_id": None,
            "short_url": upi_deep_link(invoice),
            "status": "fallback",
            "error": str(e),
        }


def cancel_payment_link(link_id: str) -> bool:
    client = _get_client()
    if client is None or not link_id:
        return False
    try:
        client.payment_link.cancel(link_id)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("Razorpay cancel failed for %s: %s", link_id, e)
        return False


def verify_webhook_signature(raw_body: str, signature: str) -> bool:
    """Return True if signature is valid. Uses razorpay SDK utility."""
    if not _WEBHOOK_SECRET:
        return False
    client = _get_client()
    if client is None:
        # We can still verify with the SDK's utility even without auth
        client = razorpay.Client(auth=(_KEY_ID or "x", _KEY_SECRET or "x"))
    try:
        client.utility.verify_webhook_signature(raw_body, signature, _WEBHOOK_SECRET)
        return True
    except razorpay.errors.SignatureVerificationError:
        return False
    except Exception as e:  # noqa: BLE001
        log.warning("verify_webhook_signature error: %s", e)
        return False


def status() -> dict:
    return {
        "enabled": enabled(),
        "webhook_configured": webhook_configured(),
        "key_id_prefix": (_KEY_ID[:12] + "…") if _KEY_ID else None,
    }
