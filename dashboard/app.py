"""
app.py
───────
Phase 2 – Flask Dashboard.

Routes:
  GET  /                   → Main dashboard (deadlines, research, reviews)
  GET  /api/deadlines      → JSON list of upcoming deadlines
  GET  /api/research       → JSON list of research sessions
  POST /api/research       → Trigger a new research query
  GET  /api/reviews        → JSON list of PR reviews
  POST /api/review_pr      → Trigger a PR review
  GET  /api/scrum          → JSON sprint health report
  POST /api/mark_done/<id> → Mark a deadline complete
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request, redirect, url_for
from dotenv import load_dotenv
from loguru import logger

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / "config" / ".env")

from core.database_manager import DatabaseManager
from agents.researcher import ResearcherAgent
from agents.code_reviewer import CodeReviewerAgent
from agents.scrum_master import ScrumMasterAgent

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# ── Shared singletons (initialised lazily) ────────────────────────────────────
_db: DatabaseManager | None = None
_researcher: ResearcherAgent | None = None
_reviewer: CodeReviewerAgent | None = None
_scrum: ScrumMasterAgent | None = None


def _get_db() -> DatabaseManager:
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db


def _get_researcher() -> ResearcherAgent:
    global _researcher
    if _researcher is None:
        _researcher = ResearcherAgent(db_manager=_get_db(), vector_db_path=str(ROOT / "data/vector_db"))
    return _researcher


def _get_reviewer() -> CodeReviewerAgent:
    global _reviewer
    if _reviewer is None:
        _reviewer = CodeReviewerAgent(db_manager=_get_db())
    return _reviewer


def _get_scrum() -> ScrumMasterAgent:
    global _scrum
    if _scrum is None:
        _scrum = ScrumMasterAgent(db_manager=_get_db())
    return _scrum


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/research")
def research_page():
    return render_template("research.html")


@app.route("/reviews")
def reviews_page():
    return render_template("reviews.html")


@app.route("/scrum")
def scrum_page():
    return render_template("scrum.html")


# ── API – Deadlines ───────────────────────────────────────────────────────────

@app.route("/api/deadlines")
def api_deadlines():
    try:
        days = int(request.args.get("days", 30))
        deadlines = _get_db().get_upcoming_deadlines(days_ahead=days)
        for d in deadlines:
            if hasattr(d.get("deadline_date"), "isoformat"):
                d["deadline_date"] = d["deadline_date"].isoformat()
            if hasattr(d.get("created_at"), "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
        return jsonify({"deadlines": deadlines})
    except Exception as exc:
        logger.error(f"/api/deadlines error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/mark_done/<int:deadline_id>", methods=["POST"])
def api_mark_done(deadline_id: int):
    try:
        _get_db().mark_deadline_complete(deadline_id)
        return jsonify({"status": "ok", "deadline_id": deadline_id})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── API – Research ─────────────────────────────────────────────────────────────

@app.route("/api/research", methods=["GET"])
def api_research_list():
    try:
        sessions = _get_db().get_research_sessions(limit=20)
        for s in sessions:
            if hasattr(s.get("created_at"), "isoformat"):
                s["created_at"] = s["created_at"].isoformat()
        return jsonify({"sessions": sessions})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/research", methods=["POST"])
def api_research_run():
    data = request.get_json(force=True)
    query = (data or {}).get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    def _run():
        try:
            result = _get_researcher().research(query)
            logger.success(f"Research complete for: {query}")
        except Exception as exc:
            logger.error(f"Background research failed: {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "query": query})


# ── API – Code Reviews ─────────────────────────────────────────────────────────

@app.route("/api/reviews", methods=["GET"])
def api_reviews_list():
    try:
        reviews = _get_db().get_pr_reviews(limit=20)
        for r in reviews:
            if hasattr(r.get("reviewed_at"), "isoformat"):
                r["reviewed_at"] = r["reviewed_at"].isoformat()
        return jsonify({"reviews": reviews})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/review_pr", methods=["POST"])
def api_review_pr():
    data = request.get_json(force=True)
    pr_number = int((data or {}).get("pr_number", 0))
    if not pr_number:
        return jsonify({"error": "pr_number is required"}), 400

    def _run():
        try:
            _get_reviewer().review_pull_request(pr_number)
        except Exception as exc:
            logger.error(f"PR review failed: {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "pr_number": pr_number})


@app.route("/api/review_code", methods=["POST"])
def api_review_code():
    data = request.get_json(force=True)
    code = (data or {}).get("code", "")
    filename = (data or {}).get("filename", "snippet.py")
    if not code:
        return jsonify({"error": "code is required"}), 400
    try:
        result = _get_reviewer().review_code_string(code, filename)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── API – Scrum ────────────────────────────────────────────────────────────────

@app.route("/api/scrum")
def api_scrum():
    try:
        report = _get_scrum().run_sprint_check()
        return jsonify(report)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/scrum/dashboard")
def api_scrum_dashboard():
    try:
        data = _get_scrum().get_team_dashboard()
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── API – Semantic Search ─────────────────────────────────────────────────────

@app.route("/api/semantic_search")
def api_semantic_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q param required"}), 400
    try:
        results = _get_researcher().semantic_search(query)
        return jsonify({"results": results})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import yaml
    cfg_path = ROOT / "config" / "settings.yaml"
    settings = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    dash_cfg = settings.get("dashboard", {})
    app.run(
        host=dash_cfg.get("host", "0.0.0.0"),
        port=dash_cfg.get("port", 5000),
        debug=os.getenv("DEBUG", "false").lower() == "true",
    )
