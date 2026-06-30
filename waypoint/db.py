# waypoint/db.py
import sqlite3
from config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            program_type TEXT,
            program_name TEXT,
            credits_completed REAL,
            credits_in_progress INTEGER,
            next_term_registered INTEGER,
            last_advisor_contact TEXT,
            enrollment_status TEXT,
            registration_hold INTEGER,
            stop_out_history TEXT,
            transfer_credits INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            issue_type TEXT,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            flag_type TEXT,
            flag_source TEXT,
            reasoning TEXT,
            outreach_note TEXT,
            confidence TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized.")


def clear_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students")
    cursor.execute("DELETE FROM data_issues")
    cursor.execute("DELETE FROM flags")
    conn.commit()
    conn.close()


def insert_student(student: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO students (
            student_id, first_name, last_name, program_type, program_name,
            credits_completed, credits_in_progress, next_term_registered,
            last_advisor_contact, enrollment_status, registration_hold,
            stop_out_history, transfer_credits
        ) VALUES (
            :student_id, :first_name, :last_name, :program_type, :program_name,
            :credits_completed, :credits_in_progress, :next_term_registered,
            :last_advisor_contact, :enrollment_status, :registration_hold,
            :stop_out_history, :transfer_credits
        )
    """, student)
    conn.commit()
    conn.close()


def insert_data_issue(student_id: str, issue_type: str, description: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO data_issues (student_id, issue_type, description) VALUES (?, ?, ?)",
        (student_id, issue_type, description)
    )
    conn.commit()
    conn.close()


def insert_flag(flag: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO flags (student_id, flag_type, flag_source, reasoning, outreach_note, confidence)
        VALUES (:student_id, :flag_type, :flag_source, :reasoning, :outreach_note, :confidence)
    """, flag)
    conn.commit()
    conn.close()


def get_all_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_all_flags():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.*, s.first_name, s.last_name, s.program_type, s.program_name,
               s.credits_completed, s.credits_in_progress, s.transfer_credits,
               s.stop_out_history, s.registration_hold
        FROM flags f
        JOIN students s ON f.student_id = s.student_id
        ORDER BY f.created_at DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows