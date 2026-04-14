"""
researcher.py
─────────────
Phase 2 – Autonomous Researcher Agent.

Given a natural-language query, this agent:
  1. Searches GitHub for relevant open-source repos.
  2. Searches the web (Serper API) for tutorials / articles.
  3. Uses Google Gemini (FREE) to synthesise a structured research brief.
  4. Saves everything to MySQL + ChromaDB for semantic retrieval later.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests
import google.generativeai as genai
from github import Github, GithubException
from loguru import logger
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv("config/.env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# Configure Gemini once at import time
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class ResearcherAgent:
    """
    Autonomous research agent.
    Combines GitHub search, Serper web search, and Gemini synthesis.
    Everything is FREE to run.
    """

    def __init__(self, db_manager=None, vector_db_path: str = "data/vector_db") -> None:
        self.db = db_manager
        self._gh = Github(GITHUB_TOKEN) if GITHUB_TOKEN else None
        self._gemini = genai.GenerativeModel(GEMINI_MODEL) if GEMINI_API_KEY else None

        self._vector_client = chromadb.PersistentClient(path=vector_db_path)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._collection = self._vector_client.get_or_create_collection(
            name="research_notes",
            embedding_function=self._ef,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def research(
        self,
        query: str,
        course_id: int | None = None,
        max_github: int = 8,
        max_web: int = 8,
    ) -> dict[str, Any]:
        """
        Full research pipeline. Returns a dict with:
          summary, github_repos, web_sources, session_id
        """
        logger.info(f"🔍 Researching: '{query}'")

        github_repos = self._search_github(query, max_github)
        web_sources  = self._search_web(query, max_web)
        summary      = self._synthesise(query, github_repos, web_sources)

        # Persist to MySQL
        session_id = None
        if self.db:
            session_id = self.db.save_research_session(
                query=query,
                summary=summary,
                sources=web_sources,
                github_repos=github_repos,
                course_id=course_id,
            )

        # Persist to ChromaDB
        self._store_in_vector_db(session_id or 0, query, summary)

        logger.success(f"Research complete – session_id={session_id}")
        return {
            "query": query,
            "summary": summary,
            "github_repos": github_repos,
            "web_sources": web_sources,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }

    def semantic_search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search past research notes semantically via ChromaDB."""
        results = self._collection.query(query_texts=[query], n_results=n_results)
        docs  = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [{"text": d, "meta": m} for d, m in zip(docs, metas)]

    # ── GitHub Search ─────────────────────────────────────────────────────────

    def _search_github(self, query: str, limit: int) -> list[dict]:
        if not self._gh:
            logger.warning("GITHUB_TOKEN not set – skipping GitHub search.")
            return []
        try:
            repos = self._gh.search_repositories(query=query, sort="stars", order="desc")
            results = []
            for repo in repos[:limit]:
                results.append({
                    "name":        repo.full_name,
                    "url":         repo.html_url,
                    "stars":       repo.stargazers_count,
                    "description": repo.description or "",
                    "language":    repo.language or "Unknown",
                    "topics":      repo.get_topics(),
                })
            logger.debug(f"GitHub: {len(results)} repos for '{query}'")
            return results
        except GithubException as exc:
            logger.error(f"GitHub search failed: {exc}")
            return []

    # ── Web Search (Serper — free 2500/mo) ───────────────────────────────────

    def _search_web(self, query: str, limit: int) -> list[dict]:
        if not SERPER_API_KEY:
            logger.warning("SERPER_API_KEY not set – skipping web search.")
            return []
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": limit},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("organic", []):
                results.append({
                    "title":   item.get("title", ""),
                    "url":     item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            logger.debug(f"Web search: {len(results)} results for '{query}'")
            return results
        except Exception as exc:
            logger.error(f"Web search failed: {exc}")
            return []

    # ── Gemini Synthesis (FREE) ────────────────────────────────────────────────

    def _synthesise(
        self, query: str, github_repos: list[dict], web_sources: list[dict]
    ) -> str:
        if not self._gemini:
            return "⚠️ GEMINI_API_KEY not configured. Get your free key at aistudio.google.com"

        github_block = "\n".join(
            f"- [{r['name']}]({r['url']}) ⭐{r['stars']}: {r['description']}"
            for r in github_repos[:5]
        ) or "No GitHub repos found."

        web_block = "\n".join(
            f"- [{s['title']}]({s['url']})\n  {s['snippet']}"
            for s in web_sources[:5]
        ) or "No web results found."

        prompt = f"""You are an expert academic research assistant helping a student.
The student is researching: "{query}"

GitHub repositories found:
{github_block}

Web articles found:
{web_block}

Write a structured research brief (max 600 words) with these sections:
1. **Overview** – what this topic is about in simple terms
2. **Key Concepts** – 3-5 bullet points the student must understand
3. **Best Resources** – which repos/articles to start with and why
4. **Implementation Tips** – practical advice for building an assignment around this
5. **Pitfalls to Avoid** – common mistakes beginners make

Use markdown formatting. Be direct and student-friendly."""

        try:
            response = self._gemini.generate_content(prompt)
            return response.text or ""
        except Exception as exc:
            logger.error(f"Gemini synthesis failed: {exc}")
            return f"⚠️ Gemini error: {exc}"

    # ── Vector Store ──────────────────────────────────────────────────────────

    def _store_in_vector_db(self, session_id: int, query: str, summary: str) -> None:
        try:
            self._collection.add(
                documents=[summary],
                metadatas=[{"query": query, "session_id": str(session_id)}],
                ids=[f"session_{session_id}_{int(datetime.now().timestamp())}"],
            )
        except Exception as exc:
            logger.warning(f"ChromaDB store failed: {exc}")
