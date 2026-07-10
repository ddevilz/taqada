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
