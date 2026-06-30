import pytest

from waypoint.rules import (
    credits_remaining,
    check_momentum_nudge,
    check_one_course_away,
    run_rule_engine,
)


def make_student(**overrides):
    student = {
        "student_id": "S1",
        "first_name": "Jordan",
        "last_name": "Lee",
        "program_type": "associates",
        "program_name": "Liberal Arts",
        "credits_completed": 15.0,
        "credits_in_progress": 0,
        "next_term_registered": 0,
        "last_advisor_contact": None,
        "enrollment_status": "active",
        "registration_hold": 0,
        "stop_out_history": "",
        "transfer_credits": 0,
    }
    student.update(overrides)
    return student


# ── credits_remaining ────────────────────────────────────────────────────────

def test_credits_remaining_none_when_credits_missing():
    student = make_student(credits_completed=None)
    assert credits_remaining(student) is None


def test_credits_remaining_computes_against_threshold():
    student = make_student(
        program_type="associates", credits_completed=50, credits_in_progress=5
    )
    # threshold 60 - 50 - 5 = 5
    assert credits_remaining(student) == 5


# ── check_momentum_nudge ─────────────────────────────────────────────────────

def test_momentum_no_flag_when_credits_missing():
    student = make_student(credits_completed=None)
    assert check_momentum_nudge(student) == "no_flag"


def test_momentum_no_flag_when_not_active():
    student = make_student(enrollment_status="inactive")
    assert check_momentum_nudge(student) == "no_flag"


def test_momentum_no_flag_when_already_registered():
    student = make_student(next_term_registered=1)
    assert check_momentum_nudge(student) == "no_flag"


def test_momentum_no_flag_when_confirmed_hold():
    student = make_student(registration_hold=1)
    assert check_momentum_nudge(student) == "no_flag"


def test_momentum_ambiguous_when_hold_unknown_and_over_threshold():
    student = make_student(registration_hold=None, credits_completed=12)
    assert check_momentum_nudge(student) == "ambiguous"


def test_momentum_ambiguous_when_stop_out_history_and_over_threshold():
    student = make_student(stop_out_history="Spring 2023", credits_completed=20)
    assert check_momentum_nudge(student) == "ambiguous"


def test_momentum_ambiguous_when_in_progress_credits_close_the_gap():
    student = make_student(credits_completed=10, credits_in_progress=3)
    assert check_momentum_nudge(student) == "ambiguous"


def test_momentum_no_flag_when_below_threshold_and_gap_not_closed():
    student = make_student(credits_completed=5, credits_in_progress=2)
    assert check_momentum_nudge(student) == "no_flag"


def test_momentum_clean_flag():
    student = make_student(credits_completed=15, credits_in_progress=0)
    assert check_momentum_nudge(student) == "flag"


# ── check_one_course_away ────────────────────────────────────────────────────

def test_one_course_away_no_flag_when_credits_missing():
    student = make_student(credits_completed=None)
    assert check_one_course_away(student) == "no_flag"


def test_one_course_away_no_flag_when_not_active():
    student = make_student(enrollment_status="inactive")
    assert check_one_course_away(student) == "no_flag"


def test_one_course_away_no_flag_when_already_registered():
    student = make_student(next_term_registered=1)
    assert check_one_course_away(student) == "no_flag"


def test_one_course_away_no_flag_when_confirmed_hold():
    student = make_student(registration_hold=1)
    assert check_one_course_away(student) == "no_flag"


def test_one_course_away_ambiguous_when_already_eligible():
    # associates threshold 60, completed 60 + in_progress 0 -> remaining 0
    student = make_student(credits_completed=60, credits_in_progress=0)
    assert check_one_course_away(student) == "ambiguous"


def test_one_course_away_ambiguous_when_transfer_credits_could_close_gap():
    # remaining = 60 - 50 - 0 = 10; transfer=8 -> remaining <= transfer + 3 (11)
    student = make_student(credits_completed=50, credits_in_progress=0, transfer_credits=8)
    assert check_one_course_away(student) == "ambiguous"


def test_one_course_away_dataset_dual_milestone_student_routes_via_transfer_check():
    # Mirrors PROFILE J from data/generate_synthetic.py: an associate's student
    # close to graduation whose transfer_credits also happen to put them close
    # to a certificate threshold. There is no dedicated dual-milestone rule —
    # this case is correctly caught by the transfer-pending check instead,
    # since remaining <= transfer + ONE_COURSE_AWAY_CREDITS holds whenever
    # remaining is small and transfer is non-negative.
    student = make_student(
        program_type="associates",
        credits_completed=57,
        credits_in_progress=0,
        transfer_credits=27,
    )
    assert check_one_course_away(student) == "ambiguous"


def test_one_course_away_clean_flag():
    # associates threshold 60, completed 58 -> remaining 2
    student = make_student(credits_completed=58, credits_in_progress=0)
    assert check_one_course_away(student) == "flag"


def test_one_course_away_no_flag_when_remaining_well_above_threshold():
    student = make_student(credits_completed=20, credits_in_progress=0)
    assert check_one_course_away(student) == "no_flag"


# ── run_rule_engine ──────────────────────────────────────────────────────────

def test_run_rule_engine_buckets_students_correctly():
    clean_flag_student = make_student(
        student_id="S1", credits_completed=15, credits_in_progress=0
    )
    ambiguous_student = make_student(
        student_id="S2", credits_completed=12, registration_hold=None
    )
    no_flag_student = make_student(
        student_id="S3", credits_completed=2, credits_in_progress=0
    )

    results = run_rule_engine([clean_flag_student, ambiguous_student, no_flag_student])

    assert [f["student_id"] for f in results["clear_flags"]] == ["S1"]
    assert [f["student_id"] for f in results["ambiguous"]] == ["S2"]
    assert [s["student_id"] for s in results["no_flag"]] == ["S3"]

    assert results["clear_flags"][0]["flag_type"] == "momentum_nudge"
    assert results["clear_flags"][0]["flag_source"] == "deterministic"
    assert results["ambiguous"][0]["flag_source"] == "llm"


def test_run_rule_engine_ambiguous_takes_priority_over_clean_flag():
    # one_course_away ambiguous (already eligible) should win over a clean
    # momentum flag the same student would also qualify for.
    student = make_student(
        student_id="S4",
        credits_completed=60,
        credits_in_progress=0,
    )
    results = run_rule_engine([student])
    assert results["clear_flags"] == []
    assert len(results["ambiguous"]) == 1
    assert results["ambiguous"][0]["flag_type"] == "one_course_away"
