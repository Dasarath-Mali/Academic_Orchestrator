"""
database_manager.py
────────────────────
Wraps all MySQL CRUD operations via mysql-connector-python.
Every public method is a clean, self-contained transaction.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

import mysql.connector
from mysql.connector import MySQLConnection, Error as MySQLError
from dotenv import load_dotenv
from loguru import logger

load_dotenv()  # works locally (reads config/.env via .env search) and on Render (reads env vars)


class DatabaseManager:
    """Singleton-style MySQL manager for the Academic Orchestrator."""

    def __init__(self) -> None:
        self._config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "database": os.getenv("DB_NAME", "academic_orchestrator"),
            "user": os.getenv("DB_USER", "orchestrator_user"),
            "password": os.getenv("DB_PASSWORD", ""),
            "autocommit": False,
            "charset": "utf8mb4",
        }

    # ── Connection helper ─────────────────────────────────────────────────────

    @contextmanager
    def _connect(self) -> Generator[MySQLConnection, None, None]:
        conn: MySQLConnection | None = None
        try:
            conn = mysql.connector.connect(**self._config)
            yield conn
            conn.commit()
        except MySQLError as exc:
            logger.error(f"DB error: {exc}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    # ── Courses ───────────────────────────────────────────────────────────────

    def upsert_course(
        self,
        name: str,
        code: str = "",
        instructor: str = "",
        semester: str = "",
        syllabus_path: str = "",
    ) -> int:
        """Insert or update a course row. Returns course_id."""
        with self._connect() as conn:
            cur = conn.cursor()
            # Check if exists by code
            if code:
                cur.execute("SELECT id FROM courses WHERE code = %s", (code,))
                row = cur.fetchone()
                if row:
                    course_id = row[0]
                    cur.execute(
                        """UPDATE courses SET name=%s, instructor=%s, semester=%s,
                           syllabus_path=%s WHERE id=%s""",
                        (name, instructor, semester, syllabus_path, course_id),
                    )
                    logger.debug(f"Updated course id={course_id}")
                    return course_id

            cur.execute(
                """INSERT INTO courses (name, code, instructor, semester, syllabus_path)
                   VALUES (%s, %s, %s, %s, %s)""",
                (name, code, instructor, semester, syllabus_path),
            )
            logger.success(f"Inserted new course: {name}")
            return cur.lastrowid  # type: ignore[return-value]

    def get_all_courses(self) -> list[dict]:
        with self._connect() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM courses ORDER BY created_at DESC")
            return cur.fetchall()

    # ── Deadlines ─────────────────────────────────────────────────────────────

    def insert_deadline(
        self,
        course_id: int,
        title: str,
        deadline_date: datetime,
        deadline_type: str = "assignment",
        weight_percent: float | None = None,
        description: str = "",
    ) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO deadlines
                   (course_id, title, deadline_date, deadline_type, weight_percent, description)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (course_id, title, deadline_date, deadline_type, weight_percent, description),
            )
            logger.success(f"Inserted deadline: '{title}' on {deadline_date.date()}")
            return cur.lastrowid  # type: ignore[return-value]

    def get_upcoming_deadlines(self, days_ahead: int = 30) -> list[dict]:
        with self._connect() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """SELECT d.*, c.name AS course_name
                   FROM deadlines d
                   JOIN courses c ON d.course_id = c.id
                   WHERE d.deadline_date BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL %s DAY)
                     AND d.is_completed = FALSE
                   ORDER BY d.deadline_date ASC""",
                (days_ahead,),
            )
            return cur.fetchall()

    def mark_deadline_complete(self, deadline_id: int) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE deadlines SET is_completed = TRUE WHERE id = %s", (deadline_id,)
            )
            logger.info(f"Marked deadline {deadline_id} as complete.")

    def update_cron_job_id(self, deadline_id: int, cron_job_id: str) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE deadlines SET cron_job_id = %s WHERE id = %s",
                (cron_job_id, deadline_id),
            )

    # ── Notification log ──────────────────────────────────────────────────────

    def log_notification(
        self,
        deadline_id: int,
        channel: str,
        message: str,
        status: str = "sent",
    ) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO notification_log (deadline_id, channel, message, status)
                   VALUES (%s, %s, %s, %s)""",
                (deadline_id, channel, message, status),
            )

    # ── Research sessions ─────────────────────────────────────────────────────

    def save_research_session(
        self,
        query: str,
        summary: str,
        sources: list[dict],
        github_repos: list[dict],
        course_id: int | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO research_sessions
                   (query, course_id, summary, sources_json, github_repos)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    query,
                    course_id,
                    summary,
                    json.dumps(sources),
                    json.dumps(github_repos),
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_research_sessions(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT * FROM research_sessions ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
            for row in rows:
                row["sources_json"] = json.loads(row["sources_json"] or "[]")
                row["github_repos"] = json.loads(row["github_repos"] or "[]")
            return rows

    # ── PR Reviews ────────────────────────────────────────────────────────────

    def save_pr_review(
        self,
        pr_number: int,
        pr_title: str,
        author: str,
        review_summary: str,
        issues_found: list[dict],
        complexity_score: float,
    ) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO pr_reviews
                   (pr_number, pr_title, author, review_summary, issues_found, complexity_score)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    pr_number,
                    pr_title,
                    author,
                    review_summary,
                    json.dumps(issues_found),
                    complexity_score,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_pr_reviews(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT * FROM pr_reviews ORDER BY reviewed_at DESC LIMIT %s", (limit,)
            )
            rows = cur.fetchall()
            for row in rows:
                row["issues_found"] = json.loads(row["issues_found"] or "[]")
            return rows

    # ── Scrum ─────────────────────────────────────────────────────────────────

    def save_scrum_update(
        self,
        member_id: int | None,
        issue_number: int,
        status_note: str,
        message_sent: str,
    ) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO scrum_updates
                   (member_id, issue_number, status_note, message_sent)
                   VALUES (%s, %s, %s, %s)""",
                (member_id, issue_number, status_note, message_sent),
            )
