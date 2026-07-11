"""Unit tests for twilio_client.py — signature verification only (send_whatsapp
hits the real Twilio API and is covered by manual verification, see Task 4)."""
import twilio_client
from conftest import compute_twilio_signature

AUTH_TOKEN = "test-auth-token-12345"
URL = "https://example.com/api/webhooks/twilio"
PARAMS = {"From": "whatsapp:+919812345001", "Body": "I'll pay by Friday", "To": "whatsapp:+14155238886"}


def test_verify_signature_valid(monkeypatch):
    monkeypatch.setattr(twilio_client, "_AUTH_TOKEN", AUTH_TOKEN)
    sig = compute_twilio_signature(AUTH_TOKEN, URL, PARAMS)
    assert twilio_client.verify_signature(URL, PARAMS, sig) is True


def test_verify_signature_invalid(monkeypatch):
    monkeypatch.setattr(twilio_client, "_AUTH_TOKEN", AUTH_TOKEN)
    assert twilio_client.verify_signature(URL, PARAMS, "not-a-real-signature") is False


def test_verify_signature_wrong_url(monkeypatch):
    monkeypatch.setattr(twilio_client, "_AUTH_TOKEN", AUTH_TOKEN)
    sig = compute_twilio_signature(AUTH_TOKEN, URL, PARAMS)
    assert twilio_client.verify_signature("https://example.com/different-path", PARAMS, sig) is False


def test_verify_signature_no_auth_token_configured(monkeypatch):
    monkeypatch.setattr(twilio_client, "_AUTH_TOKEN", "")
    sig = compute_twilio_signature(AUTH_TOKEN, URL, PARAMS)
    assert twilio_client.verify_signature(URL, PARAMS, sig) is False


def test_enabled_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(twilio_client, "_ACCOUNT_SID", "")
    monkeypatch.setattr(twilio_client, "_AUTH_TOKEN", "")
    monkeypatch.setattr(twilio_client, "_WHATSAPP_FROM", "")
    assert twilio_client.enabled() is False


def test_enabled_true_when_configured(monkeypatch):
    monkeypatch.setattr(twilio_client, "_ACCOUNT_SID", "ACxxxx")
    monkeypatch.setattr(twilio_client, "_AUTH_TOKEN", "tokxxxx")
    monkeypatch.setattr(twilio_client, "_WHATSAPP_FROM", "+14155238886")
    assert twilio_client.enabled() is True
