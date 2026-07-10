"""Configuration + statutory constants.

All statutory numbers live here in code, never in the LLM.
"""
import os
from decimal import Decimal

# --- LLM / Fireworks ---
FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "").strip()
FIREWORKS_BASE_URL = os.environ.get(
    "FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"
)
# Pin the Gemma instruct model ID here. If Fireworks renames, change here only.
FIREWORKS_MODEL = os.environ.get(
    "FIREWORKS_MODEL", "accounts/fireworks/models/gemma2-9b-it"
)

# --- Statutory (India) ---
# Source: RBI bank rate as of build date. Update via env var when RBI revises.
# Ref: https://www.rbi.org.in
RBI_BANK_RATE = Decimal(os.environ.get("RBI_BANK_RATE", "6.25"))  # percent p.a.

# MSMED Act Section 15 — payment window
UNWRITTEN_AGREEMENT_DAYS = 15  # no written agreement
MAX_WRITTEN_AGREEMENT_DAYS = 45  # even if agreement says more, capped here

# MSMED Act Section 16 — 3x RBI bank rate, compounded monthly
INTEREST_MULTIPLIER = Decimal("3")

# Categories eligible for 43B(h) / Section 16 protection
ELIGIBLE_UDYAM_CATEGORIES = {"micro", "small"}

# --- Agent behaviour ---
MAX_EXTENSION_DAYS = int(os.environ.get("MAX_EXTENSION_DAYS", "30"))
DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() == "true"

# --- Payment link (mock UPI) ---
UPI_VPA = os.environ.get("UPI_VPA", "taqada.demo@upi")
UPI_PAYEE_NAME = os.environ.get("UPI_PAYEE_NAME", "Taqada Demo Supplier")

# --- Rung thresholds (days overdue) ---
RUNG_1_MIN = 1
RUNG_2_MIN = 8
RUNG_3_MIN = 21
