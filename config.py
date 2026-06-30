# config.py
# Central configuration for Waypoint — all tunable parameters live here

import os
from datetime import date, datetime
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

# ── Ingestion Limits ──────────────────────────────────────────────────────────
# Waypoint is sized for a single institution's student population, not
# arbitrary input. These caps reject obviously-too-large files outright
# rather than attempting to load them into memory uncapped.
MAX_CSV_FILE_SIZE_MB = 10
MAX_CSV_ROWS = 5_000

# ── API Resilience ────────────────────────────────────────────────────────────
# Tuned for low-connectivity environments — the anthropic SDK's default
# connect timeout (5s) is aggressive for a genuinely slow rural connection.
API_CONNECT_TIMEOUT_SECONDS = 20
API_MAX_RETRIES = 3

# ── Registration Deadline ─────────────────────────────────────────────────────
# Set this to the actual upcoming registration deadline for your institution
# Format: YYYY-MM-DD
REGISTRATION_DEADLINE = "2026-08-01"


def validate_config() -> list[str]:
    """
    Sanity-check the manually-set, per-institution values above.
    Returns a list of human-readable warnings (empty if nothing looks wrong).
    These values are documented in the README as one-line edits an admin
    makes per deployment — nothing enforces they were actually updated, so
    this catches the most common way that goes stale or gets mistyped.
    """
    warnings = []

    try:
        deadline = datetime.strptime(REGISTRATION_DEADLINE, "%Y-%m-%d").date()
        if deadline < date.today():
            warnings.append(
                f"REGISTRATION_DEADLINE ({REGISTRATION_DEADLINE}) is in the past. "
                "Update it in config.py to your institution's actual upcoming "
                "registration deadline — it's shown directly to Claude and in "
                "drafted outreach emails."
            )
    except (ValueError, TypeError):
        warnings.append(
            f"REGISTRATION_DEADLINE ({REGISTRATION_DEADLINE!r}) is not a valid "
            "YYYY-MM-DD date."
        )

    for program, threshold in CREDENTIAL_THRESHOLDS.items():
        if not isinstance(threshold, (int, float)) or threshold <= 0:
            warnings.append(
                f"CREDENTIAL_THRESHOLDS['{program}'] = {threshold!r} should be "
                "a positive number of credits."
            )

    return warnings