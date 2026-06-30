# waypoint/rules.py
# Deterministic rule engine — applies flag logic to all student records
# Returns three lists: clear_flags, ambiguous, no_flag

from config import (
    CREDENTIAL_THRESHOLDS,
    MOMENTUM_CREDIT_THRESHOLD,
    ONE_COURSE_AWAY_CREDITS,
)


def credits_remaining(student: dict) -> float | None:
    """
    Calculate credits remaining to credential completion.
    Returns None if credits_completed is missing.
    Note: In a real deployment this would come directly from the SIS
    degree audit export as a 'credits_remaining' field rather than
    being calculated here from a hardcoded threshold.
    """
    if student["credits_completed"] is None:
        return None
    threshold = CREDENTIAL_THRESHOLDS.get(student["program_type"], 60)
    remaining = (
        threshold
        - student["credits_completed"]
        - student["credits_in_progress"]
    )
    return remaining


def check_momentum_nudge(student: dict) -> str:
    """
    Evaluate a student for the Credit Momentum Nudge flag.
    Returns: 'flag' | 'ambiguous' | 'no_flag'
    """
    # Cannot evaluate without credits
    if student["credits_completed"] is None:
        return "no_flag"

    # Must be active
    if student["enrollment_status"] != "active":
        return "no_flag"

    # Already registered — no nudge needed
    if student["next_term_registered"] == 1:
        return "no_flag"

    # Confirmed registration hold — can't register anyway
    if student["registration_hold"] == 1:
        return "no_flag"

    credits = student["credits_completed"]
    in_progress = student["credits_in_progress"]

    # Unknown hold status — ambiguous
    if student["registration_hold"] is None:
        if credits >= MOMENTUM_CREDIT_THRESHOLD:
            return "ambiguous"

    # Stop-out history — check for seasonal pattern
    stop_out = student["stop_out_history"] or ""
    if stop_out and credits >= MOMENTUM_CREDIT_THRESHOLD:
        return "ambiguous"

    # Just below threshold but in-progress credits will push past it
    if credits < MOMENTUM_CREDIT_THRESHOLD:
        if credits + in_progress >= MOMENTUM_CREDIT_THRESHOLD:
            return "ambiguous"
        return "no_flag"

    # Clean momentum flag
    if credits >= MOMENTUM_CREDIT_THRESHOLD:
        return "flag"

    return "no_flag"


def check_one_course_away(student: dict) -> str:
    """
    Evaluate a student for the One Course Away flag.
    Returns: 'flag' | 'ambiguous' | 'no_flag'
    """
    # Cannot evaluate without credits
    if student["credits_completed"] is None:
        return "no_flag"

    # Must be active
    if student["enrollment_status"] != "active":
        return "no_flag"

    # Already registered — no nudge needed
    if student["next_term_registered"] == 1:
        return "no_flag"

    # Confirmed registration hold — cannot register
    if student["registration_hold"] == 1:
        return "no_flag"

    remaining = credits_remaining(student)
    if remaining is None:
        return "no_flag"

    # Already eligible (remaining <= 0) — ambiguous special case
    # Student may need to apply for graduation rather than register
    if remaining <= 0:
        return "ambiguous"

    # Has unevaluated transfer credits that could close the gap — route to LLM
    transfer = student["transfer_credits"] or 0
    if transfer > 0 and remaining <= transfer + ONE_COURSE_AWAY_CREDITS:
        return "ambiguous"

    # Clean one course away flag
    if 0 < remaining <= ONE_COURSE_AWAY_CREDITS:
        return "flag"

    return "no_flag"


def run_rule_engine(students: list[dict]) -> dict:
    """
    Run both rules against all student records.
    Returns a dict with three lists: clear_flags, ambiguous, no_flag.
    Priority: ambiguous > flag > no_flag
    If either rule returns ambiguous, the student routes to LLM.
    """
    clear_flags = []
    ambiguous = []
    no_flag = []

    for student in students:
        momentum_result = check_momentum_nudge(student)
        one_course_result = check_one_course_away(student)

        # Ambiguous takes priority — if either rule is uncertain, route to LLM
        if one_course_result == "ambiguous":
            ambiguous.append({
                **student,
                "flag_type": "one_course_away",
                "flag_source": "llm",
                "reasoning": None,
                "outreach_note": None,
                "confidence": None,
            })
        elif momentum_result == "ambiguous":
            ambiguous.append({
                **student,
                "flag_type": "momentum_nudge",
                "flag_source": "llm",
                "reasoning": None,
                "outreach_note": None,
                "confidence": None,
            })
        # Clean flags — one course away takes priority over momentum
        elif one_course_result == "flag":
            remaining = credits_remaining(student)
            clear_flags.append({
                **student,
                "flag_type": "one_course_away",
                "flag_source": "deterministic",
                "reasoning": f"Student has {remaining:.0f} credits remaining to {student['program_type']} completion and is not registered for next term.",
                "outreach_note": None,
                "confidence": "high",
            })
        elif momentum_result == "flag":
            clear_flags.append({
                **student,
                "flag_type": "momentum_nudge",
                "flag_source": "deterministic",
                "reasoning": f"Student has completed {student['credits_completed']:.0f} credits and is not registered for next term.",
                "outreach_note": None,
                "confidence": "high",
            })
        else:
            no_flag.append(student)

    return {
        "clear_flags": clear_flags,
        "ambiguous": ambiguous,
        "no_flag": no_flag,
    }