"""
main.py
────────
Entry point for the Academic Orchestrator.

Starts three background threads:
  1. Watchdog — monitors data/raw_syllabi/ for new PDFs
  2. Scheduler — runs the daily digest at the configured time
  3. Flask dashboard — serves the web UI on configured port

Usage:
  python main.py                   # full stack
  python main.py --phase 1         # watchdog + notifications only
  python main.py --phase 2         # + research agent + dashboard
  python main.py --phase 3         # full multi-agent mode
  python main.py --dashboard-only  # just the Flask UI
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from loguru import logger
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# ── Bootstrap ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
load_dotenv(ROOT / "config" / ".env")

# Configure loguru
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    ROOT / "logs" / "orchestrator.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
)


def load_settings() -> dict:
    cfg = ROOT / "config" / "settings.yaml"
    return yaml.safe_load(cfg.read_text()) if cfg.exists() else {}


# ── Syllabus Watchdog ─────────────────────────────────────────────────────────

class SyllabusHandler(FileSystemEventHandler):
    """Reacts to new PDF files dropped into the watch folder."""

    def __init__(self, db, scheduler, settings: dict) -> None:
        self.db = db
        self.scheduler = scheduler
        self.settings = settings
        self._processing: set[str] = set()

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".pdf" or str(path) in self._processing:
            return

        self._processing.add(str(path))
        logger.info(f"📄 New syllabus detected: {path.name}")

        try:
            self._process_pdf(path)
        except Exception as exc:
            logger.error(f"Failed to process {path.name}: {exc}")
        finally:
            self._processing.discard(str(path))

    def _process_pdf(self, path: Path) -> None:
        from core.pdf_processor import PDFProcessor

        processor = PDFProcessor()
        parsed = processor.process(path)

        # Save course to DB
        course_id = self.db.upsert_course(
            name=parsed.course_name,
            code=parsed.course_code,
            instructor=parsed.instructor,
            semester=parsed.semester,
            syllabus_path=str(path),
        )

        notif_settings = self.settings.get("notifications", {})
        reminder_days = notif_settings.get("reminder_days_before", [7, 3, 1])
        method = notif_settings.get("method", "discord")

        for deadline in parsed.deadlines:
            if not deadline.parsed_date:
                logger.warning(f"Could not parse date for: {deadline.title[:60]}")
                continue

            deadline_id = self.db.insert_deadline(
                course_id=course_id,
                title=deadline.title,
                deadline_date=deadline.parsed_date,
                deadline_type=deadline.deadline_type,
                weight_percent=deadline.weight_percent,
            )

            # Create Linux cron jobs
            cron_ids = self.scheduler.create_reminder_cron(
                deadline_id=deadline_id,
                deadline_date=deadline.parsed_date,
                reminder_days=reminder_days,
                message=f"[{parsed.course_name}] Due: {deadline.title[:80]}",
            )

        # Send a summary notification
        summary = (
            f"📚 Syllabus processed: **{parsed.course_name}**\n"
            f"Found **{len(parsed.deadlines)}** deadlines."
        )
        self.scheduler.notify("New Syllabus Loaded", summary, method=method)
        logger.success(f"Syllabus '{parsed.course_name}' fully processed.")


# ── Thread Launchers ──────────────────────────────────────────────────────────

def start_watchdog(settings: dict, db, scheduler) -> Observer:
    watch_dir = ROOT / settings.get("paths", {}).get("watch_folder", "data/raw_syllabi")
    watch_dir.mkdir(parents=True, exist_ok=True)

    handler = SyllabusHandler(db, scheduler, settings)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()
    logger.info(f"👁  Watchdog started on: {watch_dir}")
    return observer


def start_dashboard(settings: dict) -> threading.Thread:
    def _run():
        import dashboard.app as dash_app
        dash_cfg = settings.get("dashboard", {})
        dash_app.app.run(
            host=dash_cfg.get("host", "0.0.0.0"),
            port=dash_cfg.get("port", 5000),
            debug=False,
            use_reloader=False,
        )

    t = threading.Thread(target=_run, daemon=True, name="FlaskDashboard")
    t.start()
    logger.info("🌐 Dashboard thread started")
    return t


def start_digest_scheduler(settings: dict, db, scheduler) -> threading.Thread:
    digest_time = settings.get("scheduler", {}).get("morning_digest_time", "08:00")
    method = settings.get("notifications", {}).get("method", "discord")

    t = threading.Thread(
        target=scheduler.start_daily_digest,
        kwargs={"digest_time": digest_time, "notification_method": method},
        daemon=True,
        name="DigestScheduler",
    )
    t.start()
    logger.info(f"⏰ Daily digest scheduler started (fires at {digest_time})")
    return t


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Academic Orchestrator")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], default=3,
                        help="Which phases to activate (1=basic, 2=+research, 3=+agents)")
    parser.add_argument("--dashboard-only", action="store_true",
                        help="Start only the Flask dashboard")
    parser.add_argument("--research", type=str, metavar="QUERY",
                        help="Run a one-off research query and exit")
    parser.add_argument("--review-pr", type=int, metavar="PR_NUMBER",
                        help="Run code review on a specific PR and exit")
    parser.add_argument("--sprint-check", action="store_true",
                        help="Run a sprint check and print the report")
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    console = Console()
    args = parse_args()
    settings = load_settings()

    console.print(Panel(
        Text("🎓 Academic Orchestrator", style="bold purple") +
        Text(f"\n  Phase: {args.phase}  |  Dashboard: 5000", style="dim"),
        border_style="purple",
    ))

    from core.database_manager import DatabaseManager
    from core.scheduler import Scheduler

    db = DatabaseManager()
    scheduler = Scheduler(db_manager=db)

    # ── One-off commands ───────────────────────────────────────────────────────
    if args.research:
        from agents.researcher import ResearcherAgent
        agent = ResearcherAgent(db_manager=db)
        result = agent.research(args.research)
        console.print(result["summary"])
        return

    if args.review_pr:
        from agents.code_reviewer import CodeReviewerAgent
        agent = CodeReviewerAgent(db_manager=db)
        result = agent.review_pull_request(args.review_pr)
        console.print(result.get("summary", "No summary generated."))
        return

    if args.sprint_check:
        from agents.scrum_master import ScrumMasterAgent
        agent = ScrumMasterAgent(db_manager=db, scheduler=scheduler)
        report = agent.run_sprint_check()
        import json
        console.print_json(json.dumps(report, indent=2, default=str))
        return

    # ── Long-running mode ──────────────────────────────────────────────────────
    threads: list[threading.Thread] = []
    observer: Observer | None = None

    if args.dashboard_only:
        start_dashboard(settings)
    else:
        # Phase 1 – always on
        observer = start_watchdog(settings, db, scheduler)
        threads.append(start_digest_scheduler(settings, db, scheduler))

        # Phase 2+ – dashboard
        if args.phase >= 2:
            threads.append(start_dashboard(settings))

    logger.info("✅ Orchestrator running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down…")
        if observer:
            observer.stop()
            observer.join()
        logger.info("Goodbye!")


if __name__ == "__main__":
    main()
