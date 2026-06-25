# config.py
# Central configuration for Waypoint — all tunable parameters live here

import os
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()

# ── API ───────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Models
LLM_REASONING_MODEL = "claude-sonnet-4-6"      # Ambiguous case reasoning
LLM_GENERATION_MODEL = "claude-haiku-4-5-20251001"  # Outreach message drafting

# ── Token Budget ──────────────────────────────────────────────────────────────
MAX_TOKENS_PER_RUN = 50_000     # Hard cap on total tokens used per batch run
MAX_OUTPUT_TOKENS = 200         # Max tokens per LLM response

# ── Credential Thresholds ─────────────────────────────────────────────────────
# Total credits required to complete each program type
CREDENTIAL_THRESHOLDS = {
    "certificate": 30,
    "associates": 60,
    "bachelors": 120,
}

# ── Flag Thresholds ───────────────────────────────────────────────────────────
MOMENTUM_CREDIT_THRESHOLD = 12  # Minimum credits completed to trigger momentum flag
ONE_COURSE_AWAY_CREDITS = 3     # Credits remaining threshold for one-course-away flag

# ── Data Paths ────────────────────────────────────────────────────────────────
CSV_PATH = "data/synthetic/redrock_students.csv"
DB_PATH = "waypoint.db"

# ── Registration Deadline ─────────────────────────────────────────────────────
# Set this to the actual upcoming registration deadline for your institution
# Format: YYYY-MM-DD
REGISTRATION_DEADLINE = "2025-08-01"