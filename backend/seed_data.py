"""Seed 25-30 synthetic invoices across aging buckets, debtors, Udyam categories."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import uuid

DEBTORS = [
    {"name": "Rakesh Sharma", "company": "Bharat Electronics Traders", "phone_whatsapp": "+919812345001", "relationship_value": "high", "language_pref": "en"},
    {"name": "Priya Iyer",    "company": "Coromandel Textiles",       "phone_whatsapp": "+919812345002", "relationship_value": "normal", "language_pref": "en"},
    {"name": "Vikram Mehta",  "company": "Mehta Auto Components",     "phone_whatsapp": "+919812345003", "relationship_value": "normal", "language_pref": "en"},
    {"name": "Anjali Deshmukh","company": "Konkan Foods Pvt Ltd",     "phone_whatsapp": "+919812345004", "relationship_value": "normal", "language_pref": "en"},
    {"name": "Suresh Nair",   "company": "Kerala Rubber Works",       "phone_whatsapp": "+919812345005", "relationship_value": "high", "language_pref": "en"},
    {"name": "Deepak Agarwal","company": "Marwari Chemicals & Co.",   "phone_whatsapp": "+919812345006", "relationship_value": "normal", "language_pref": "en"},
    {"name": "Fatima Sheikh", "company": "Hyderabad Pharma Distributors","phone_whatsapp":"+919812345007","relationship_value":"normal","language_pref":"en"},
    {"name": "Arjun Reddy",   "company": "Reddy Engineering",         "phone_whatsapp": "+919812345008", "relationship_value": "normal", "language_pref": "en"},
]

# (debtor_idx, invoice_number, amount, days_since_issue, agreement, category, status)
# days_since_issue = days ago the invoice was issued; due_date = issue + agreement_days
_INVOICES: list[tuple] = [
    # Current (not overdue)
    (0, "INV-2601", 45000, 5, 45, "small", "unpaid"),
    (1, "INV-2602", 22000, 10, 30, "micro", "unpaid"),
    (2, "INV-2603", 180000, 8, 45, "small", "unpaid"),

    # 1-15 overdue (rung 1)
    (3, "INV-2545", 65000, 20, 15, "micro", "unpaid"),      # 5 overdue
    (4, "INV-2546", 128000, 25, 15, "small", "unpaid"),     # 10 overdue
    (5, "INV-2547", 34500, 22, 15, "micro", "unpaid"),      # 7 overdue
    (0, "INV-2548", 92000, 28, 15, "small", "unpaid"),      # 13 overdue
    (6, "INV-2549", 15000, 24, 15, "micro", "unpaid"),      # 9 overdue

    # 16-45 overdue (rung 2)
    (1, "INV-2510", 210000, 65, 45, "small", "unpaid"),     # 20 overdue
    (2, "INV-2511", 78000, 45, 15, "micro", "unpaid"),      # 30 overdue
    (3, "INV-2512", 8000, 50, 15, "micro", "unpaid"),       # 35 overdue
    (4, "INV-2513", 155000, 70, 45, "small", "unpaid"),     # 25 overdue
    (7, "INV-2514", 42000, 55, 15, "micro", "unpaid"),      # 40 overdue

    # 46-90 overdue (rung 3 — statutory)
    (5, "INV-2440", 320000, 80, 15, "small", "unpaid"),     # 65 overdue, 50 past statutory
    (6, "INV-2441", 55000, 75, 15, "micro", "unpaid"),      # 60 overdue, 45 past statutory
    (0, "INV-2442", 445000, 110, 45, "small", "unpaid"),    # 65 overdue, 20 past statutory
    (2, "INV-2443", 96000, 95, 15, "small", "unpaid"),      # 80 overdue
    (7, "INV-2444", 28000, 90, 15, "micro", "unpaid"),      # 75 overdue

    # 90+ overdue — medium (INELIGIBLE — demonstrates gate)
    (1, "INV-2350", 380000, 130, 30, "medium", "unpaid"),   # 100 overdue, category=medium
    # 90+ overdue — unregistered (INELIGIBLE)
    (3, "INV-2351", 62000, 120, 15, "unregistered", "unpaid"),  # 105 overdue, unregistered

    # 90+ overdue eligible (rung 3 heavy)
    (4, "INV-2352", 275000, 140, 15, "small", "unpaid"),    # 125 overdue
    (5, "INV-2353", 118000, 135, 45, "small", "unpaid"),    # 90 overdue

    # Some already paid (contribute to Recovered counter)
    (0, "INV-2401", 175000, 40, 15, "small", "paid"),
    (2, "INV-2402", 88000, 35, 15, "micro", "paid"),
    (6, "INV-2403", 210000, 50, 45, "small", "paid"),
    (1, "INV-2404", 42000, 20, 15, "micro", "paid"),

    # One promised
    (4, "INV-2450", 145000, 60, 15, "small", "promised"),

    # One disputed
    (7, "INV-2451", 33000, 55, 15, "micro", "disputed"),
]


def _iso(d: date) -> str:
    return d.isoformat()


async def seed_database(db) -> dict:
    """Clear and seed all collections. Idempotent."""
    await db.debtors.delete_many({})
    await db.invoices.delete_many({})
    await db.chase_events.delete_many({})
    await db.inbound_messages.delete_many({})
    await db.promises.delete_many({})

    today = datetime.now(timezone.utc).date()
    debtor_ids: list[str] = []
    for d in DEBTORS:
        did = str(uuid.uuid4())
        debtor_ids.append(did)
        await db.debtors.insert_one({
            **d,
            "id": did,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    inv_count = 0
    for (didx, invnum, amount, days_ago, agreement_days, category, status) in _INVOICES:
        issue = today - timedelta(days=days_ago)
        acceptance = issue + timedelta(days=1)
        due = issue + timedelta(days=agreement_days)
        paid_date = None
        if status == "paid":
            paid_date = _iso(today - timedelta(days=max(1, days_ago - agreement_days - 5)))
        doc = {
            "id": str(uuid.uuid4()),
            "debtor_id": debtor_ids[didx],
            "invoice_number": invnum,
            "amount_inr": float(amount),
            "issue_date": _iso(issue),
            "acceptance_date": _iso(acceptance),
            "due_date": _iso(due),
            "has_written_agreement": agreement_days != 15,
            "supplier_udyam_category": category,
            "status": status,
            "paid_date": paid_date,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.invoices.insert_one(doc)
        inv_count += 1

    return {"debtors": len(DEBTORS), "invoices": inv_count}
