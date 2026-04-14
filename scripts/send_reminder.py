"""
send_reminder.py
─────────────────
Called by cron jobs to send a deadline reminder.

Usage (generated automatically by scheduler.py):
  python3 scripts/send_reminder.py --deadline_id 7 --message "Assignment 2 due!"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

import yaml
from loguru import logger
from core.database_manager import DatabaseManager
from core.scheduler import Scheduler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deadline_id", type=int, required=True)
    parser.add_argument("--message", type=str, required=True)
    args = parser.parse_args()

    cfg_path = ROOT / "config" / "settings.yaml"
    settings = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    method = settings.get("notifications", {}).get("method", "discord")

    db = DatabaseManager()
    scheduler = Scheduler(db_manager=db)

    subject = f"⏰ Deadline Reminder #{args.deadline_id}"
    body = args.message

    scheduler.notify(subject, body, method=method)
    db.log_notification(
        deadline_id=args.deadline_id,
        channel=method,
        message=body,
        status="sent",
    )
    logger.success(f"Reminder sent for deadline #{args.deadline_id}")


if __name__ == "__main__":
    main()
