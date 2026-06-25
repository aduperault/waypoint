# waypoint/ingest.py
# CSV ingestion and normalization layer
# Handles messy real-world exports gracefully — bad data is flagged, not dropped

import pandas as pd
from datetime import datetime
from waypoint.db import initialize_db, clear_tables, insert_student, insert_data_issue
from config import CSV_PATH

# ── Field Name Aliases ────────────────────────────────────────────────────────
# Maps common SIS export column name variants to Waypoint's internal field names
FIELD_ALIASES = {
    "student_id":           ["student_id", "stu_id", "id", "studentid", "student id"],
    "first_name":           ["first_name", "firstname", "first"],
    "last_name":            ["last_name", "lastname", "last"],
    "program_type":         ["program_type", "program", "degree_type", "credential_type"],
    "program_name":         ["program_name", "program name", "degree_name"],
    "credits_completed":    ["credits_completed", "credits_earned", "earned_credits",
                             "total_credits", "cumulative_credits"],
    "credits_in_progress":  ["credits_in_progress", "current_credits", "enrolled_credits",
                             "credits_enrolled", "in_progress"],
    "next_term_registered": ["next_term_registered", "registered_next", "fall_registered",
                             "spring_registered", "next_registration"],
    "last_advisor_contact": ["last_contact", "last_advisor_contact", "advisor_contact",
                             "last_contact_date"],
    "enrollment_status":    ["enrollment_status", "status", "enroll_status"],
    "registration_hold":    ["registration_hold", "reg_hold", "hold", "reg hold"],
    "stop_out_history":     ["stop_out_history", "stop_out_terms", "stopout_terms",
                             "prior_stopouts"],
    "transfer_credits":     ["transfer_credits", "transfer_credit", "xfer_credits"],
}

# ── Program Type Normalization ────────────────────────────────────────────────
PROGRAM_TYPE_MAP = {
    "certificate":  ["certificate", "cert", "cert-ece", "cert-aot", "cert-dlc",
                     "cert-est", "cert-na"],
    "associates":   ["associates", "associate", "associate's", "as", "as-bus",
                     "as-la", "aas", "aa"],
    "bachelors":    ["bachelors", "bachelor", "bachelor's", "bs", "ba", "bas"],
}

# ── Date Formats to Try ───────────────────────────────────────────────────────
DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y",
    "%d-%b-%Y", "%B %d, %Y", "%Y%m%d"
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename CSV columns to Waypoint's internal field names using FIELD_ALIASES."""
    # Lowercase and strip all column names first
    df.columns = [c.strip().lower() for c in df.columns]

    rename_map = {}
    for internal_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = internal_name
                break

    df = df.rename(columns=rename_map)
    return df


def normalize_program_type(value: str) -> str:
    """Map legacy or variant program type codes to standard internal values."""
    if not value:
        return "associates"  # Default per spec
    val = str(value).strip().lower()
    for standard, variants in PROGRAM_TYPE_MAP.items():
        if val in variants:
            return standard
    return None  # Unrecognized — caller will flag this


def normalize_boolean(value) -> int:
    """Normalize Y/N, True/False, 1/0 to integer 1 or 0."""
    if pd.isna(value):
        return None
    val = str(value).strip().lower()
    if val in ["true", "yes", "y", "1"]:
        return 1
    if val in ["false", "no", "n", "0"]:
        return 0
    return None


def normalize_date(value) -> str:
    """Try multiple date formats and return ISO format string, or None if unparseable."""
    if pd.isna(value) or str(value).strip() == "":
        return None
    val = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None  # Caller will flag this


def ingest_csv(csv_path: str = CSV_PATH) -> dict:
    """
    Main ingestion function. Reads CSV, normalizes fields, writes to SQLite.
    Returns a summary dict with counts for the Streamlit UI.
    """
    initialize_db()
    clear_tables()

    summary = {
        "total_rows": 0,
        "records_loaded": 0,
        "records_skipped": 0,
        "data_issues": 0,
        "duplicates_removed": 0,
    }

    # ── Load CSV ──────────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(csv_path, dtype=str)  # Read everything as string first
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV not found at: {csv_path}")

    summary["total_rows"] = len(df)

    # ── Normalize Column Names ────────────────────────────────────────────────
    df = normalize_columns(df)

    # ── Deduplicate on student_id ─────────────────────────────────────────────
    if "student_id" in df.columns:
        before = len(df)
        # Keep the row with the highest credits_completed for each student_id
        if "credits_completed" in df.columns:
            df["credits_completed_sort"] = pd.to_numeric(
                df["credits_completed"], errors="coerce"
            ).fillna(0)
            df = df.sort_values("credits_completed_sort", ascending=False)
            df = df.drop_duplicates(subset=["student_id"], keep="first")
            df = df.drop(columns=["credits_completed_sort"])
        else:
            df = df.drop_duplicates(subset=["student_id"], keep="first")
        summary["duplicates_removed"] = before - len(df)

    # ── Process Each Row ──────────────────────────────────────────────────────
    for _, row in df.iterrows():
        student_id = str(row.get("student_id", "")).strip()

        # Skip rows with no student_id
        if not student_id or student_id.lower() == "nan":
            summary["records_skipped"] += 1
            continue

        issues = []  # Collect data quality issues for this student

        # Program type
        raw_program_type = row.get("program_type", "")
        program_type = normalize_program_type(raw_program_type)
        if program_type is None:
            issues.append(("unrecognized_program_type",
                           f"'{raw_program_type}' not recognized — defaulting to associates"))
            program_type = "associates"

        # Credits completed
        credits_completed = pd.to_numeric(
            row.get("credits_completed", ""), errors="coerce"
        )
        if pd.isna(credits_completed):
            issues.append(("missing_credits_completed",
                           "credits_completed field is blank — routed to human review"))
            credits_completed = None
        else:
            credits_completed = float(credits_completed)

        # Credits in progress
        credits_in_progress = pd.to_numeric(
            row.get("credits_in_progress", ""), errors="coerce"
        )
        if pd.isna(credits_in_progress):
            credits_in_progress = 0  # Default per spec

        # Next term registered
        next_term_registered = normalize_boolean(row.get("next_term_registered"))
        if next_term_registered is None:
            issues.append(("missing_next_term_registered",
                           "next_term_registered is null — treating as not registered"))
            next_term_registered = 0

        # Registration hold
        registration_hold = normalize_boolean(row.get("registration_hold"))
        # None here is meaningful — unknown hold status routes to LLM

        # Last advisor contact date
        raw_date = row.get("last_advisor_contact", "")
        last_advisor_contact = normalize_date(raw_date)
        if raw_date and not pd.isna(raw_date) and last_advisor_contact is None:
            issues.append(("unparseable_date",
                           f"Could not parse last_advisor_contact: '{raw_date}'"))

        # Enrollment status — default to active if credits in progress
        enrollment_status = str(row.get("enrollment_status", "")).strip().lower()
        if enrollment_status in ["", "nan"]:
            enrollment_status = "active" if credits_in_progress > 0 else "unknown"

        # Transfer credits
        transfer_credits = pd.to_numeric(
            row.get("transfer_credits", ""), errors="coerce"
        )
        transfer_credits = int(transfer_credits) if not pd.isna(transfer_credits) else 0

        # Stop out history
        stop_out_history = str(row.get("stop_out_history", "")).strip()
        if stop_out_history.lower() in ["nan", ""]:
            stop_out_history = ""

        # ── Build Student Record ──────────────────────────────────────────────
        student = {
            "student_id":           student_id,
            "first_name":           str(row.get("first_name", "")).strip(),
            "last_name":            str(row.get("last_name", "")).strip(),
            "program_type":         program_type,
            "program_name":         str(row.get("program_name", "")).strip(),
            "credits_completed":    credits_completed,
            "credits_in_progress":  int(credits_in_progress),
            "next_term_registered": next_term_registered,
            "last_advisor_contact": last_advisor_contact,
            "enrollment_status":    enrollment_status,
            "registration_hold":    registration_hold,
            "stop_out_history":     stop_out_history,
            "transfer_credits":     transfer_credits,
        }

        insert_student(student)

        # Log any data quality issues
        for issue_type, description in issues:
            insert_data_issue(student_id, issue_type, description)
            summary["data_issues"] += 1

        summary["records_loaded"] += 1

    print(f"Ingestion complete: {summary}")
    return summary


if __name__ == "__main__":
    ingest_csv()