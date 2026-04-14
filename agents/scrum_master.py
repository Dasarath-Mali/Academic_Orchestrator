"""
scrum_master.py
────────────────
Phase 3 – Scrum Master Agent.

Monitors a GitHub repository for:
  • Stale issues / PRs (no activity for N days)
  • Team members with no recent commits
  • Deadline proximity vs open tasks

Uses Google Gemini (FREE) to draft polite, personalised nudge messages
and optionally sends them via Discord or GitHub issue comments.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import google.generativeai as genai
from github import Github, GithubException
from loguru import logger
from dotenv import load_dotenv

load_dotenv("config/.env")

GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "")
GITHUB_REPO_NAME  = os.getenv("GITHUB_REPO_NAME", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class ScrumMasterAgent:
    """
    Monitors team GitHub activity and generates polite nudge messages
    for stale issues and lagging contributors.
    Uses Gemini (FREE) for message drafting.
    """

    def __init__(
        self,
        db_manager=None,
        scheduler=None,
        stale_days: int = 2,
        auto_message: bool = False,
    ) -> None:
        self.db           = db_manager
        self.scheduler    = scheduler
        self.stale_days   = stale_days
        self.auto_message = auto_message
        self._gemini      = genai.GenerativeModel(GEMINI_MODEL) if GEMINI_API_KEY else None
        self._gh          = Github(GITHUB_TOKEN) if GITHUB_TOKEN else None

    # ── Public API ────────────────────────────────────────────────────────────

    def run_sprint_check(self) -> dict[str, Any]:
        """Full sprint health check. Returns a structured report."""
        if not self._gh:
            logger.error("GITHUB_TOKEN not configured.")
            return {"error": "GITHUB_TOKEN not configured."}

        repo = self._gh.get_repo(f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
        logger.info(f"Running sprint check on {repo.full_name}")

        stale_issues         = self._find_stale_issues(repo)
        open_prs             = self._get_open_prs(repo)
        contributor_activity = self._analyse_contributor_activity(repo)
        messages             = self._draft_nudge_messages(stale_issues, contributor_activity)

        report = {
            "timestamp":             datetime.now().isoformat(),
            "repo":                  repo.full_name,
            "stale_issues":          stale_issues,
            "open_prs":              open_prs,
            "contributor_activity":  contributor_activity,
            "nudge_messages":        messages,
        }

        if self.auto_message:
            self._dispatch_messages(messages, repo)

        return report

    def get_team_dashboard(self) -> dict[str, Any]:
        """Lightweight summary for the Flask dashboard."""
        if not self._gh:
            return {"error": "GITHUB_TOKEN not configured."}
        try:
            repo          = self._gh.get_repo(f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
            open_issues   = list(repo.get_issues(state="open"))
            open_prs      = list(repo.get_pulls(state="open"))
            recent_commits = list(repo.get_commits()[:10])
            return {
                "open_issues_count": len(open_issues),
                "open_prs_count":    len(open_prs),
                "recent_commits": [
                    {
                        "sha":     c.sha[:7],
                        "author":  c.commit.author.name,
                        "message": c.commit.message.splitlines()[0][:80],
                        "date":    c.commit.author.date.isoformat(),
                    }
                    for c in recent_commits
                ],
            }
        except GithubException as exc:
            return {"error": str(exc)}

    # ── GitHub Analysis ───────────────────────────────────────────────────────

    def _find_stale_issues(self, repo) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.stale_days)
        stale: list[dict] = []
        try:
            for issue in repo.get_issues(state="open"):
                if issue.updated_at < cutoff:
                    stale.append({
                        "number":       issue.number,
                        "title":        issue.title,
                        "assignees":    [a.login for a in issue.assignees],
                        "last_updated": issue.updated_at.isoformat(),
                        "url":          issue.html_url,
                        "days_stale":   (datetime.now(timezone.utc) - issue.updated_at).days,
                    })
        except GithubException as exc:
            logger.error(f"Error fetching issues: {exc}")
        return stale

    def _get_open_prs(self, repo) -> list[dict]:
        try:
            return [
                {
                    "number":     pr.number,
                    "title":      pr.title,
                    "author":     pr.user.login,
                    "created_at": pr.created_at.isoformat(),
                    "url":        pr.html_url,
                    "draft":      pr.draft,
                }
                for pr in repo.get_pulls(state="open")
            ]
        except GithubException as exc:
            logger.error(f"Error fetching PRs: {exc}")
            return []

    def _analyse_contributor_activity(self, repo) -> list[dict]:
        """Commit count per contributor over the last 7 days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        activity: dict[str, int] = {}
        try:
            for commit in repo.get_commits(since=cutoff):
                author = commit.author.login if commit.author else "unknown"
                activity[author] = activity.get(author, 0) + 1
        except GithubException as exc:
            logger.error(f"Error analysing commits: {exc}")
        return [
            {"username": u, "commits_last_7d": c}
            for u, c in sorted(activity.items(), key=lambda x: -x[1])
        ]

    # ── Gemini Nudge Message Drafting (FREE) ──────────────────────────────────

    def _draft_nudge_messages(
        self,
        stale_issues: list[dict],
        contributor_activity: list[dict],
    ) -> list[dict]:
        if not self._gemini or not stale_issues:
            return []

        inactive = [c["username"] for c in contributor_activity if c["commits_last_7d"] == 0]

        issue_block = "\n".join(
            f"- Issue #{i['number']}: '{i['title']}' "
            f"(stale {i['days_stale']}d, assigned to: {', '.join(i['assignees']) or 'nobody'})"
            for i in stale_issues[:10]
        )

        prompt = f"""You are a friendly Scrum Master bot for a student project team.
Draft SHORT, polite, encouraging status-update messages for the following:

Stale Issues (no activity for 2+ days):
{issue_block}

Team members with ZERO commits in the last 7 days: {', '.join(inactive) or 'None'}

Rules:
- Write one message per stale issue (addressed to assignee, or "team" if unassigned).
- If there are inactive members, write one combined message for all of them.
- Be warm and non-accusatory — assume people are busy with exams/coursework.
- Each message must be under 3 sentences.
- Return ONLY a valid JSON array in this exact format, with no extra text, no markdown fences:
[{{"recipient": "username_or_team", "context": "issue #N / inactivity", "message": "..."}}]"""

        try:
            response = self._gemini.generate_content(prompt)
            content = (response.text or "[]").strip()
            # Strip any accidental markdown code fences
            content = content.lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(content)
        except Exception as exc:
            logger.warning(f"Could not parse Gemini nudge messages: {exc}")
            return []

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch_messages(self, messages: list[dict], repo) -> None:
        for msg_data in messages:
            recipient = msg_data.get("recipient", "team")
            context   = msg_data.get("context", "")
            message   = msg_data.get("message", "")
            if not message:
                continue

            # Post to the GitHub issue if context references one
            issue_num = self._extract_issue_number(context)
            if issue_num:
                try:
                    issue = repo.get_issue(issue_num)
                    issue.create_comment(
                        f"👋 @{recipient} {message}\n\n"
                        "*— Automated Scrum Master Check-in (Gemini)*"
                    )
                    logger.success(f"Posted comment on issue #{issue_num}")
                except GithubException as exc:
                    logger.error(f"Failed to post issue comment: {exc}")

            # Also send to Discord if scheduler available
            if self.scheduler:
                self.scheduler.send_discord_message(
                    f"📌 **Scrum Check-in** | @{recipient}\n> {message}"
                )

            # Save to DB
            if self.db:
                self.db.save_scrum_update(
                    member_id=None,
                    issue_number=issue_num or 0,
                    status_note=context,
                    message_sent=message,
                )

    def _extract_issue_number(self, context: str) -> int | None:
        import re
        match = re.search(r"issue\s*#(\d+)", context, re.IGNORECASE)
        return int(match.group(1)) if match else None
