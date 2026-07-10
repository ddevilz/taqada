"""Taqada backend — FastAPI server, MongoDB, in-process agent loop."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Local imports (after load_dotenv so config sees env)
from aging import enrich_invoice, format_inr  # noqa: E402
from agent import handle_inbound_reply, run_agent_tick, ensure_payment_link  # noqa: E402
from config import DEMO_MODE  # noqa: E402
from llm import llm_status  # noqa: E402
import razorpay_client  # noqa: E402
from seed_data import seed_database  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("taqada")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Taqada API")
api = APIRouter(prefix="/api")


# ============================================================
# Health / config
# ============================================================


@api.get("/")
async def root():
    return {
        "service": "taqada",
        "demo_mode": DEMO_MODE,
        "llm": llm_status(),
        "razorpay": razorpay_client.status(),
    }


@api.get("/config")
async def get_config():
    from config import MAX_EXTENSION_DAYS, RBI_BANK_RATE

    return {
        "demo_mode": DEMO_MODE,
        "rbi_bank_rate_percent": float(RBI_BANK_RATE),
        "max_extension_days": MAX_EXTENSION_DAYS,
        "llm": llm_status(),
        "razorpay": razorpay_client.status(),
    }


# ============================================================
# Seed
# ============================================================


@api.post("/seed")
async def do_seed():
    result = await seed_database(db)
    return {"seeded": True, **result}


# ============================================================
# Debtors
# ============================================================


@api.get("/debtors")
async def list_debtors():
    debtors = await db.debtors.find({}, {"_id": 0}).to_list(500)
    return debtors


# ============================================================
# Invoices
# ============================================================


@api.get("/invoices")
async def list_invoices(status: Optional[str] = None):
    q = {}
    if status:
        q["status"] = status
    invoices = await db.invoices.find(q, {"_id": 0}).to_list(1000)
    # Attach debtor info + computed fields
    debtor_ids = {i["debtor_id"] for i in invoices}
    debtors = await db.debtors.find({"id": {"$in": list(debtor_ids)}}, {"_id": 0}).to_list(500)
    dmap = {d["id"]: d for d in debtors}
    enriched = []
    for inv in invoices:
        e = enrich_invoice(inv)
        e["debtor"] = dmap.get(inv["debtor_id"])
        enriched.append(e)
    # sort by days_overdue desc
    enriched.sort(key=lambda x: x["days_overdue"], reverse=True)
    return enriched


@api.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    inv = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "invoice not found")
    debtor = await db.debtors.find_one({"id": inv["debtor_id"]}, {"_id": 0})
    e = enrich_invoice(inv)
    e["debtor"] = debtor
    # Attach conversation
    chase_events = await db.chase_events.find(
        {"invoice_id": invoice_id}, {"_id": 0}
    ).sort("sent_at", 1).to_list(200)
    inbound = await db.inbound_messages.find(
        {"invoice_id": invoice_id}, {"_id": 0}
    ).sort("received_at", 1).to_list(200)
    promises = await db.promises.find(
        {"invoice_id": invoice_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(50)
    e["chase_events"] = chase_events
    e["inbound_messages"] = inbound
    e["promises"] = promises
    return e


# ============================================================
# Dashboard aggregates
# ============================================================


@api.get("/dashboard/summary")
async def dashboard_summary():
    invoices = await db.invoices.find({}, {"_id": 0}).to_list(2000)
    buckets = {"current": 0.0, "1-15": 0.0, "16-45": 0.0, "46-90": 0.0, "90+": 0.0}
    bucket_counts = {"current": 0, "1-15": 0, "16-45": 0, "46-90": 0, "90+": 0}
    total_outstanding = 0.0
    total_paid_this_week = 0.0
    total_paid_all_time = 0.0
    now = datetime.now(timezone.utc).date()

    weighted_days = 0.0
    for inv in invoices:
        e = enrich_invoice(inv)
        amt = float(inv["amount_inr"])
        status = inv.get("status")
        if status == "paid":
            total_paid_all_time += amt
            paid_date = inv.get("paid_date")
            if paid_date:
                try:
                    pd = datetime.fromisoformat(paid_date).date()
                    if (now - pd).days <= 7:
                        total_paid_this_week += amt
                except Exception:
                    pass
        else:
            total_outstanding += amt
            b = e["aging_bucket"]
            buckets[b] += amt
            bucket_counts[b] += 1
            weighted_days += amt * max(0, e["days_overdue"])

    dso = (weighted_days / total_outstanding) if total_outstanding > 0 else 0.0

    escalated = await db.invoices.count_documents({"status": "escalated_human"})
    promised = await db.invoices.count_documents({"status": "promised"})

    return {
        "buckets": [
            {"key": k, "amount": buckets[k], "count": bucket_counts[k], "formatted": format_inr(buckets[k])}
            for k in ["current", "1-15", "16-45", "46-90", "90+"]
        ],
        "total_outstanding": total_outstanding,
        "total_outstanding_formatted": format_inr(total_outstanding),
        "recovered_this_week": total_paid_this_week,
        "recovered_this_week_formatted": format_inr(total_paid_this_week),
        "recovered_all_time": total_paid_all_time,
        "recovered_all_time_formatted": format_inr(total_paid_all_time),
        "dso_days": round(dso, 1),
        "escalated_count": escalated,
        "promised_count": promised,
    }


@api.get("/dashboard/activity")
async def dashboard_activity(limit: int = 40):
    chases = await db.chase_events.find({}, {"_id": 0}).sort("sent_at", -1).to_list(limit)
    inbound = await db.inbound_messages.find({}, {"_id": 0}).sort("received_at", -1).to_list(limit)

    # Enrich with invoice + debtor
    inv_ids = list({*[c["invoice_id"] for c in chases], *[i["invoice_id"] for i in inbound]})
    invoices = await db.invoices.find({"id": {"$in": inv_ids}}, {"_id": 0}).to_list(1000)
    imap = {i["id"]: i for i in invoices}
    debtor_ids = list({i["debtor_id"] for i in invoices})
    debtors = await db.debtors.find({"id": {"$in": debtor_ids}}, {"_id": 0}).to_list(500)
    dmap = {d["id"]: d for d in debtors}

    combined = []
    for c in chases:
        inv = imap.get(c["invoice_id"], {})
        dbtr = dmap.get(inv.get("debtor_id"))
        combined.append({
            "type": "outbound",
            "id": c["id"],
            "at": c["sent_at"],
            "rung": c["rung"],
            "text": c["message_text"],
            "invoice_number": inv.get("invoice_number"),
            "invoice_id": c["invoice_id"],
            "debtor_name": dbtr["name"] if dbtr else None,
            "debtor_company": dbtr["company"] if dbtr else None,
            "amount_formatted": format_inr(inv["amount_inr"]) if inv else None,
        })
    for m in inbound:
        inv = imap.get(m["invoice_id"], {})
        dbtr = dmap.get(inv.get("debtor_id"))
        combined.append({
            "type": "inbound",
            "id": m["id"],
            "at": m["received_at"],
            "intent": m.get("classified_intent"),
            "confidence": m.get("confidence"),
            "text": m["raw_text"],
            "invoice_number": inv.get("invoice_number"),
            "invoice_id": m["invoice_id"],
            "debtor_name": dbtr["name"] if dbtr else None,
            "debtor_company": dbtr["company"] if dbtr else None,
        })
    combined.sort(key=lambda x: x["at"], reverse=True)
    return combined[:limit]


@api.get("/dashboard/escalations")
async def dashboard_escalations():
    invoices = await db.invoices.find(
        {"status": "escalated_human"}, {"_id": 0}
    ).to_list(200)
    debtor_ids = list({i["debtor_id"] for i in invoices})
    debtors = await db.debtors.find({"id": {"$in": debtor_ids}}, {"_id": 0}).to_list(200)
    dmap = {d["id"]: d for d in debtors}
    out = []
    for inv in invoices:
        e = enrich_invoice(inv)
        e["debtor"] = dmap.get(inv["debtor_id"])
        # Get last inbound message for context
        last = await db.inbound_messages.find(
            {"invoice_id": inv["id"]}, {"_id": 0}
        ).sort("received_at", -1).to_list(1)
        e["last_inbound"] = last[0] if last else None
        out.append(e)
    out.sort(key=lambda x: x["days_overdue"], reverse=True)
    return out


# ============================================================
# Agent controls
# ============================================================


@api.post("/agent/run")
async def agent_run():
    result = await run_agent_tick(db)
    return result


class ChaseRequest(BaseModel):
    invoice_id: str


@api.post("/agent/chase")
async def agent_chase_one(req: ChaseRequest):
    inv = await db.invoices.find_one({"id": req.invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "invoice not found")
    from agent import chase_invoice as _chase
    result = await _chase(db, inv)
    return result


class SimulateReplyRequest(BaseModel):
    invoice_id: str
    text: str = Field(..., min_length=1, max_length=1000)


@api.post("/agent/simulate-reply")
async def agent_simulate_reply(req: SimulateReplyRequest):
    result = await handle_inbound_reply(db, req.invoice_id, req.text)
    return result


class MarkPaidRequest(BaseModel):
    invoice_id: str


@api.post("/demo/mark-paid")
async def demo_mark_paid(req: MarkPaidRequest):
    inv = await db.invoices.find_one({"id": req.invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "invoice not found")
    now = datetime.now(timezone.utc)
    await db.invoices.update_one(
        {"id": req.invoice_id},
        {"$set": {"status": "paid", "paid_date": now.date().isoformat()}},
    )
    # mark promise as kept if pending
    await db.promises.update_many(
        {"invoice_id": req.invoice_id, "status": "pending"},
        {"$set": {"status": "kept"}},
    )
    return {"marked_paid": True, "invoice_id": req.invoice_id, "amount": inv["amount_inr"]}


# ============================================================
# Preview a message without sending (for the message-preview modal)
# ============================================================


class PreviewRequest(BaseModel):
    invoice_id: str
    rung: Optional[int] = None  # if None, uses select_rung


@api.post("/messages/preview")
async def preview_message(req: PreviewRequest):
    from aging import (
        compute_accrued_interest,
        days_overdue,
        days_past_statutory,
        is_statutory_eligible,
        select_rung,
        statutory_limit_days,
        upi_deep_link,
    )
    from llm import generate_chase_message

    inv = await db.invoices.find_one({"id": req.invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "invoice not found")
    debtor = await db.debtors.find_one({"id": inv["debtor_id"]}, {"_id": 0})
    rung = req.rung if req.rung is not None else max(1, select_rung(inv))
    if rung == 0:
        rung = 1
    eligible, reason = is_statutory_eligible(inv)
    interest = compute_accrued_interest(inv) if eligible else 0
    # Reuse persisted link if present; do NOT create a new Razorpay link for a
    # preview (avoids polluting Razorpay with unused links).
    persisted = inv.get("payment_link") or {}
    pay_url = persisted.get("short_url") or upi_deep_link(inv)
    ctx = {
        "debtor_name": debtor["name"],
        "invoice_number": inv["invoice_number"],
        "formatted_amount": format_inr(inv["amount_inr"]),
        "days_overdue": days_overdue(inv),
        "upi_link": pay_url,
        "statutory_eligible": eligible,
        "statutory_limit_days": statutory_limit_days(inv),
        "days_past_statutory": days_past_statutory(inv),
        "formatted_interest": format_inr(interest),
    }
    message = generate_chase_message(rung, ctx)
    return {
        "rung": rung,
        "message": message,
        "statutory_eligible": eligible,
        "eligibility_reason": reason,
        "accrued_interest_formatted": format_inr(interest),
        "payment_link": {
            "provider": persisted.get("provider", "mock_upi"),
            "short_url": pay_url,
            "link_id": persisted.get("link_id"),
        },
    }


# ============================================================
# Razorpay Payment Links + webhook
# ============================================================


class CreateLinkRequest(BaseModel):
    invoice_id: str


@api.post("/payment-links/create")
async def create_link_for_invoice(req: CreateLinkRequest):
    inv = await db.invoices.find_one({"id": req.invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "invoice not found")
    link = await ensure_payment_link(db, inv)
    return link


@api.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    raw = (await request.body()).decode("utf-8")
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not razorpay_client.verify_webhook_signature(raw, signature):
        log.warning("Razorpay webhook signature verification FAILED")
        raise HTTPException(status_code=400, detail="invalid signature")

    import json as _json
    try:
        payload = _json.loads(raw)
    except Exception:
        raise HTTPException(400, "invalid json")

    event = payload.get("event", "")
    log.info("Razorpay webhook received: %s", event)

    if event in {"payment_link.paid", "payment_link.partially_paid"}:
        # Payload shape: payload.payload.payment_link.entity
        entity = (
            payload.get("payload", {})
            .get("payment_link", {})
            .get("entity", {})
        )
        link_id = entity.get("id")
        notes = entity.get("notes") or {}
        invoice_id = notes.get("invoice_id")

        # Prefer notes.invoice_id; fall back to link_id lookup.
        inv = None
        if invoice_id:
            inv = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not inv and link_id:
            inv = await db.invoices.find_one({"payment_link.link_id": link_id}, {"_id": 0})

        if not inv:
            log.warning("Razorpay webhook: no matching invoice for link_id=%s", link_id)
            return {"received": True, "matched": False}

        now = datetime.now(timezone.utc)
        await db.invoices.update_one(
            {"id": inv["id"]},
            {
                "$set": {
                    "status": "paid",
                    "paid_date": now.date().isoformat(),
                    "payment_link.status": "paid",
                    "reconciled_via": "razorpay_webhook",
                    "reconciled_at": now.isoformat(),
                }
            },
        )
        # Mark any pending promise as kept
        await db.promises.update_many(
            {"invoice_id": inv["id"], "status": "pending"},
            {"$set": {"status": "kept"}},
        )
        return {"received": True, "matched": True, "invoice_id": inv["id"]}

    if event in {"payment_link.expired", "payment_link.cancelled"}:
        entity = (
            payload.get("payload", {})
            .get("payment_link", {})
            .get("entity", {})
        )
        link_id = entity.get("id")
        if link_id:
            await db.invoices.update_one(
                {"payment_link.link_id": link_id},
                {"$set": {"payment_link.status": event.split(".", 1)[1]}},
            )
        return {"received": True, "action": "link_deactivated"}

    return {"received": True, "ignored": event}


# ============================================================
# App wiring
# ============================================================

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    log.info("Taqada starting. DEMO_MODE=%s, LLM=%s", DEMO_MODE, llm_status())
    # Auto-seed if empty (so a fresh pod boots into a demoable state)
    count = await db.invoices.count_documents({})
    if count == 0:
        log.info("empty invoices collection → seeding demo data")
        await seed_database(db)


@app.on_event("shutdown")
async def shutdown():
    client.close()
