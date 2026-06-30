import pytest

from waypoint import agent


def patch_pipeline(monkeypatch, *, ingest_raises=False, rules_raises=False, llm_raises=False, llm_skipped=0):
    if ingest_raises:
        monkeypatch.setattr(
            agent, "ingest_csv",
            lambda csv_path: (_ for _ in ()).throw(RuntimeError("bad csv"))
        )
    else:
        monkeypatch.setattr(agent, "ingest_csv", lambda csv_path: {"records_loaded": 2})

    monkeypatch.setattr(agent, "get_all_students", lambda: [{"student_id": "S1"}, {"student_id": "S2"}])

    if rules_raises:
        monkeypatch.setattr(
            agent, "run_rule_engine",
            lambda students: (_ for _ in ()).throw(RuntimeError("bad rules"))
        )
    else:
        monkeypatch.setattr(agent, "run_rule_engine", lambda students: {
            "clear_flags": [{
                "student_id": "S1", "flag_type": "momentum_nudge",
                "flag_source": "deterministic", "reasoning": "r",
                "outreach_note": None, "confidence": "high",
            }],
            "ambiguous": [{"student_id": "S2"}],
            "no_flag": [],
        })

    if llm_raises:
        monkeypatch.setattr(
            agent, "evaluate_batch",
            lambda ambiguous: (_ for _ in ()).throw(RuntimeError("llm down"))
        )
    else:
        monkeypatch.setattr(agent, "evaluate_batch", lambda ambiguous: {
            "flags": [{
                "student_id": "S2", "flag_type": "one_course_away",
                "flag_source": "llm", "reasoning": "r",
                "outreach_note": None, "confidence": "medium",
            }],
            "skipped": llm_skipped,
        })

    inserted = []
    monkeypatch.setattr(agent, "insert_flag", lambda flag: inserted.append(flag))
    monkeypatch.setattr(agent, "get_all_flags", lambda: inserted)
    return inserted


def test_run_waypoint_happy_path(monkeypatch):
    inserted = patch_pipeline(monkeypatch)

    final_state = agent.run_waypoint("fake.csv")

    assert final_state["status"] == "complete"
    assert final_state["errors"] == []
    assert len(final_state["clear_flags"]) == 1
    assert len(final_state["llm_flags"]) == 1
    assert final_state["llm_skipped"] == 0
    # both the deterministic and the LLM flag should have been saved
    assert len(inserted) == 2


def test_run_waypoint_surfaces_llm_skipped_count(monkeypatch):
    patch_pipeline(monkeypatch, llm_skipped=3)

    final_state = agent.run_waypoint("fake.csv")

    assert final_state["status"] == "complete"
    assert final_state["llm_skipped"] == 3


def test_run_waypoint_stops_on_ingest_failure(monkeypatch):
    inserted = patch_pipeline(monkeypatch, ingest_raises=True)

    final_state = agent.run_waypoint("fake.csv")

    assert final_state["status"] == "error"
    assert any("Ingest failed" in e for e in final_state["errors"])
    # downstream nodes never ran
    assert final_state["clear_flags"] == []
    assert inserted == []


def test_run_waypoint_stops_on_rule_engine_failure(monkeypatch):
    inserted = patch_pipeline(monkeypatch, rules_raises=True)

    final_state = agent.run_waypoint("fake.csv")

    assert final_state["status"] == "error"
    assert any("Rule engine failed" in e for e in final_state["errors"])
    assert final_state["llm_flags"] == []
    assert inserted == []


def test_run_waypoint_llm_failure_is_non_fatal(monkeypatch):
    inserted = patch_pipeline(monkeypatch, llm_raises=True)

    final_state = agent.run_waypoint("fake.csv")

    # LLM errors don't stop the pipeline — deterministic flags still save
    assert final_state["status"] == "complete"
    assert any("LLM evaluation failed" in e for e in final_state["errors"])
    assert final_state["llm_flags"] == []
    assert final_state["llm_skipped"] == 0
    # only the deterministic flag was saved
    assert len(inserted) == 1
    assert inserted[0]["student_id"] == "S1"
