# Taqada — Product Requirements (living doc)

## Problem
Indian small businesses spend 14 hrs/wk chasing overdue receivables. Autonomous collections agent that chases debtors over WhatsApp with a UPI link, negotiates payment dates, and escalates through a 3-rung tone ladder whose final rung cites Section 43B(h) Income Tax Act + Section 16 MSMED Act.

## Architecture principle
Deterministic core, LLM at the edges.
- Code owns: aging, eligibility, interest math, rung selection, statutory gating, follow-up scheduling.
- LLM (Gemma via Fireworks) owns: message phrasing, inbound reply classification (JSON-constrained), negotiation phrasing.
- LLM never generates rupee amounts, dates, or section numbers — code computes and injects.

## Tech
Backend: FastAPI + MongoDB + Motor (no ObjectId leaks — insert with `dict(ev)` copy).
LLM: Fireworks AI OpenAI-compatible SDK, model `accounts/fireworks/models/gemma2-9b-it`.
  - Falls back to deterministic stub when `FIREWORKS_API_KEY` is empty (current build).
Frontend: React 19 (CRA), Fraunces/Space Grotesk/IBM Plex Mono, sharp-corner ledger aesthetic.

## Implemented (2026-07-08)
- [x] Data model: debtors, invoices, chase_events, inbound_messages, promises
- [x] Seed: 8 debtors + 28 invoices spanning all aging buckets, Udyam categories (incl. medium & unregistered for gate demo)
- [x] Aging module: days_overdue, statutory_limit_days, is_statutory_eligible, compute_accrued_interest (3x RBI, monthly compound), select_rung, upi_deep_link, format_inr (Indian grouping)
- [x] LLM module: 3-rung prompt templates + intent classifier (JSON schema, 2-retry) + stub fallback
- [x] Agent loop: `POST /api/agent/run` — priority = amount * days_overdue, promise-aware skip, rung-based chase
- [x] Inbound handler: classify → route (promise_to_pay bounded by MAX_EXTENSION_DAYS=30 with counter-offer; dispute/hostile/2x unclear → escalated_human; claims_paid → verify queue)
- [x] Dashboard 4 widgets: Aging buckets bar chart · Recovered-this-week hero · Live activity feed · Human escalation queue
- [x] Invoice ledger with rung/status/Udyam badges + filters (All, Overdue, Statutory, Promised, Escalated, Paid)
- [x] Invoice drawer with conversation view, Rung-1/2/3 message preview, statutory eligibility indicator, details
- [x] Demo controls: Run agent tick, Simulate debtor reply (with preset messages), Mark invoice paid

## P1 backlog
- [ ] APScheduler daily tick (currently on-demand only)
- [ ] Add FIREWORKS_API_KEY and validate live Gemma output
- [ ] MSME Samadhaan filing draft (PDF export)
- [ ] Multi-language chase (Hindi, Tamil, Marathi)
- [ ] Twilio production WhatsApp integration (currently DEMO_MODE)
- [ ] Real UPI payment link (Razorpay/Cashfree) + reconciliation webhook
- [ ] Tally / Zoho Books ledger sync

## P2 backlog
- [ ] Multi-tenant + auth
- [ ] AMD Dev Cloud vLLM/ROCm mirror as `LLM_BACKEND=selfhosted`
- [ ] Success-fee pricing: 1–2% of recovered auto-invoiced

## Constraints
- Solo dev, hackathon deadline 2026-07-11 15:00 UTC
- Not scored on speed/accuracy benchmarks — no evals

## 2026-07-10 · Testing iteration 1 fixes
- Fixed `llm._stub_classify`: added `didn't order`, `invoice is wrong` for disputes; added `'ll pay`, `pay in`, and a regex `in N (days|weeks|months)` for promise extraction. Both fixes verified via curl.
- Cleaned up duplicate `growth = ...` computation in `aging.compute_accrued_interest`.
- Backend pytest 15/17 → all core flows now working; test agent found no UI bugs.

## 2026-07-10 · Razorpay Payment Links + webhook (feature add)
- Added `razorpay_client.py`: `create_payment_link` (INR paise, notes.invoice_id for reconciliation) + `verify_webhook_signature` (razorpay SDK utility) + `cancel_payment_link`.
- Backend env: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`.
- `agent.chase_invoice` calls `ensure_payment_link` before message generation — reuses persisted link, embeds the `rzp.io/l/…` short_url in the WhatsApp message. Falls back to `upi://` mock link if Razorpay disabled or the API rejects (e.g. test-account amount cap).
- New endpoints:
  - `POST /api/payment-links/create` — manual link creation for an invoice.
  - `POST /api/webhooks/razorpay` — verifies X-Razorpay-Signature, handles `payment_link.paid` / `payment_link.partially_paid` → marks invoice paid + sets `reconciled_via=razorpay_webhook` + closes any pending promise as kept; handles `payment_link.expired` / `cancelled` → marks the link stale so next chase regenerates.
- `enrich_invoice` now surfaces `payment_link: {provider, short_url, link_id, status}`.
- Frontend header shows "Razorpay · live (test mode)" indicator.
- InvoiceDrawer Preview shows a "Razorpay live" or "Mock UPI" badge; Details tab shows the actual clickable link and `reconciled_via` after payment.
- Seed now includes three small (< ₹5,000) invoices — `INV-2601-S`, `INV-2602-S`, `INV-2603-S` — so live Razorpay links can be demoed on the test-mode account (which caps per-link amount).

### Verified end-to-end
- Real link created: `https://rzp.io/rzp/rjFR8Mwx` for INV-2601-S (₹4,500).
- Webhook with bad signature → HTTP 400.
- Webhook with valid HMAC-SHA256(secret=test12345) for `payment_link.paid` → invoice marked paid, `reconciled_via=razorpay_webhook`, `recovered_this_week` counter bumped.

## 2026-07-10 · Telegram Bot channel (fallback for Twilio)
- Added `telegram_client.py` — thin httpx wrapper for `sendMessage`, `setWebhook`, `getMe`, `getWebhookInfo`. Bot username cached on first call. Webhook auth via `X-Telegram-Bot-Api-Secret-Token` header (set via `setWebhook.secret_token`).
- Added `messaging.py` — channel router. Auto-selects: WhatsApp (Twilio) → Telegram → Demo based on env vars (`TWILIO_*` beats `TELEGRAM_BOT_TOKEN`). `send_chase(debtor, text)` returns `{channel, delivered, target, error?}`. Never raises; caller logs chase_event regardless.
- Backend env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `PUBLIC_BASE_URL`, `TWILIO_*` placeholders.
- Debtor doc gains: `telegram_chat_id`, `last_outbound_invoice_id` (to route inbound replies).
- chase_events gains: `channel`, `delivered`, `delivery_target`, `delivery_error`.
- On startup: if `TELEGRAM_BOT_TOKEN` set, call `getMe` (cache username) + `setWebhook(PUBLIC_BASE_URL + /api/webhooks/telegram, secret_token=…)`.
- New endpoints:
  - `POST /api/webhooks/telegram` — verifies secret header, handles `/start <debtor_id>` (auto-links chat_id), regular text (routes via `last_outbound_invoice_id` or the most-overdue invoice for that debtor into the existing `handle_inbound_reply` intent classifier).
  - `GET /api/debtors/{id}/telegram-link` — returns the deep-link URL and current link status.
  - `POST /api/debtors/link-telegram` — manual chat_id linking.
- Frontend:
  - Header now shows `Channel · telegram (@taqada_bot)` (or `whatsapp` / `demo`).
  - Activity feed rows show a per-message delivery pill (`✓ telegram` if delivered, `! telegram` if not, `demo` if channel is off).
  - InvoiceDrawer Details tab has a "Telegram channel" section with the deep-link URL + Copy / Open buttons; shows `✓ Linked · chat_id N` once the debtor has /start'd the bot.

### Verified end-to-end
- Bot registered as `@taqada_bot`, webhook set successfully on startup.
- `/api/webhooks/telegram` rejects requests without valid secret → 403.
- `/start <debtor_id>` via deep-link → debtor.telegram_chat_id updated, welcome message sent (real Telegram API call).
- Chase to a linked debtor made a real Telegram API call (fake chat_id → "chat not found" surfaces as `delivery_error`).
- Chase to an unlinked debtor still logs the chase_event but marks `delivered=False` with a clear error message.

## 2026-07-10 · Test credentials update
`test_credentials.md` unchanged — app still has no auth. Telegram: the seed debtors are not pre-linked; a real user must `/start` the `@taqada_bot` bot with a debtor-specific deep-link to receive messages.
