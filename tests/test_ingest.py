import sqlite3
import pandas as pd
import pytest

import config
from waypoint import db
from waypoint.ingest import (
    normalize_columns,
    normalize_program_type,
    normalize_boolean,
    normalize_date,
    ingest_csv,
)


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point DB_PATH at a throwaway sqlite file for every test in this module."""
    db_file = tmp_path / "test_waypoint.db"
    monkeypatch.setattr(config, "DB_PATH", str(db_file))
    monkeypatch.setattr(db, "DB_PATH", str(db_file))
    yield db_file


# ── normalize_columns ─────────────────────────────────────────────────────────

def test_normalize_columns_maps_aliases():
    df = pd.DataFrame(columns=["stu_id", " Status ", "FIRST"])
    df = normalize_columns(df)
    assert "student_id" in df.columns
    assert "enrollment_status" in df.columns
    assert "first_name" in df.columns


def test_normalize_columns_leaves_unmapped_columns_alone():
    df = pd.DataFrame(columns=["some_unknown_field"])
    df = normalize_columns(df)
    assert "some_unknown_field" in df.columns


# ── normalize_program_type ────────────────────────────────────────────────────

def test_normalize_program_type_known_variant():
    assert normalize_program_type("CERT-ECE") == "certificate"
    assert normalize_program_type("as-bus") == "associates"


def test_normalize_program_type_blank_defaults_to_associates():
    assert normalize_program_type("") == "associates"
    assert normalize_program_type(None) == "associates"


def test_normalize_program_type_unrecognized_returns_none():
    assert normalize_program_type("doctorate") is None


# ── normalize_boolean ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("Y", 1), ("n", 0), ("True", 1), ("false", 0), ("1", 1), ("0", 0),
])
def test_normalize_boolean_known_values(raw, expected):
    assert normalize_boolean(raw) == expected


def test_normalize_boolean_unparseable_returns_none():
    assert normalize_boolean("maybe") is None


def test_normalize_boolean_nan_returns_none():
    assert normalize_boolean(float("nan")) is None


# ── normalize_date ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw", [
    "2024-03-01", "03/01/2024", "03/01/24", "01-Mar-2024", "March 01, 2024", "20240301",
])
def test_normalize_date_supported_formats(raw):
    assert normalize_date(raw) == "2024-03-01"


def test_normalize_date_unparseable_returns_none():
    assert normalize_date("not a date") is None


def test_normalize_date_blank_returns_none():
    assert normalize_date("") is None
    assert normalize_date(float("nan")) is None


# ── ingest_csv (integration, real temp sqlite + temp csv) ────────────────────

def write_csv(tmp_path, rows, columns):
    path = tmp_path / "students.csv"
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    return str(path)


COLUMNS = [
    "student_id", "first_name", "last_name", "program_type", "program_name",
    "credits_completed", "credits_in_progress", "next_term_registered",
    "last_advisor_contact", "enrollment_status", "registration_hold",
    "stop_out_history", "transfer_credits",
]


def test_ingest_csv_loads_clean_rows(tmp_path):
    rows = [
        ["S1", "Ana", "Cruz", "associates", "Liberal Arts", "15", "0", "Y",
         "2024-01-01", "active", "N", "", "0"],
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    summary = ingest_csv(csv_path)

    assert summary["total_rows"] == 1
    assert summary["records_loaded"] == 1
    assert summary["records_skipped"] == 0
    assert summary["data_issues"] == 0

    students = db.get_all_students()
    assert len(students) == 1
    assert students[0]["student_id"] == "S1"
    assert students[0]["credits_completed"] == 15.0


def test_ingest_csv_skips_blank_student_id(tmp_path):
    rows = [
        ["", "Ana", "Cruz", "associates", "Liberal Arts", "15", "0", "Y",
         "2024-01-01", "active", "N", "", "0"],
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    summary = ingest_csv(csv_path)

    assert summary["records_skipped"] == 1
    assert summary["records_loaded"] == 0


def test_ingest_csv_deduplicates_keeping_highest_credits(tmp_path):
    rows = [
        ["S1", "Ana", "Cruz", "associates", "Liberal Arts", "10", "0", "Y",
         "2024-01-01", "active", "N", "", "0"],
        ["S1", "Ana", "Cruz", "associates", "Liberal Arts", "40", "0", "Y",
         "2024-01-01", "active", "N", "", "0"],
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    summary = ingest_csv(csv_path)

    assert summary["duplicates_removed"] == 1
    students = db.get_all_students()
    assert len(students) == 1
    assert students[0]["credits_completed"] == 40.0


def test_ingest_csv_flags_missing_credits_completed(tmp_path):
    rows = [
        ["S1", "Ana", "Cruz", "associates", "Liberal Arts", "", "0", "Y",
         "2024-01-01", "active", "N", "", "0"],
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    summary = ingest_csv(csv_path)

    assert summary["data_issues"] == 1
    students = db.get_all_students()
    assert students[0]["credits_completed"] is None

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    issues = conn.execute("SELECT * FROM data_issues").fetchall()
    conn.close()
    assert len(issues) == 1
    assert issues[0]["issue_type"] == "missing_credits_completed"


def test_ingest_csv_flags_unrecognized_program_type(tmp_path):
    rows = [
        ["S1", "Ana", "Cruz", "doctorate", "Liberal Arts", "15", "0", "Y",
         "2024-01-01", "active", "N", "", "0"],
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    ingest_csv(csv_path)

    students = db.get_all_students()
    assert students[0]["program_type"] == "associates"  # defaulted

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    issues = conn.execute("SELECT * FROM data_issues").fetchall()
    conn.close()
    assert any(i["issue_type"] == "unrecognized_program_type" for i in issues)


def test_ingest_csv_flags_unparseable_date(tmp_path):
    rows = [
        ["S1", "Ana", "Cruz", "associates", "Liberal Arts", "15", "0", "Y",
         "not-a-date", "active", "N", "", "0"],
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    ingest_csv(csv_path)

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    issues = conn.execute("SELECT * FROM data_issues").fetchall()
    conn.close()
    assert any(i["issue_type"] == "unparseable_date" for i in issues)


def test_ingest_csv_raises_on_missing_file(tmp_path):
    missing_path = str(tmp_path / "does_not_exist.csv")
    with pytest.raises(FileNotFoundError):
        ingest_csv(missing_path)


def test_ingest_csv_raises_clear_error_when_no_student_id_column_recognized(tmp_path):
    # A CSV whose ID column uses an alias Waypoint doesn't recognize should
    # fail loudly, not silently load zero students.
    path = tmp_path / "students.csv"
    pd.DataFrame(
        [["A1", "Ana", "Cruz"]],
        columns=["unrecognized_id_field", "first_name", "last_name"],
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="No student ID column recognized"):
        ingest_csv(str(path))


def test_ingest_csv_empty_file_does_not_raise_column_error(tmp_path):
    # An empty CSV (headers only, no rows) shouldn't trigger the missing
    # student_id error — there's nothing to load either way.
    path = tmp_path / "students.csv"
    pd.DataFrame(columns=["unrecognized_id_field"]).to_csv(path, index=False)

    summary = ingest_csv(str(path))
    assert summary["records_loaded"] == 0


def test_ingest_csv_rejects_file_exceeding_size_limit(tmp_path, monkeypatch):
    # ingest.py imports MAX_CSV_FILE_SIZE_MB by name, so patch its own
    # module binding rather than config's.
    import waypoint.ingest as ingest_module
    monkeypatch.setattr(ingest_module, "MAX_CSV_FILE_SIZE_MB", 0.0001)  # ~100 bytes

    rows = [
        ["S1", "Ana", "Cruz", "associates", "Liberal Arts", "15", "0", "Y",
         "2024-01-01", "active", "N", "", "0"],
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    with pytest.raises(ValueError, match="exceeds the"):
        ingest_csv(csv_path)


def test_ingest_csv_rejects_file_exceeding_row_limit(tmp_path, monkeypatch):
    import waypoint.ingest as ingest_module
    monkeypatch.setattr(ingest_module, "MAX_CSV_ROWS", 2)

    rows = [
        [f"S{i}", "Ana", "Cruz", "associates", "Liberal Arts", "15", "0", "Y",
         "2024-01-01", "active", "N", "", "0"]
        for i in range(5)
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    with pytest.raises(ValueError, match="exceeds the"):
        ingest_csv(csv_path)


def test_ingest_csv_within_limits_succeeds(tmp_path, monkeypatch):
    import waypoint.ingest as ingest_module
    monkeypatch.setattr(ingest_module, "MAX_CSV_ROWS", 10)
    monkeypatch.setattr(ingest_module, "MAX_CSV_FILE_SIZE_MB", 10)

    rows = [
        ["S1", "Ana", "Cruz", "associates", "Liberal Arts", "15", "0", "Y",
         "2024-01-01", "active", "N", "", "0"],
    ]
    csv_path = write_csv(tmp_path, rows, COLUMNS)

    summary = ingest_csv(csv_path)
    assert summary["records_loaded"] == 1
