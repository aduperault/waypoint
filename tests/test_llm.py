import pytest

from waypoint import llm


def make_student(**overrides):
    student = {
        "student_id": "S1",
        "first_name": "Jordan",
        "last_name": "Lee",
        "program_type": "associates",
        "program_name": "Liberal Arts",
        "credits_completed": 50,
        "credits_in_progress": 5,
        "next_term_registered": 0,
        "registration_hold": None,
        "stop_out_history": "",
        "transfer_credits": 0,
        "enrollment_status": "active",
        "flag_type": "momentum_nudge",
    }
    student.update(overrides)
    return student


class FakeContentBlock:
    def __init__(self, text):
        self.text = text


class FakeUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeResponse:
    def __init__(self, text, usage=None):
        self.content = [FakeContentBlock(text)]
        self.usage = usage


# ── parse_llm_response ────────────────────────────────────────────────────────

def test_parse_llm_response_well_formed_flag():
    text = (
        "DECISION: flag\n"
        "FLAG_TYPE: one_course_away\n"
        "CONFIDENCE: high\n"
        "REASONING: Student is close to completion.\n"
        "OUTREACH_NOTE: Mention summer term option.\n"
    )
    result = llm.parse_llm_response(text)
    assert result["decision"] == "flag"
    assert result["flag_type"] == "one_course_away"
    assert result["confidence"] == "high"
    assert result["reasoning"] == "Student is close to completion."
    assert result["outreach_note"] == "Mention summer term option."


def test_parse_llm_response_no_flag_decision():
    text = "DECISION: no_flag\nFLAG_TYPE: none\nCONFIDENCE: low\nREASONING: Not enough signal.\nOUTREACH_NOTE: None"
    result = llm.parse_llm_response(text)
    assert result["decision"] == "no_flag"
    assert result["outreach_note"] is None


def test_parse_llm_response_unrecognized_flag_type_falls_back_to_none():
    text = "DECISION: flag\nFLAG_TYPE: something_else\nCONFIDENCE: high\nREASONING: x\nOUTREACH_NOTE: None"
    result = llm.parse_llm_response(text)
    assert result["flag_type"] == "none"


def test_parse_llm_response_invalid_confidence_falls_back_to_low():
    text = "DECISION: flag\nFLAG_TYPE: momentum_nudge\nCONFIDENCE: extremely-sure\nREASONING: x\nOUTREACH_NOTE: None"
    result = llm.parse_llm_response(text)
    assert result["confidence"] == "low"


def test_parse_llm_response_missing_lines_keep_defaults():
    result = llm.parse_llm_response("DECISION: flag\nFLAG_TYPE: momentum_nudge")
    assert result["confidence"] == "low"
    assert result["reasoning"] == ""
    assert result["outreach_note"] is None


# ── prompt builders ───────────────────────────────────────────────────────────

def test_build_reasoning_prompt_includes_key_fields():
    student = make_student()
    prompt = llm.build_reasoning_prompt(student)
    assert "Jordan Lee" in prompt
    assert "Liberal Arts" in prompt
    assert "50" in prompt
    assert "Momentum Nudge" in prompt


def test_build_outreach_prompt_includes_key_fields():
    student = make_student()
    prompt = llm.build_outreach_prompt(student, "one_course_away", "Almost done with credential.")
    assert "Jordan" in prompt
    assert "Almost done with credential." in prompt
    assert "close to completing" in prompt


def test_build_reasoning_prompt_isolates_untrusted_data():
    # Student fields come from an uploaded CSV — make sure they're wrapped
    # in a clearly-delimited data block with an explicit anti-injection
    # instruction, not interpolated as free-floating prompt text.
    student = make_student()
    prompt = llm.build_reasoning_prompt(student)
    assert "<student_record>" in prompt
    assert "</student_record>" in prompt
    assert "untrusted data" in prompt
    assert "ignore it" in prompt
    # the data block must actually contain the student's record
    record_start = prompt.index("<student_record>")
    record_end = prompt.index("</student_record>")
    assert "Jordan Lee" in prompt[record_start:record_end]


def test_build_outreach_prompt_isolates_untrusted_data():
    student = make_student()
    prompt = llm.build_outreach_prompt(student, "momentum_nudge", "Doing well.")
    assert "<context>" in prompt
    assert "</context>" in prompt
    assert "untrusted data" in prompt
    assert "ignore it" in prompt


# ── evaluate_ambiguous_case (mocked Claude calls) ────────────────────────────

def test_evaluate_ambiguous_case_success(monkeypatch):
    response_text = (
        "DECISION: flag\n"
        "FLAG_TYPE: momentum_nudge\n"
        "CONFIDENCE: medium\n"
        "REASONING: Strong progress, unclear hold status.\n"
        "OUTREACH_NOTE: Verify hold before contacting.\n"
    )
    monkeypatch.setattr(
        llm.client.messages, "create", lambda **kwargs: FakeResponse(response_text)
    )

    student = make_student()
    result = llm.evaluate_ambiguous_case(student)

    assert result["student_id"] == "S1"
    assert result["flag_type"] == "momentum_nudge"
    assert result["flag_source"] == "llm"
    assert result["confidence"] == "medium"
    assert result["reasoning"] == "Strong progress, unclear hold status."


def test_evaluate_ambiguous_case_no_flag_decision_returns_none_flag_type(monkeypatch):
    response_text = "DECISION: no_flag\nFLAG_TYPE: none\nCONFIDENCE: low\nREASONING: x\nOUTREACH_NOTE: None"
    monkeypatch.setattr(
        llm.client.messages, "create", lambda **kwargs: FakeResponse(response_text)
    )

    student = make_student()
    result = llm.evaluate_ambiguous_case(student)
    assert result["flag_type"] == "none"


def test_evaluate_ambiguous_case_handles_api_error_gracefully(monkeypatch):
    # A failed API call must NOT silently drop the student — it should be
    # routed back for manual review, not discarded, since this is a real
    # operating condition for low-connectivity institutions.
    def raise_error(**kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(llm.client.messages, "create", raise_error)

    student = make_student(flag_type="momentum_nudge")
    result = llm.evaluate_ambiguous_case(student)

    assert result["flag_type"] == "momentum_nudge"  # preserved from the original ambiguous flag
    assert result["flag_source"] == "llm_error"
    assert result["confidence"] == "low"
    assert "Manual review required" in result["outreach_note"]
    assert "LLM evaluation failed" in result["reasoning"]


def test_evaluate_ambiguous_case_api_error_defaults_flag_type_if_missing(monkeypatch):
    def raise_error(**kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(llm.client.messages, "create", raise_error)

    student = make_student()
    del student["flag_type"]
    result = llm.evaluate_ambiguous_case(student)

    assert result["flag_type"] == "needs_review"
    assert result["flag_source"] == "llm_error"


# ── generate_outreach_message (mocked Claude calls) ──────────────────────────

def test_generate_outreach_message_success(monkeypatch):
    monkeypatch.setattr(
        llm.client.messages, "create",
        lambda **kwargs: FakeResponse("Hi Jordan, great progress this term!")
    )
    student = make_student()
    message = llm.generate_outreach_message(student, "momentum_nudge", "Doing well.")
    assert message == "Hi Jordan, great progress this term!"


def test_generate_outreach_message_handles_api_error_gracefully(monkeypatch):
    def raise_error(**kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(llm.client.messages, "create", raise_error)
    student = make_student()
    message = llm.generate_outreach_message(student, "momentum_nudge", "Doing well.")
    assert "Could not generate outreach message" in message


# ── evaluate_batch ─────────────────────────────────────────────────────────────

def test_evaluate_batch_keeps_only_flagged_cases(monkeypatch):
    students = [make_student(student_id="S1"), make_student(student_id="S2")]

    def fake_evaluate(student, budget=None):
        if student["student_id"] == "S1":
            return {
                "student_id": "S1", "flag_type": "momentum_nudge",
                "flag_source": "llm", "reasoning": "r", "outreach_note": None,
                "confidence": "high",
            }
        return {
            "student_id": "S2", "flag_type": "none",
            "flag_source": "llm", "reasoning": "r", "outreach_note": None,
            "confidence": "low",
        }

    monkeypatch.setattr(llm, "evaluate_ambiguous_case", fake_evaluate)

    result = llm.evaluate_batch(students)
    assert len(result["flags"]) == 1
    assert result["flags"][0]["student_id"] == "S1"
    assert result["skipped"] == 0


# ── TokenBudget ──────────────────────────────────────────────────────────────

def test_token_budget_not_exhausted_below_cap():
    budget = llm.TokenBudget(1000)
    budget.add(400)
    assert budget.exhausted is False


def test_token_budget_exhausted_at_or_above_cap():
    budget = llm.TokenBudget(1000)
    budget.add(1000)
    assert budget.exhausted is True


# ── evaluate_ambiguous_case token tracking ───────────────────────────────────

def test_evaluate_ambiguous_case_adds_usage_to_budget(monkeypatch):
    response_text = "DECISION: flag\nFLAG_TYPE: momentum_nudge\nCONFIDENCE: high\nREASONING: r\nOUTREACH_NOTE: None"
    monkeypatch.setattr(
        llm.client.messages, "create",
        lambda **kwargs: FakeResponse(response_text, usage=FakeUsage(300, 50))
    )

    budget = llm.TokenBudget(10_000)
    llm.evaluate_ambiguous_case(make_student(), budget=budget)

    assert budget.used == 350


def test_evaluate_ambiguous_case_without_budget_does_not_error(monkeypatch):
    response_text = "DECISION: flag\nFLAG_TYPE: momentum_nudge\nCONFIDENCE: high\nREASONING: r\nOUTREACH_NOTE: None"
    monkeypatch.setattr(
        llm.client.messages, "create",
        lambda **kwargs: FakeResponse(response_text, usage=FakeUsage(300, 50))
    )

    result = llm.evaluate_ambiguous_case(make_student())
    assert result["flag_type"] == "momentum_nudge"


# ── evaluate_batch token budget enforcement ──────────────────────────────────

def test_evaluate_batch_stops_when_token_budget_exhausted(monkeypatch):
    response_text = "DECISION: flag\nFLAG_TYPE: momentum_nudge\nCONFIDENCE: high\nREASONING: r\nOUTREACH_NOTE: None"
    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        return FakeResponse(response_text, usage=FakeUsage(4000, 1000))

    monkeypatch.setattr(llm.client.messages, "create", fake_create)
    monkeypatch.setattr(llm, "MAX_TOKENS_PER_RUN", 5000)

    students = [make_student(student_id=f"S{i}") for i in range(5)]
    result = llm.evaluate_batch(students)

    # Budget is 5000, each call costs 5000 tokens -> only the first call
    # should run before the batch stops.
    assert call_count["n"] == 1
    assert len(result["flags"]) == 1
    assert result["skipped"] == 4


def test_evaluate_batch_processes_all_when_budget_is_generous(monkeypatch):
    response_text = "DECISION: flag\nFLAG_TYPE: momentum_nudge\nCONFIDENCE: high\nREASONING: r\nOUTREACH_NOTE: None"
    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        return FakeResponse(response_text, usage=FakeUsage(10, 5))

    monkeypatch.setattr(llm.client.messages, "create", fake_create)
    monkeypatch.setattr(llm, "MAX_TOKENS_PER_RUN", 50_000)

    students = [make_student(student_id=f"S{i}") for i in range(5)]
    result = llm.evaluate_batch(students)

    assert call_count["n"] == 5
    assert len(result["flags"]) == 5
    assert result["skipped"] == 0
