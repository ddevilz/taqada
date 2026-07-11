# Twilio WhatsApp Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stubbed WhatsApp send in `messaging.py` with a real Twilio integration, and add an inbound webhook so WhatsApp debtors get the same negotiate-by-reply flow Telegram debtors already have.

**Architecture:** New `twilio_client.py` (sync SDK wrapper, mirrors `razorpay_client.py`'s `enabled()`/`status()` shape). `messaging.py`'s whatsapp branch calls it via `asyncio.to_thread`. New `POST /api/webhooks/twilio` in `server.py` verifies `X-Twilio-Signature` and routes into the existing `handle_inbound_reply`, matching the `/api/webhooks/telegram` pattern minus the linking step (WhatsApp number is already on the debtor doc).

**Tech Stack:** `twilio` Python SDK (sync), FastAPI `Request.form()` for the webhook, `asyncio.to_thread` to keep the blocking SDK call off the event loop.

## Global Constraints

- Target: Twilio Trial account + WhatsApp Sandbox (free). Sandbox number `+14155238886`. One real participant already joined: `whatsapp:+917738962742`.
- `backend/.env` already has `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM=+14155238886` (renamed from `ACCOUNT_SID`/`AUTH_TOKEN`).
- `send_chase()`'s return shape must stay `{channel, delivered, target, error?}` — `agent.py` depends on this and needs zero edits.
- Never raise out of `send_chase()` / the whatsapp branch — best-effort delivery, caller always logs the chase_event regardless (existing contract, see `messaging.py:41-46`).
- Webhook signature failures hard-reject with 403 (matches `/api/webhooks/telegram` and the Razorpay webhook convention already in `server.py`).
- No existing unit tests import backend modules directly (`backend/tests/backend_test.py` is pure HTTP-integration style against a live server). This plan adds the first direct-import unit tests and therefore a `conftest.py` to make that importable.

---

### Task 1: `twilio_client.py` — SDK wrapper + signature verification

**Files:**
- Create: `backend/twilio_client.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_twilio_client.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces: `twilio_client.enabled() -> bool`, `twilio_client.send_whatsapp(to_e164: str, text: str) -> dict` (returns `{"sid": str, "status": str}`, raises on any Twilio API error), `twilio_client.verify_signature(url: str, params: dict, signature: str) -> bool`, `twilio_client.status() -> dict`.

- [ ] **Step 1: Add the `twilio` SDK to requirements**

Add this line to `backend/requirements.txt` (keep alphabetical position, after `tzlocal`):

```
twilio==9.4.3
```

Install it:

Run: `cd backend && pip install twilio==9.4.3`
Expected: `Successfully installed twilio-9.4.3 ...` (plus its deps: `PyJWT`, `aiohttp-retry` if not already present)

- [ ] **Step 2: Add `backend/tests/conftest.py` so tests can import backend modules directly**

```python
"""Makes `backend/` importable from `backend/tests/*.py` (e.g. `import messaging`,
`import twilio_client`) regardless of the cwd pytest is invoked from."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def compute_twilio_signature(auth_token: str, url: str, params: dict) -> str:
    """Twilio's documented request-signing algorithm: HMAC-SHA1 of the URL with
    each param's key+value appended in sorted-key order, base64-encoded.
    Shared by test_twilio_client.py (unit) and backend_test.py (integration)."""
    import base64
    import hashlib
    import hmac

    base = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    digest = hmac.new(auth_token.encode("utf-8"), base.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")
```

- [ ] **Step 3: Write the failing tests**

Create `backend/tests/test_twilio_client.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_twilio_client.py -v -n 0`
Expected: `ModuleNotFoundError: No module named 'twilio_client'` (module doesn't exist yet)

- [ ] **Step 5: Write `backend/twilio_client.py`**

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_twilio_client.py -v -n 0`
Expected: `6 passed`

- [ ] **Step 7: Commit**

```bash
cd backend && git add twilio_client.py tests/conftest.py tests/test_twilio_client.py requirements.txt
git commit -m "feat: add twilio_client for WhatsApp send + webhook signature verification"
```

---

### Task 2: Wire `messaging.py`'s whatsapp branch to `twilio_client`

**Files:**
- Modify: `backend/messaging.py:1-16` (imports), `backend/messaging.py:72-79` (whatsapp branch)
- Create: `backend/tests/test_messaging.py`

**Interfaces:**
- Consumes: `twilio_client.send_whatsapp(to_e164: str, text: str) -> dict` from Task 1 (raises on failure).
- Produces: no change to `messaging.send_chase(debtor: dict, text: str) -> dict`'s return shape — `agent.py` is untouched.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_messaging.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_messaging.py -v -n 0`
Expected: `AssertionError` on `test_send_chase_whatsapp_success` — current stub returns `{"channel": "whatsapp", "delivered": False, "target": ..., "error": "whatsapp send not implemented in this build"}`, not the success shape.

- [ ] **Step 3: Update `backend/messaging.py`**

Add `import asyncio` and `import twilio_client` to the top of the file (after the existing `import telegram_client`, `backend/messaging.py:13`):

```python
import asyncio
import logging
import os

import telegram_client
import twilio_client
```

Replace the whatsapp branch at `backend/messaging.py:72-79`:

```python
    if channel == "whatsapp":
        to = debtor.get("phone_whatsapp")
        if not to:
            return {
                "channel": "whatsapp",
                "delivered": False,
                "target": None,
                "error": "debtor has no phone_whatsapp on file",
            }
        try:
            resp = await asyncio.to_thread(twilio_client.send_whatsapp, to, text)
            return {"channel": "whatsapp", "delivered": True, "target": to, "sid": resp["sid"]}
        except Exception as e:  # noqa: BLE001
            log.warning("twilio send failed: %s", e)
            return {"channel": "whatsapp", "delivered": False, "target": to, "error": str(e)}
```

Also update `status()` (`backend/messaging.py:33-38`) to surface twilio status alongside telegram:

```python
def status() -> dict:
    return {
        "active": active_channel(),
        "whatsapp": {"configured": _twilio_configured(), **twilio_client.status()},
        "telegram": telegram_client.status(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_messaging.py -v -n 0`
Expected: `3 passed`

- [ ] **Step 5: Run the full existing suite to confirm no regression**

Run: `cd backend && python -m pytest tests/test_twilio_client.py tests/test_messaging.py -v -n 0`
Expected: `9 passed`

- [ ] **Step 6: Commit**

```bash
cd backend && git add messaging.py tests/test_messaging.py
git commit -m "feat: wire messaging.py whatsapp branch to twilio_client"
```

---

### Task 3: `POST /api/webhooks/twilio` — inbound reply routing

**Files:**
- Modify: `backend/server.py` — add imports, add new endpoint after the Telegram webhook section (after `backend/server.py:602`, before the `# App wiring` section)
- Modify: `backend/tests/backend_test.py` — add webhook tests at the end of the file

**Interfaces:**
- Consumes: `twilio_client.verify_signature(url, params, signature) -> bool` (Task 1), `agent.handle_inbound_reply(db, invoice_id, text) -> dict` (existing, unchanged).
- Produces: `POST /api/webhooks/twilio` — 403 on bad/missing signature, 200 `{"ok": True, ...}` otherwise.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/backend_test.py` (after the last existing test, `test_mark_paid_updates_recovered`):

```python
# -----------------------------------------------------------------------------
# Twilio WhatsApp webhook (inbound)
# -----------------------------------------------------------------------------
from conftest import compute_twilio_signature  # noqa: E402

TWILIO_WEBHOOK_URL = f"{API}/webhooks/twilio"


def test_twilio_webhook_rejects_bad_signature():
    params = {"From": "whatsapp:+919812345001", "Body": "hello", "To": "whatsapp:+14155238886"}
    r = requests.post(
        TWILIO_WEBHOOK_URL, data=params,
        headers={"X-Twilio-Signature": "not-a-real-signature"},
    )
    assert r.status_code == 403


def test_twilio_webhook_rejects_missing_signature():
    params = {"From": "whatsapp:+919812345001", "Body": "hello", "To": "whatsapp:+14155238886"}
    r = requests.post(TWILIO_WEBHOOK_URL, data=params)
    assert r.status_code == 403


def test_twilio_webhook_routes_reply_to_matching_debtor(all_invoices):
    # Rakesh Sharma, seeded debtor, phone +919812345001 (see backend/seed_data.py)
    inv = next(i for i in all_invoices if i["debtor"]["phone_whatsapp"] == "+919812345001")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    assert auth_token, "TWILIO_AUTH_TOKEN must be set on the running backend for this test"

    params = {"From": "whatsapp:+919812345001", "Body": "I will pay in 5 days", "To": "whatsapp:+14155238886"}
    sig = compute_twilio_signature(auth_token, TWILIO_WEBHOOK_URL, params)
    r = requests.post(TWILIO_WEBHOOK_URL, data=params, headers={"X-Twilio-Signature": sig})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["intent"] == "promise_to_pay"


def test_twilio_webhook_unmatched_number_returns_200():
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    assert auth_token, "TWILIO_AUTH_TOKEN must be set on the running backend for this test"

    params = {"From": "whatsapp:+919999999999", "Body": "hello", "To": "whatsapp:+14155238886"}
    sig = compute_twilio_signature(auth_token, TWILIO_WEBHOOK_URL, params)
    r = requests.post(TWILIO_WEBHOOK_URL, data=params, headers={"X-Twilio-Signature": sig})
    assert r.status_code == 200
    assert r.json().get("action") == "unmatched_number"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/backend_test.py -v -n 0 -k twilio_webhook`
Expected: `404` (`Not Found`) on all four — the endpoint doesn't exist yet. (Note: `test_twilio_webhook_routes_reply_to_matching_debtor` and `test_twilio_webhook_unmatched_number_returns_200` require a live server with `TWILIO_AUTH_TOKEN` set — same live-server assumption every other test in this file already makes.)

- [ ] **Step 3: Add the endpoint to `backend/server.py`**

Add to the imports near the top (after `import telegram_client`, `backend/server.py:27`):

```python
import twilio_client
```

Add this new section to `backend/server.py`, immediately after the Telegram webhook section ends (after the `telegram_webhook` function, which currently ends at line 602, and before the `# App wiring` comment at line 605):

```python
# ============================================================
# Twilio: WhatsApp webhook (inbound)
# ============================================================


@api.post("/webhooks/twilio")
async def twilio_webhook(request: Request):
    form = await request.form()
    params = dict(form)
    signature = request.headers.get("X-Twilio-Signature", "")

    public_base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    verify_url = f"{public_base}{request.url.path}" if public_base else str(request.url)

    if not twilio_client.verify_signature(verify_url, params, signature):
        log.warning("Twilio webhook signature verification FAILED")
        raise HTTPException(status_code=403, detail="invalid signature")

    from_number = (params.get("From") or "").removeprefix("whatsapp:")
    text = (params.get("Body") or "").strip()
    if not from_number or not text:
        return {"ok": True, "ignored": True}

    debtor = await db.debtors.find_one({"phone_whatsapp": from_number}, {"_id": 0})
    if not debtor:
        log.info("Twilio webhook: no debtor matches %s", from_number)
        return {"ok": True, "action": "unmatched_number"}

    invoice_id = debtor.get("last_outbound_invoice_id")
    if not invoice_id:
        inv = await db.invoices.find_one(
            {"debtor_id": debtor["id"], "status": {"$in": ["unpaid", "promised"]}},
            {"_id": 0},
            sort=[("due_date", 1)],
        )
        invoice_id = inv["id"] if inv else None

    if not invoice_id:
        return {"ok": True, "action": "no_open_invoice"}

    result = await handle_inbound_reply(db, invoice_id, text)
    return {"ok": True, **result}
```

- [ ] **Step 4: Run tests to verify they pass**

Restart the backend so it picks up the new route and the `.env` `TWILIO_*` values (`load_dotenv` only runs at process start):

Run: `cd backend && python -m pytest tests/backend_test.py -v -n 0 -k twilio_webhook`
Expected: `4 passed`

- [ ] **Step 5: Run the complete backend suite**

Run: `cd backend && python -m pytest -n 0`
Expected: all tests pass (existing suite + the 4 new webhook tests + Task 1/2's 9 tests)

- [ ] **Step 6: Commit**

```bash
cd backend && git add server.py tests/backend_test.py
git commit -m "feat: add POST /api/webhooks/twilio for inbound WhatsApp replies"
```

---

### Task 4: Manual end-to-end verification against the real Sandbox

No code changes — this task confirms the deployed system actually works against Twilio's real sandbox, the same way `memory/PRD.md` documents "Verified end-to-end" for Razorpay and Telegram.

**Files:** none (verification only — append results to `memory/PRD.md` under a new `## 2026-07-11 · Twilio WhatsApp Sandbox` heading, following the existing dated-entry format already used for the Razorpay and Telegram sections)

- [ ] **Step 1: Point the sandbox webhook at the real backend**

In the Twilio Console → WhatsApp Sandbox Settings → "When a message comes in," replace `https://timberwolf-mastiff-9776.twil.io/demo-reply` with `<PUBLIC_BASE_URL>/api/webhooks/twilio` (method `POST`). `PUBLIC_BASE_URL` must be set in `backend/.env` and the backend must be reachable at that URL (ngrok tunnel or the actual deploy host).

- [ ] **Step 2: Confirm config surfaces the new channel**

Run: `curl -s <BACKEND_URL>/api/config | python3 -m json.tool`
Expected: `"messaging": {"active": "whatsapp", "whatsapp": {"configured": true, "enabled": true, "from_number": "+14155238886"}, ...}`

- [ ] **Step 3: Point one seed debtor at the real joined number**

Run:
```bash
curl -s -X POST <BACKEND_URL>/api/debtors/link-telegram -d '{}' # (n/a, ignore — no whatsapp-link endpoint needed; phone_whatsapp already IS the routing key)
```
Instead: temporarily edit `backend/seed_data.py`'s first debtor's `phone_whatsapp` to `"+917738962742"` (the already-joined sandbox participant) for this manual test, or directly `db.debtors.update_one` via mongo shell. Re-seed is not required — a direct update is enough since the seed only runs when the collection is empty (`backend/server.py:627-630`).

- [ ] **Step 4: Trigger a real chase and confirm delivery**

Run: `curl -s -X POST <BACKEND_URL>/api/agent/chase -d '{"invoice_id": "<that debtor'"'"'s unpaid invoice id>"}' -H 'Content-Type: application/json' | python3 -m json.tool`
Expected: `delivery.channel == "whatsapp"`, `delivery.delivered == true`, a real WhatsApp message arrives on the joined phone.

- [ ] **Step 5: Reply from the phone and confirm the round trip**

From the joined WhatsApp number, reply e.g. "I'll pay in 5 days." Confirm:
- The Twilio Sandbox console shows the webhook fired without error.
- `GET <BACKEND_URL>/api/invoices/<invoice_id>` shows a new entry in `inbound_messages` with `classified_intent: "promise_to_pay"` and a new entry in `promises`.
- A confirmation WhatsApp message arrives back on the phone.

- [ ] **Step 6: Record results in `memory/PRD.md`**

Append a new dated section documenting what was verified, following the exact format of the existing `## 2026-07-10 · Telegram Bot channel` section (what was tested, what passed, any surprises — e.g. sandbox join friction, 72h expiry).

---

## Plan Self-Review

**Spec coverage:** `twilio_client.py` (Task 1) ✓. `messaging.py` real send (Task 2) ✓. `/api/webhooks/twilio` with signature verification + phone-based routing, no linking step (Task 3) ✓. `requirements.txt` (Task 1, Step 1) ✓. Config additions (already done in `.env` per the design doc; no code task needed). Sandbox constraints and manual console step (Task 4) ✓. Testing section from the spec (unit signature tests, integration send/reply, manual repoint) ✓ — covered across Tasks 1, 2, 3, 4.

**Type consistency:** `send_chase()` return shape `{channel, delivered, target, error?, sid?}` used identically in Task 2's tests and Task 3's endpoint expectations. `twilio_client.verify_signature(url: str, params: dict, signature: str) -> bool` signature matches its Task 1 definition and Task 3's call site. `handle_inbound_reply(db, invoice_id, text) -> dict` reused unchanged from `agent.py`.

**No placeholders:** every step has complete, runnable code — no TODOs.
