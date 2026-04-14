"""
code_reviewer.py
─────────────────
Phase 3 – Automated Code Review Agent.

For each new PR / code submission:
  1. Runs pylint + bandit for static analysis.
  2. Uses lizard to compute cyclomatic complexity.
  3. Sends code + static-analysis results to Google Gemini (FREE) for a
     human-style structured review.
  4. Posts the review as a comment directly on the GitHub PR.
  5. Saves the review to MySQL.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
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


class CodeReviewerAgent:
    """Automated code reviewer — static analysis + Gemini LLM review (FREE)."""

    def __init__(self, db_manager=None, complexity_threshold: int = 10) -> None:
        self.db = db_manager
        self.complexity_threshold = complexity_threshold
        self._gemini = genai.GenerativeModel(GEMINI_MODEL) if GEMINI_API_KEY else None
        self._gh     = Github(GITHUB_TOKEN) if GITHUB_TOKEN else None

    # ── Public API ────────────────────────────────────────────────────────────

    def review_pull_request(self, pr_number: int) -> dict[str, Any]:
        """Full pipeline for a GitHub PR. Posts a review comment and saves to DB."""
        if not self._gh:
            logger.error("GITHUB_TOKEN not configured.")
            return {}

        repo = self._gh.get_repo(f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
        pr   = repo.get_pull(pr_number)
        logger.info(f"Reviewing PR #{pr_number}: {pr.title}")

        all_issues: list[dict]  = []
        code_snippets: list[str] = []
        max_complexity = 0.0

        for file in pr.get_files():
            if not self._is_reviewable(file.filename):
                continue
            patch = file.patch or ""
            code_snippets.append(f"### {file.filename}\n```\n{patch[:3000]}\n```")
            issues, complexity = self._run_static_analysis(file.filename, patch)
            all_issues.extend(issues)
            max_complexity = max(max_complexity, complexity)

        full_code = "\n\n".join(code_snippets[:5])
        review_summary = self._llm_review(
            pr_title=pr.title,
            pr_body=pr.body or "",
            code_context=full_code,
            static_issues=all_issues,
        )

        # Post GitHub comment
        comment = self._format_github_comment(review_summary, all_issues, max_complexity)
        pr.create_issue_comment(comment)
        logger.success(f"Posted review comment on PR #{pr_number}")

        # Save to DB
        if self.db:
            self.db.save_pr_review(
                pr_number=pr_number,
                pr_title=pr.title,
                author=pr.user.login,
                review_summary=review_summary,
                issues_found=all_issues,
                complexity_score=max_complexity,
            )

        return {
            "pr_number": pr_number,
            "summary":   review_summary,
            "issues":    all_issues,
            "complexity": max_complexity,
        }

    def review_code_string(self, code: str, filename: str = "snippet.py") -> dict[str, Any]:
        """Review a raw code string without needing GitHub."""
        issues, complexity = self._run_static_analysis(filename, code)
        summary = self._llm_review(
            pr_title=filename,
            pr_body="",
            code_context=f"```\n{code[:4000]}\n```",
            static_issues=issues,
        )
        return {"summary": summary, "issues": issues, "complexity": complexity}

    # ── Static Analysis ───────────────────────────────────────────────────────

    def _run_static_analysis(self, filename: str, code: str) -> tuple[list[dict], float]:
        issues: list[dict] = []
        complexity = 0.0
        ext = Path(filename).suffix.lower()

        with tempfile.NamedTemporaryFile(suffix=ext or ".py", mode="w", delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            if ext == ".py":
                issues += self._run_pylint(tmp_path)
                issues += self._run_bandit(tmp_path)
            complexity = self._run_lizard(tmp_path)
            if complexity > self.complexity_threshold:
                issues.append({
                    "severity": "warning",
                    "line": 0,
                    "message": (
                        f"High cyclomatic complexity ({complexity:.1f}) – "
                        "consider breaking this into smaller functions."
                    ),
                })
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return issues, complexity

    def _run_pylint(self, path: str) -> list[dict]:
        result = subprocess.run(
            ["pylint", "--output-format=json", "--score=no", path],
            capture_output=True, text=True
        )
        try:
            raw = json.loads(result.stdout or "[]")
            return [
                {
                    "severity": msg.get("type", "info"),
                    "line":     msg.get("line", 0),
                    "message":  f"[pylint {msg.get('message-id','')}] {msg.get('message','')}",
                }
                for msg in raw if msg.get("type") in ("error", "warning")
            ]
        except Exception:
            return []

    def _run_bandit(self, path: str) -> list[dict]:
        result = subprocess.run(
            ["bandit", "-r", "-f", "json", path],
            capture_output=True, text=True
        )
        try:
            data = json.loads(result.stdout or "{}")
            return [
                {
                    "severity": r.get("issue_severity", "low").lower(),
                    "line":     r.get("line_number", 0),
                    "message":  f"[bandit] {r.get('issue_text','')}",
                }
                for r in data.get("results", [])
            ]
        except Exception:
            return []

    def _run_lizard(self, path: str) -> float:
        result = subprocess.run(["lizard", path, "--csv"], capture_output=True, text=True)
        complexities = []
        for line in result.stdout.splitlines():
            parts = line.split(",")
            if len(parts) > 2:
                try:
                    complexities.append(float(parts[2]))
                except ValueError:
                    pass
        return max(complexities, default=0.0)

    # ── Gemini LLM Review (FREE) ───────────────────────────────────────────────

    def _llm_review(
        self,
        pr_title: str,
        pr_body: str,
        code_context: str,
        static_issues: list[dict],
    ) -> str:
        if not self._gemini:
            return "⚠️ GEMINI_API_KEY not configured. Get your free key at aistudio.google.com"

        issues_block = "\n".join(
            f"- [{i['severity'].upper()}] Line {i['line']}: {i['message']}"
            for i in static_issues[:20]
        ) or "No static analysis issues detected."

        prompt = f"""You are a senior software engineer doing a thorough but friendly code review for a student.

PR Title: {pr_title}
PR Description: {pr_body[:400] or 'No description provided.'}

Static Analysis Results:
{issues_block}

Code Changes:
{code_context[:4000]}

Write a structured code review with these sections:
1. **Summary** – overall quality assessment in 1-2 sentences
2. **Correctness** – any logic errors, edge cases, or bugs
3. **Security** – any risky patterns or vulnerabilities
4. **Code Quality** – readability, naming conventions, structure
5. **Performance** – any obvious inefficiencies
6. **Suggestions** – specific actionable improvements (with short code examples where helpful)
7. **Verdict** – one of: ✅ Approve | ⚠️ Request Changes | 🔴 Major Revision Needed

Be constructive and educational — this is a student project. Use markdown."""

        try:
            response = self._gemini.generate_content(prompt)
            return response.text or ""
        except Exception as exc:
            logger.error(f"Gemini review failed: {exc}")
            return f"⚠️ Gemini error: {exc}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_reviewable(self, filename: str) -> bool:
        return Path(filename).suffix.lower() in {".py", ".c", ".cpp", ".h", ".js", ".ts"}

    def _format_github_comment(
        self, summary: str, issues: list[dict], complexity: float
    ) -> str:
        return "\n".join([
            "## 🤖 Automated Code Review",
            f"> Complexity score: **{complexity:.1f}** | Issues found: **{len(issues)}**",
            "",
            summary,
            "",
            "---",
            "*Generated by the Academic Orchestrator – Code Review Agent (Gemini)*",
        ])
