"""Deterministic core: aging, eligibility, interest math.

The LLM never computes any number in this file. All figures are calculated here
and injected into prompts as strings.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from config import (
    ELIGIBLE_UDYAM_CATEGORIES,
    INTEREST_MULTIPLIER,
    MAX_WRITTEN_AGREEMENT_DAYS,
    RBI_BANK_RATE,
    RUNG_1_MIN,
    RUNG_2_MIN,
    RUNG_3_MIN,
    UNWRITTEN_AGREEMENT_DAYS,
    UPI_PAYEE_NAME,
    UPI_VPA,
)


def _to_date(v: Any) -> date:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        return datetime.fromisoformat(v).date()
    raise ValueError(f"cannot parse date: {v!r}")


def today() -> date:
    return datetime.now(timezone.utc).date()


def days_overdue(invoice: dict) -> int:
    """Days past due_date. Negative = not yet due."""
    due = _to_date(invoice["due_date"])
    return (today() - due).days


def statutory_limit_days(invoice: dict) -> int:
    """Section 15 limit: 15 days if no written agreement, else agreed date capped at 45."""
    if invoice.get("has_written_agreement"):
        return MAX_WRITTEN_AGREEMENT_DAYS
    return UNWRITTEN_AGREEMENT_DAYS


def is_statutory_eligible(invoice: dict) -> tuple[bool, str]:
    """Returns (eligible, reason). Only micro/small suppliers are covered by
    Section 43B(h) / Section 16 leverage, AND only after the statutory limit passes."""
    cat = (invoice.get("supplier_udyam_category") or "").lower()
    if cat not in ELIGIBLE_UDYAM_CATEGORIES:
        return False, f"supplier category '{cat}' not eligible (must be micro or small)"

    d = days_overdue(invoice)
    limit = statutory_limit_days(invoice)
    days_past_limit = d - limit
    if days_past_limit <= 0:
        return False, f"within statutory limit ({limit} days)"
    return True, "eligible"


def days_past_statutory(invoice: dict) -> int:
    """Days past the applicable Section 15 limit (min 0)."""
    return max(0, days_overdue(invoice) - statutory_limit_days(invoice))


def compute_accrued_interest(invoice: dict) -> Decimal:
    """MSMED Section 16: interest at 3x RBI bank rate, compounded MONTHLY,
    starting from the appointed day (i.e., end of statutory limit).

    Formula: principal * ((1 + monthly_rate) ** months_elapsed - 1)
    Where monthly_rate = (3 * RBI_BANK_RATE / 100) / 12 and months_elapsed is
    computed from days_past_statutory / 30 (fractional).
    """
    dpl = days_past_statutory(invoice)
    if dpl <= 0:
        return Decimal("0.00")

    principal = Decimal(str(invoice["amount_inr"]))
    annual_rate = (INTEREST_MULTIPLIER * RBI_BANK_RATE) / Decimal("100")
    monthly_rate = annual_rate / Decimal("12")
    months = Decimal(dpl) / Decimal("30")

    # Compound: P * ((1 + r)^n - 1). Decimal**Decimal can fail on fractional
    # exponents on some Python versions — fall back to float in that case.
    try:
        growth = (Decimal("1") + monthly_rate) ** months
    except Exception:
        growth = Decimal(str((1 + float(monthly_rate)) ** float(months)))

    interest = principal * (growth - Decimal("1"))
    return interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def aging_bucket(invoice: dict) -> str:
    d = days_overdue(invoice)
    if d <= 0:
        return "current"
    if d <= 15:
        return "1-15"
    if d <= 45:
        return "16-45"
    if d <= 90:
        return "46-90"
    return "90+"


def select_rung(invoice: dict) -> int:
    """Returns rung 1/2/3 based on days overdue. relationship_value=high softens by one."""
    d = days_overdue(invoice)
    if d < RUNG_1_MIN:
        return 0  # not overdue yet
    if d < RUNG_2_MIN:
        rung = 1
    elif d < RUNG_3_MIN:
        rung = 2
    else:
        rung = 3

    if invoice.get("relationship_value") == "high" and rung > 1:
        rung -= 1
    return rung


def upi_deep_link(invoice: dict) -> str:
    """Mock UPI deep link. Format per NPCI spec."""
    amount = Decimal(str(invoice["amount_inr"])).quantize(Decimal("0.01"))
    note = f"Invoice {invoice.get('invoice_number', '')}"
    # URL-safe encoding of payee name
    from urllib.parse import quote
    return (
        f"upi://pay?pa={UPI_VPA}"
        f"&pn={quote(UPI_PAYEE_NAME)}"
        f"&am={amount}"
        f"&cu=INR"
        f"&tn={quote(note)}"
    )


def format_inr(amount) -> str:
    """Indian number formatting: 1,50,000 not 150,000."""
    a = Decimal(str(amount)).quantize(Decimal("0.01"))
    sign = "-" if a < 0 else ""
    a = abs(a)
    whole, _, frac = f"{a:.2f}".partition(".")
    # Indian grouping: last 3 digits, then groups of 2
    if len(whole) <= 3:
        grouped = whole
    else:
        head, tail = whole[:-3], whole[-3:]
        # break head into groups of 2 from right
        chunks = []
        while len(head) > 2:
            chunks.insert(0, head[-2:])
            head = head[:-2]
        if head:
            chunks.insert(0, head)
        grouped = ",".join(chunks) + "," + tail
    return f"{sign}₹{grouped}.{frac}"


def enrich_invoice(invoice: dict) -> dict:
    """Attach computed fields for API responses (does not persist)."""
    eligible, reason = is_statutory_eligible(invoice)
    return {
        **invoice,
        "days_overdue": days_overdue(invoice),
        "statutory_limit_days": statutory_limit_days(invoice),
        "days_past_statutory": days_past_statutory(invoice),
        "aging_bucket": aging_bucket(invoice),
        "selected_rung": select_rung(invoice),
        "statutory_eligible": eligible,
        "eligibility_reason": reason,
        "accrued_interest_inr": float(compute_accrued_interest(invoice)) if eligible else 0.0,
        "upi_link": upi_deep_link(invoice),
        "formatted_amount": format_inr(invoice["amount_inr"]),
    }
