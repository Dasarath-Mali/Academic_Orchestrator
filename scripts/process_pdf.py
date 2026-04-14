"""
process_pdf.py
───────────────
Standalone CLI script invoked by the shell watcher (watch_folder.sh).
Also useful for one-off manual processing of a PDF.

Usage:
  python scripts/process_pdf.py --file data/raw_syllabi/cs101.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

from loguru import logger
from core.pdf_processor import PDFProcessor
from core.database_manager import DatabaseManager
from core.scheduler import Scheduler
import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Process a syllabus PDF")
    parser.add_argument("--file", required=True, help="Path to the PDF file")
    args = parser.parse_args()

    pdf_path = Path(args.file)
    if not pdf_path.exists():
        logger.error(f"File not found: {pdf_path}")
        sys.exit(1)

    # Load settings
    cfg_path = ROOT / "config" / "settings.yaml"
    settings = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}

    db = DatabaseManager()
    scheduler = Scheduler(db_manager=db)
    processor = PDFProcessor()

    parsed = processor.process(pdf_path)

    course_id = db.upsert_course(
        name=parsed.course_name,
        code=parsed.course_code,
        instructor=parsed.instructor,
        semester=parsed.semester,
        syllabus_path=str(pdf_path),
    )

    notif = settings.get("notifications", {})
    reminder_days = notif.get("reminder_days_before", [7, 3, 1])
    method = notif.get("method", "discord")
    count = 0

    for deadline in parsed.deadlines:
        if not deadline.parsed_date:
            continue
        deadline_id = db.insert_deadline(
            course_id=course_id,
            title=deadline.title,
            deadline_date=deadline.parsed_date,
            deadline_type=deadline.deadline_type,
            weight_percent=deadline.weight_percent,
        )
        scheduler.create_reminder_cron(
            deadline_id=deadline_id,
            deadline_date=deadline.parsed_date,
            reminder_days=reminder_days,
            message=f"[{parsed.course_name}] Due: {deadline.title[:80]}",
        )
        count += 1

    scheduler.notify(
        "📚 Syllabus Processed",
        f"**{parsed.course_name}** — {count} deadlines added.",
        method=method,
    )
    logger.success(f"Done. {count} deadlines saved for '{parsed.course_name}'.")


if __name__ == "__main__":
    main()
