# waypoint/llm.py
# LLM reasoning layer — sends ambiguous cases to Claude for evaluation
# Called by the agent after the deterministic rule engine

import anthropic
from config import (
    ANTHROPIC_API_KEY,
    LLM_REASONING_MODEL,
    LLM_GENERATION_MODEL,
    MAX_OUTPUT_TOKENS,
    REGISTRATION_DEADLINE,
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def build_reasoning_prompt(student: dict) -> str:
    """
    Build the prompt sent to Claude for ambiguous case evaluation.
    Structured to elicit a consistent, parseable response.
    """
    return f"""You are an academic advising assistant helping evaluate whether a student 
should receive an outreach nudge from their advisor.

STUDENT RECORD:
- Name: {student['first_name']} {student['last_name']}
- Program: {student['program_type'].title()} in {student['program_name']}
- Credits completed: {student['credits_completed']}
- Credits in progress this term: {student['credits_in_progress']}
- Transfer credits (unevaluated): {student['transfer_credits'] or 0}
- Registered for next term: {'Yes' if student['next_term_registered'] else 'No'}
- Registration hold on file: {'Yes' if student['registration_hold'] == 1 else 'Unknown' if student['registration_hold'] is None else 'No'}
- Stop-out history: {student['stop_out_history'] or 'None'}
- Enrollment status: {student['enrollment_status']}
- Next registration deadline: {REGISTRATION_DEADLINE}

FLAGGED FOR REVIEW: {student.get('flag_type', 'unknown').replace('_', ' ').title()}

CREDENTIAL THRESHOLDS:
- Certificate: 30 credits
- Associate's: 60 credits  
- Bachelor's: 120 credits

NOTE: Credits remaining is calculated from the threshold minus credits completed 
minus credits in progress. In a real deployment this would come directly from the 
SIS degree audit export.

Your task: Decide whether this student should receive an advisor nudge email.

Respond in exactly this format:
DECISION: [flag / no_flag]
FLAG_TYPE: [momentum_nudge / one_course_away / none]
CONFIDENCE: [high / medium / low]
REASONING: [1-2 sentences explaining your decision]
OUTREACH_NOTE: [1 sentence the advisor should know before reaching out, or 'None']"""


def build_outreach_prompt(student: dict, flag_type: str, reasoning: str) -> str:
    """
    Build the prompt for generating a draft outreach message.
    Uses an asset-based, warm tone per the spec.
    """
    if flag_type == "one_course_away":
        context = f"This student is very close to completing their {student['program_type']} credential."
    else:
        context = f"This student has made strong progress toward their {student['program_type']} credential."

    return f"""You are helping an academic advisor draft a brief, warm outreach email 
to a student who may benefit from advisor support.

STUDENT: {student['first_name']} {student['last_name']}
PROGRAM: {student['program_type'].title()} in {student['program_name']}
CONTEXT: {context}
ADVISOR NOTE: {reasoning}
REGISTRATION DEADLINE: {REGISTRATION_DEADLINE}

Write a 2-3 sentence email from the advisor to the student. The tone should be:
- Warm and encouraging, not alarming
- Asset-based — acknowledge what the student HAS accomplished
- Action-oriented — include a clear next step
- Brief — advisors are busy, students are busy

Do not include a subject line. Do not use placeholders like [Name]. 
Start directly with the greeting using the student's first name."""


def parse_llm_response(response_text: str) -> dict:
    """
    Parse the structured LLM reasoning response into a dict.
    Handles minor formatting variations gracefully.
    """
    result = {
        "decision": "no_flag",
        "flag_type": "none",
        "confidence": "low",
        "reasoning": "",
        "outreach_note": None,
    }

    for line in response_text.strip().splitlines():
        line = line.strip()
        if line.startswith("DECISION:"):
            val = line.split(":", 1)[1].strip().lower()
            result["decision"] = "flag" if "flag" in val and "no_flag" not in val else "no_flag"
        elif line.startswith("FLAG_TYPE:"):
            val = line.split(":", 1)[1].strip().lower()
            if "one_course" in val or "course_away" in val:
                result["flag_type"] = "one_course_away"
            elif "momentum" in val:
                result["flag_type"] = "momentum_nudge"
            else:
                result["flag_type"] = "none"
        elif line.startswith("CONFIDENCE:"):
            val = line.split(":", 1)[1].strip().lower()
            result["confidence"] = val if val in ["high", "medium", "low"] else "low"
        elif line.startswith("REASONING:"):
            result["reasoning"] = line.split(":", 1)[1].strip()
        elif line.startswith("OUTREACH_NOTE:"):
            val = line.split(":", 1)[1].strip()
            result["outreach_note"] = None if val.lower() == "none" else val

    return result


def evaluate_ambiguous_case(student: dict) -> dict:
    """
    Send an ambiguous student case to Claude for reasoning.
    Returns a flag dict ready to insert into the flags table.
    """
    prompt = build_reasoning_prompt(student)

    try:
        response = client.messages.create(
            model=LLM_REASONING_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text
        parsed = parse_llm_response(response_text)

    except Exception as e:
        print(f"LLM error for {student['student_id']}: {e}")
        parsed = {
            "decision": "no_flag",
            "flag_type": "none",
            "confidence": "low",
            "reasoning": f"LLM evaluation failed: {str(e)}",
            "outreach_note": "Manual review required — LLM evaluation unavailable",
        }

    return {
        "student_id": student["student_id"],
        "flag_type": parsed["flag_type"] if parsed["decision"] == "flag" else "none",
        "flag_source": "llm",
        "reasoning": parsed["reasoning"],
        "outreach_note": parsed["outreach_note"],
        "confidence": parsed["confidence"],
    }


def generate_outreach_message(student: dict, flag_type: str, reasoning: str) -> str:
    """
    Generate a draft outreach email for a confirmed flag.
    Called from the Streamlit UI when an advisor confirms a flag.
    """
    prompt = build_outreach_prompt(student, flag_type, reasoning)

    try:
        response = client.messages.create(
            model=LLM_GENERATION_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    except Exception as e:
        return f"Could not generate outreach message: {str(e)}"


def evaluate_batch(ambiguous_cases: list[dict]) -> list[dict]:
    """
    Evaluate a list of ambiguous student cases.
    Returns only the cases Claude decided should be flagged.
    """
    results = []
    for student in ambiguous_cases:
        print(f"  Evaluating: {student['first_name']} {student['last_name']}...")
        result = evaluate_ambiguous_case(student)
        if result["flag_type"] != "none":
            results.append(result)
    return results