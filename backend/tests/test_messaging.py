"""Unit tests for messaging.py's whatsapp branch. Monkeypatches
messaging.twilio_client so no real Twilio API call is made."""
import asyncio

import messaging


def test_send_chase_whatsapp_success(monkeypatch):
    monkeypatch.setattr(messaging, "active_channel", lambda: "whatsapp")
    monkeypatch.setattr(
        messaging.twilio_client, "send_whatsapp",
        lambda to, text: {"sid": "SM_test_123", "status": "queued"},
    )
    debtor = {"phone_whatsapp": "+919812345001"}
    result = asyncio.run(messaging.send_chase(debtor, "your invoice is due"))
    assert result == {
        "channel": "whatsapp",
        "delivered": True,
        "target": "+919812345001",
        "sid": "SM_test_123",
    }


def test_send_chase_whatsapp_send_failure(monkeypatch):
    monkeypatch.setattr(messaging, "active_channel", lambda: "whatsapp")

    def _raise(to, text):
        raise RuntimeError("Twilio API error: 21610 unsubscribed recipient")

    monkeypatch.setattr(messaging.twilio_client, "send_whatsapp", _raise)
    debtor = {"phone_whatsapp": "+919812345001"}
    result = asyncio.run(messaging.send_chase(debtor, "your invoice is due"))
    assert result["channel"] == "whatsapp"
    assert result["delivered"] is False
    assert result["target"] == "+919812345001"
    assert "21610" in result["error"]


def test_send_chase_whatsapp_no_phone_on_file(monkeypatch):
    monkeypatch.setattr(messaging, "active_channel", lambda: "whatsapp")
    result = asyncio.run(messaging.send_chase({}, "your invoice is due"))
    assert result == {
        "channel": "whatsapp",
        "delivered": False,
        "target": None,
        "error": "debtor has no phone_whatsapp on file",
    }
