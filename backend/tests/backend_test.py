"""Taqada backend integration tests.

Covers:
- Health/config endpoints
- Seed idempotency
- Invoices/Debtors listing
- Dashboard (summary/activity/escalations)
- Agent tick, simulate-reply (promise/dispute/counter-offer), mark-paid
- Aging math (days_overdue, statutory_limit, past_statutory, bucket, rung)
- Interest math for statutory-eligible invoice
- Statutory eligibility gate (medium/unregistered NOT eligible)
- Message preview across rungs (Rung 3 citations vs no-citation gate)
"""
import os
import re
import requests
import pytest
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session", autouse=True)
def seed_once():
    r = requests.post(f"{API}/seed", timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def all_invoices():
    r = requests.get(f"{API}/invoices", timeout=15)
    assert r.status_code == 200
    return r.json()


# -----------------------------------------------------------------------------
# Health / config
# -----------------------------------------------------------------------------
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    d = r.json()
    assert d["service"] == "taqada"
    assert d["demo_mode"] is True
    assert d["llm"]["backend"] == "stub"


def test_config():
    r = requests.get(f"{API}/config")
    assert r.status_code == 200
    d = r.json()
    assert d["rbi_bank_rate_percent"] == 6.25
    assert d["max_extension_days"] == 30
    assert d["demo_mode"] is True


# -----------------------------------------------------------------------------
# Seed idempotency
# -----------------------------------------------------------------------------
def test_seed_idempotent():
    r1 = requests.post(f"{API}/seed").json()
    r2 = requests.post(f"{API}/seed").json()
    assert r1.get("seeded") is True and r2.get("seeded") is True
    inv = requests.get(f"{API}/invoices").json()
    assert len(inv) == 28, f"expected 28 invoices, got {len(inv)}"
    debtors = requests.get(f"{API}/debtors").json()
    assert len(debtors) == 8


# -----------------------------------------------------------------------------
# Invoices
# -----------------------------------------------------------------------------
def test_invoices_list_no_objectid(all_invoices):
    assert len(all_invoices) == 28
    # No _id leak
    assert all("_id" not in i for i in all_invoices)
    # Required computed fields
    sample = all_invoices[0]
    for k in ("days_overdue", "aging_bucket", "selected_rung", "statutory_eligible",
              "accrued_interest_inr", "upi_link", "formatted_amount", "debtor"):
        assert k in sample


def test_invoice_detail_has_conversation(all_invoices):
    inv_id = all_invoices[0]["id"]
    r = requests.get(f"{API}/invoices/{inv_id}")
    assert r.status_code == 200
    d = r.json()
    assert "chase_events" in d and "inbound_messages" in d and "promises" in d


# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------
def test_dashboard_summary():
    r = requests.get(f"{API}/dashboard/summary")
    assert r.status_code == 200
    d = r.json()
    keys = [b["key"] for b in d["buckets"]]
    assert keys == ["current", "1-15", "16-45", "46-90", "90+"]
    assert "recovered_this_week_formatted" in d


def test_dashboard_activity():
    r = requests.get(f"{API}/dashboard/activity")
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_dashboard_escalations():
    r = requests.get(f"{API}/dashboard/escalations")
    assert r.status_code == 200 and isinstance(r.json(), list)


# -----------------------------------------------------------------------------
# INV-2352 aging + interest math (spec)
# -----------------------------------------------------------------------------
def _find(all_invoices, inv_num):
    for i in all_invoices:
        if i["invoice_number"] == inv_num:
            return i
    return None


def test_inv2352_aging_and_interest(all_invoices):
    inv = _find(all_invoices, "INV-2352")
    assert inv, "INV-2352 not in seed"
    assert inv["days_overdue"] == 125
    assert inv["statutory_limit_days"] == 15
    assert inv["days_past_statutory"] == 110
    assert inv["aging_bucket"] == "90+"
    assert inv["selected_rung"] == 3
    assert inv["statutory_eligible"] is True
    interest = inv["accrued_interest_inr"]
    assert 15500 <= interest <= 17500, f"interest out of expected band: {interest}"


def test_statutory_gate_medium_ineligible(all_invoices):
    inv = _find(all_invoices, "INV-2350")
    assert inv, "INV-2350 not in seed"
    assert inv["supplier_udyam_category"] in ("medium", "unregistered")
    assert inv["statutory_eligible"] is False
    assert inv["accrued_interest_inr"] == 0.0


# -----------------------------------------------------------------------------
# Message preview: Rung 3 citation gating
# -----------------------------------------------------------------------------
def test_preview_rung3_eligible_cites_law(all_invoices):
    inv = _find(all_invoices, "INV-2352")
    r = requests.post(f"{API}/messages/preview", json={"invoice_id": inv["id"], "rung": 3})
    assert r.status_code == 200
    d = r.json()
    msg = d["message"]
    assert "Section 15" in msg
    assert "Section 16" in msg or "3× the RBI" in msg or "3x the RBI" in msg
    assert "43B" in msg
    assert d["statutory_eligible"] is True


def test_preview_rung3_ineligible_no_citation(all_invoices):
    inv = _find(all_invoices, "INV-2350")
    r = requests.post(f"{API}/messages/preview", json={"invoice_id": inv["id"], "rung": 3})
    assert r.status_code == 200
    d = r.json()
    msg = d["message"]
    assert "43B" not in msg
    assert "Section 15" not in msg
    assert d["statutory_eligible"] is False
    assert "not eligible" in (d.get("eligibility_reason") or "").lower()


# -----------------------------------------------------------------------------
# Agent tick
# -----------------------------------------------------------------------------
def test_agent_tick():
    r = requests.post(f"{API}/agent/run")
    assert r.status_code == 200
    d = r.json()
    assert "chased" in d and "scanned" in d
    assert d["scanned"] >= 1


# -----------------------------------------------------------------------------
# Simulate reply: promise / dispute / long promise counter-offer
# -----------------------------------------------------------------------------
def test_simulate_promise_to_pay(all_invoices):
    # pick an unpaid invoice
    inv = next(i for i in all_invoices if i["status"] == "unpaid")
    r = requests.post(f"{API}/agent/simulate-reply", json={
        "invoice_id": inv["id"], "text": "I'll pay by next Friday",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["intent"] == "promise_to_pay"
    assert d["action"] == "promise_logged"
    # invoice moves to promised
    inv2 = requests.get(f"{API}/invoices/{inv['id']}").json()
    assert inv2["status"] == "promised"


def test_simulate_dispute_escalates(all_invoices):
    inv = next(i for i in all_invoices if i["status"] == "unpaid" and i["invoice_number"] != "INV-2352")
    r = requests.post(f"{API}/agent/simulate-reply", json={
        "invoice_id": inv["id"],
        "text": "This invoice is wrong, we didn't order this",
    })
    d = r.json()
    assert d["intent"] == "dispute"
    assert d["action"] == "escalated"
    inv2 = requests.get(f"{API}/invoices/{inv['id']}").json()
    assert inv2["status"] == "escalated_human"


def test_simulate_long_promise_counter_offer(all_invoices):
    inv = next(i for i in all_invoices
               if i["status"] == "unpaid" and i["invoice_number"] not in ("INV-2352",))
    r = requests.post(f"{API}/agent/simulate-reply", json={
        "invoice_id": inv["id"], "text": "I'll pay in 6 months",
    })
    d = r.json()
    assert d["intent"] == "promise_to_pay"
    # Reply should mention counter-offer
    assert d["reply"] and ("could we settle" in d["reply"].lower() or "instead" in d["reply"].lower())


# -----------------------------------------------------------------------------
# Mark paid → recovered counter increases
# -----------------------------------------------------------------------------
def test_mark_paid_updates_recovered(all_invoices):
    summary_before = requests.get(f"{API}/dashboard/summary").json()
    inv = next(i for i in all_invoices if i["status"] == "unpaid")
    r = requests.post(f"{API}/demo/mark-paid", json={"invoice_id": inv["id"]})
    assert r.status_code == 200
    inv2 = requests.get(f"{API}/invoices/{inv['id']}").json()
    assert inv2["status"] == "paid"
    summary_after = requests.get(f"{API}/dashboard/summary").json()
    assert summary_after["recovered_this_week"] >= summary_before["recovered_this_week"] + inv["amount_inr"] - 0.01
