# Twilio WhatsApp Adapter — Design

Status: approved
Date: 2026-07-11

## Problem

`messaging.py` already auto-selects the `whatsapp` channel when `TWILIO_*` env
vars are present (`active_channel()`), but `send_chase()`'s whatsapp branch is
a stub that always returns `delivered: False, error: "not implemented"`.
Inbound WhatsApp replies have no route at all — only Telegram does. This
closes both gaps so WhatsApp reaches parity with the existing Telegram
integration: outbound send, inbound reply routing into the same
`handle_inbound_reply` intent classifier, signature-verified webhook.

## Target environment

Twilio Trial account + WhatsApp Sandbox (free, no card charge for sandbox
usage). Confirmed working for this project:
- Sandbox number: `+14155238886`
- Join code already used by one real tester (`whatsapp:+917738962742`)
- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` in `backend/.env` (renamed from
  `ACCOUNT_SID`/`AUTH_TOKEN` as part of this work)

Sandbox constraints (ops, not code):
- Any WhatsApp number must text `join <code>` to the sandbox number once
  before it can send/receive. Seeded demo debtor numbers are fake and can't
  do this — for a live demo, point one seed debtor's `phone_whatsapp` at a
  real joined number.
- Sandbox session expires after 72h of inactivity per participant; must
  rejoin. No code fix for this — a demo-day reminder only.
- Twilio's sandbox "when a message comes in" webhook field currently points
  at Twilio's own demo echo bot; must be manually repointed in the Twilio
  console to `<PUBLIC_BASE_URL>/api/webhooks/twilio` once the backend is
  publicly reachable. No API to set this (unlike Telegram's `setWebhook`).

## Architecture

Mirrors two existing patterns exactly — no new shape introduced:
- `razorpay_client.py`'s sync-SDK-with-`enabled()`/`status()` client module
- `telegram_client.py` + `/api/webhooks/telegram`'s signature-verified
  inbound webhook, routed into `handle_inbound_reply`

### 1. `backend/twilio_client.py` (new)

```
enabled() -> bool                         # all three TWILIO_* env vars set
send_whatsapp(to_e164: str, text: str) -> dict
    # client.messages.create(from_=f"whatsapp:{FROM}", to=f"whatsapp:{to}", body=text)
    # returns {sid, status}; raises on Twilio API error (caller wraps)
verify_signature(url: str, params: dict, signature: str) -> bool
    # twilio.request_validator.RequestValidator(AUTH_TOKEN).validate(...)
status() -> dict                          # {enabled, from_number}
```

### 2. `backend/messaging.py`

Replace the stub `whatsapp` branch (current lines ~72-79) with a real call:

```python
if channel == "whatsapp":
    to = debtor.get("phone_whatsapp")
    if not to:
        return {"channel": "whatsapp", "delivered": False, "target": None,
                 "error": "debtor has no phone_whatsapp on file"}
    try:
        resp = await asyncio.to_thread(twilio_client.send_whatsapp, to, text)
        return {"channel": "whatsapp", "delivered": True, "target": to, "sid": resp["sid"]}
    except Exception as e:
        log.warning("twilio send failed: %s", e)
        return {"channel": "whatsapp", "delivered": False, "target": to, "error": str(e)}
```

`asyncio.to_thread` used because the Twilio SDK is sync/blocking — same
concern `razorpay_client` already has un-addressed; not fixing that one here,
just not repeating the anti-pattern in new code on the hot send path.

No signature change to `send_chase()`, so `agent.py` needs zero edits.

### 3. `backend/server.py` — new `POST /api/webhooks/twilio`

- Twilio posts `application/x-www-form-urlencoded`, not JSON — read via
  `await request.form()`.
- Verify `X-Twilio-Signature` header against the full callback URL + form
  params via `twilio_client.verify_signature`; return 403 on failure (matches
  the Telegram/Razorpay hard-reject convention already in this codebase).
- Extract `From` (strip `whatsapp:` prefix) and `Body`.
- **Routing differs from Telegram: no linking step.** The debtor's WhatsApp
  number is already stored in `debtor.phone_whatsapp` from seed data — match
  the inbound `From` against it directly. Then route to
  `debtor.last_outbound_invoice_id`, falling back to the most-overdue
  open invoice for that debtor (same fallback `agent.py`/`telegram_webhook`
  already implements) → `handle_inbound_reply(db, invoice_id, text)`.
- If no debtor matches the `From` number: log and return 200 with no action
  (don't 403 — an unmatched number isn't a signature/auth failure).

### 4. Config

Add to `backend/.env` (done): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_WHATSAPP_FROM`. `PUBLIC_BASE_URL` reused from the Telegram setup —
still needs to be set to the backend's public URL for signature verification
and for the manual Twilio console webhook field.

### 5. `backend/requirements.txt`

Add `twilio` (official Python SDK).

## Platform constraint (accepted, not solved)

Outside the Twilio Sandbox, Meta only allows freeform business-initiated
WhatsApp text within a 24h window after the customer's last inbound message,
or via pre-approved templates otherwise. The Sandbox sidesteps this for demo
purposes (freeform works once a number has joined). First-touch production
chases outside the sandbox would need template approval — explicitly out of
scope for this pass; if hit during testing it surfaces as `delivery.error`
through the existing never-raise contract, same as any other send failure.

## Testing

- Unit: `twilio_client.verify_signature` against known-good/known-bad
  signatures (fixture from Twilio's own test vectors).
- Integration: send to the joined sandbox number (`+917738962742`), confirm
  `chase_event.delivered=True` and `channel=whatsapp`.
- Integration: reply from that number, confirm webhook 403s on bad signature,
  200s + routes into `handle_inbound_reply` on valid signature.
- Manual: repoint sandbox webhook URL, confirm end-to-end reply → intent
  classification → response send round-trip, matching what's already
  verified for Telegram in `memory/PRD.md`.
