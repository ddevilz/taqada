"""Agent orchestration: rung selection → payment link → message generation → send → log.
Also handles inbound reply routing + negotiation."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from aging import (
    compute_accrued_interest,
    days_overdue,
    days_past_statutory,
    enrich_invoice,
    format_inr,
    is_statutory_eligible,
    select_rung,
    statutory_limit_days,
    upi_deep_link,
)
from config import MAX_EXTENSION_DAYS
from llm import classify_reply, generate_chase_message
import razorpay_client

log = logging.getLogger("taqada.agent")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_debtor(db, debtor_id: str) -> dict | None:
    return await db.debtors.find_one({"id": debtor_id}, {"_id": 0})


async def ensure_payment_link(db, invoice: dict) -> dict:
    """Return the active payment link for an invoice, creating one via Razorpay
    if none exists. Falls back to a mock upi:// link if Razorpay is disabled
    or the call fails.

    Persists the link on the invoice document so it's reused across chases.
    Returns dict with keys: provider, link_id, short_url, status.
    """
    existing = invoice.get("payment_link")
    if existing and existing.get("short_url") and existing.get("status") in {"created", "issued", "fallback"}:
        return existing

    debtor = await _get_debtor(db, invoice["debtor_id"]) or {}
    link = razorpay_client.create_payment_link(invoice, debtor)
    link["created_at"] = _now_iso()
    await db.invoices.update_one(
        {"id": invoice["id"]},
        {"$set": {"payment_link": link}},
    )
    invoice["payment_link"] = link
    return link


async def _log_chase(db, invoice: dict, rung: int, message: str) -> dict:
    ev = {
        "id": str(uuid.uuid4()),
        "invoice_id": invoice["id"],
        "debtor_id": invoice["debtor_id"],
        "rung": rung,
        "channel": "whatsapp_demo",
        "message_text": message,
        "sent_at": _now_iso(),
    }
    await db.chase_events.insert_one(dict(ev))
    return ev


async def chase_invoice(db, invoice: dict) -> dict:
    """Select rung, ensure payment link, generate & log message. Returns the chase_event."""
    debtor = await _get_debtor(db, invoice["debtor_id"])
    if not debtor:
        raise ValueError(f"debtor {invoice['debtor_id']} not found")

    rung = select_rung(invoice)
    if rung == 0:
        return {"skipped": True, "reason": "not_overdue"}

    eligible, reason = is_statutory_eligible(invoice)
    effective_rung = rung

    # Reuse or create a Razorpay Payment Link
    link = await ensure_payment_link(db, invoice)
    pay_url = link.get("short_url") or upi_deep_link(invoice)

    interest = compute_accrued_interest(invoice) if eligible else 0
    ctx = {
        "debtor_name": debtor["name"],
        "invoice_number": invoice["invoice_number"],
        "formatted_amount": format_inr(invoice["amount_inr"]),
        "days_overdue": days_overdue(invoice),
        "upi_link": pay_url,
        "statutory_eligible": eligible,
        "statutory_limit_days": statutory_limit_days(invoice),
        "days_past_statutory": days_past_statutory(invoice),
        "formatted_interest": format_inr(interest),
    }
    message = generate_chase_message(effective_rung, ctx)
    ev = await _log_chase(db, invoice, effective_rung, message)
    ev["payment_link"] = link
    return {"skipped": False, "chase_event": ev, "rung": effective_rung}


async def run_agent_tick(db) -> dict:
    """Scan all unpaid invoices, chase those that need chasing. Priority: amount * days_overdue."""
    invoices = await db.invoices.find(
        {"status": {"$in": ["unpaid", "promised"]}}, {"_id": 0}
    ).to_list(1000)

    # Score & sort
    scored = []
    for inv in invoices:
        d = days_overdue(inv)
        if d < 1:
            continue
        # Skip promised invoices whose promise date hasn't passed
        if inv.get("status") == "promised":
            # find latest promise
            pr = await db.promises.find_one(
                {"invoice_id": inv["id"], "status": "pending"}, {"_id": 0}
            )
            if pr:
                promise_date = datetime.fromisoformat(pr["promised_date"]).date()
                if promise_date >= datetime.now(timezone.utc).date():
                    continue
                # promise broken → mark and continue chasing
                await db.promises.update_one({"id": pr["id"]}, {"$set": {"status": "broken"}})
                await db.invoices.update_one({"id": inv["id"]}, {"$set": {"status": "unpaid"}})
        scored.append((float(inv["amount_inr"]) * d, inv))
    scored.sort(key=lambda x: x[0], reverse=True)

    events = []
    for _score, inv in scored:
        try:
            result = await chase_invoice(db, inv)
            if not result.get("skipped"):
                events.append(result["chase_event"])
        except Exception as e:  # noqa: BLE001
            log.exception("chase_invoice failed for %s: %s", inv.get("invoice_number"), e)
    return {"chased": len(events), "events": events, "scanned": len(invoices)}


async def handle_inbound_reply(db, invoice_id: str, text: str) -> dict:
    """Route inbound message: classify → act."""
    inv = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise ValueError(f"invoice {invoice_id} not found")

    classification = classify_reply(text)
    intent = classification["intent"]

    inbound_id = str(uuid.uuid4())
    await db.inbound_messages.insert_one({
        "id": inbound_id,
        "invoice_id": invoice_id,
        "debtor_id": inv["debtor_id"],
        "raw_text": text,
        "classified_intent": intent,
        "confidence": classification.get("confidence", 0),
        "notes": classification.get("notes", ""),
        "received_at": _now_iso(),
    })

    response_message = None
    action = intent

    if intent == "promise_to_pay":
        promised_str = classification.get("promised_date")
        today = datetime.now(timezone.utc).date()
        try:
            promised_date = datetime.fromisoformat(promised_str).date() if promised_str else today + timedelta(days=7)
        except Exception:
            promised_date = today + timedelta(days=7)

        max_allowed = today + timedelta(days=MAX_EXTENSION_DAYS)
        if promised_date > max_allowed:
            # counter-offer
            counter = max_allowed
            response_message = (
                f"Thanks for the update. {promised_date.isoformat()} is a bit far out — "
                f"could we settle on {counter.isoformat()} instead? That's the latest we can hold."
            )
            promised_date = counter

        # log promise
        await db.promises.insert_one({
            "id": str(uuid.uuid4()),
            "invoice_id": invoice_id,
            "promised_date": promised_date.isoformat(),
            "created_from_message_id": inbound_id,
            "status": "pending",
            "created_at": _now_iso(),
        })
        await db.invoices.update_one(
            {"id": invoice_id}, {"$set": {"status": "promised"}}
        )
        if response_message is None:
            response_message = (
                f"Noted, thank you. We'll expect payment by {promised_date.isoformat()}. "
                f"A confirmation link is on the way."
            )
        # log outbound as chase_event rung=0 (negotiation)
        await _log_chase(db, inv, 0, response_message)
        action = "promise_logged"

    elif intent in {"dispute", "hostile"}:
        await db.invoices.update_one(
            {"id": invoice_id}, {"$set": {"status": "escalated_human"}}
        )
        response_message = (
            "Understood. I'm flagging this to our accounts team who will reach out "
            "directly to resolve. Thank you for the note."
        )
        await _log_chase(db, inv, 0, response_message)
        action = "escalated"

    elif intent == "claims_paid":
        await db.invoices.update_one(
            {"id": invoice_id}, {"$set": {"status": "escalated_human"}}
        )
        response_message = (
            "Thanks — we'll verify the payment on our end and confirm shortly. "
            "If you have a UTR / transaction reference, please share it."
        )
        await _log_chase(db, inv, 0, response_message)
        action = "verify_pending"

    elif intent == "request_info":
        debtor = await _get_debtor(db, inv["debtor_id"])
        response_message = (
            f"Sure — invoice {inv['invoice_number']} for {format_inr(inv['amount_inr'])}, "
            f"issued {inv['issue_date']}, due {inv['due_date']}. Payment link: {upi_deep_link(inv)}"
        )
        await _log_chase(db, inv, 0, response_message)
        action = "info_sent"

    else:  # unclear
        # Count recent unclears — 2 in a row → escalate
        recent = await db.inbound_messages.find(
            {"invoice_id": invoice_id}, {"_id": 0}
        ).sort("received_at", -1).to_list(2)
        if len(recent) >= 2 and all(r.get("classified_intent") == "unclear" for r in recent):
            await db.invoices.update_one(
                {"id": invoice_id}, {"$set": {"status": "escalated_human"}}
            )
            response_message = (
                "I want to make sure I understand you correctly. I've asked our team to "
                "reach out directly to help."
            )
            action = "escalated_needs_human"
        else:
            response_message = "Sorry, could you clarify — are you asking for details, disputing, or planning to pay?"
        await _log_chase(db, inv, 0, response_message)

    return {
        "inbound_id": inbound_id,
        "intent": intent,
        "confidence": classification.get("confidence", 0),
        "action": action,
        "reply": response_message,
    }
