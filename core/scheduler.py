"""
scheduler.py
────────────
Phase 1 – Cron Job Manager + Notification Dispatcher.

Responsibilities:
  1. Create Linux cron entries that fire reminder scripts.
  2. Dispatch Discord / email notifications on demand.
  3. Run a lightweight in-process scheduler for the daily digest.
"""

from __future__ import annotations

import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

import discord
import schedule
import time
import asyncio
from crontab import CronTab
from dotenv import load_dotenv
from loguru import logger

load_dotenv("config/.env")

# ── Constants ─────────────────────────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


class Scheduler:
    """Creates cron jobs and sends notifications."""

    def __init__(self, db_manager=None) -> None:
        self.db = db_manager
        self._cron = CronTab(user=True)

    # ── Cron Job Management ───────────────────────────────────────────────────

    def create_reminder_cron(
        self,
        deadline_id: int,
        deadline_date: datetime,
        reminder_days: list[int],
        message: str,
    ) -> list[str]:
        """
        Creates one cron job per reminder day.
        Returns a list of cron job comment-IDs that were created.
        """
        job_ids: list[str] = []
        script_path = Path(__file__).parent.parent / "scripts" / "send_reminder.py"

        for days_before in reminder_days:
            remind_dt = deadline_date - timedelta(days=days_before)
            if remind_dt < datetime.now():
                logger.debug(f"Skipping past reminder ({days_before}d before) for deadline {deadline_id}")
                continue

            job_comment = f"orchestrator_dl_{deadline_id}_{days_before}d"

            # Remove old job with same comment if exists
            self._cron.remove_all(comment=job_comment)

            job = self._cron.new(
                command=(
                    f"python3 {script_path} --deadline_id {deadline_id} "
                    f'--message "{message[:100]}"'
                ),
                comment=job_comment,
            )
            job.setall(
                remind_dt.minute,
                remind_dt.hour,
                remind_dt.day,
                remind_dt.month,
                "*",
            )
            self._cron.write()
            job_ids.append(job_comment)
            logger.success(
                f"Cron job set: remind {days_before}d before deadline {deadline_id} "
                f"at {remind_dt.strftime('%Y-%m-%d %H:%M')}"
            )

        return job_ids

    def remove_deadline_crons(self, deadline_id: int) -> None:
        """Remove all cron jobs associated with a deadline."""
        self._cron.remove_all(comment=f"orchestrator_dl_{deadline_id}_")
        self._cron.write()
        logger.info(f"Removed cron jobs for deadline {deadline_id}")

    # ── Notification Dispatch ─────────────────────────────────────────────────

    def send_discord_message(self, message: str) -> None:
        """Send a message to the configured Discord channel."""
        if not DISCORD_TOKEN or not DISCORD_CHANNEL_ID:
            logger.warning("Discord credentials not configured.")
            return

        async def _send():
            intents = discord.Intents.default()
            client = discord.Client(intents=intents)

            @client.event
            async def on_ready():
                channel = client.get_channel(DISCORD_CHANNEL_ID)
                if channel:
                    await channel.send(message)
                    logger.success(f"Discord message sent to channel {DISCORD_CHANNEL_ID}")
                else:
                    logger.error("Discord channel not found.")
                await client.close()

            await client.start(DISCORD_TOKEN)

        asyncio.run(_send())

    def send_email(self, subject: str, body: str) -> None:
        """Send a plain-text email via SMTP."""
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.warning("Email credentials not configured.")
            return
        try:
            msg = MIMEText(body, "plain")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = SMTP_USER  # send to self – change as needed

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            logger.success(f"Email sent: {subject}")
        except Exception as exc:
            logger.error(f"Email failed: {exc}")

    def notify(self, subject: str, body: str, method: str = "discord") -> None:
        """Unified notification gateway."""
        if method in ("discord", "both"):
            self.send_discord_message(f"**{subject}**\n{body}")
        if method in ("email", "both"):
            self.send_email(subject, body)

    # ── In-process daily digest ────────────────────────────────────────────────

    def start_daily_digest(
        self, digest_time: str = "08:00", notification_method: str = "discord"
    ) -> None:
        """
        Blocks the current thread running a daily summary job.
        Typically called in a background thread from main.py.
        """
        logger.info(f"Daily digest scheduler started – fires at {digest_time}")

        schedule.every().day.at(digest_time).do(
            self._run_daily_digest, method=notification_method
        )

        while True:
            schedule.run_pending()
            time.sleep(30)

    def _run_daily_digest(self, method: str) -> None:
        if not self.db:
            return
        deadlines = self.db.get_upcoming_deadlines(days_ahead=7)
        if not deadlines:
            msg_body = "No deadlines in the next 7 days. Keep it up! 🎉"
        else:
            lines = ["📅 **Upcoming Deadlines (next 7 days):**"]
            for d in deadlines:
                date_str = d["deadline_date"].strftime("%a %b %d")
                lines.append(f"  • [{d['course_name']}] {d['title']} — **{date_str}**")
            msg_body = "\n".join(lines)

        self.notify("🎓 Daily Academic Digest", msg_body, method=method)
