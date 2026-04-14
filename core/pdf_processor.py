"""
pdf_processor.py
────────────────
Phase 1 – Syllabus & Rubric Parser.

Reads a PDF from the watch folder, extracts text with pdfplumber,
then uses spaCy + regex heuristics to pull out:
  • Course name / code
  • Instructor
  • Every deadline / deliverable + its date + weight
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pdfplumber
import spacy
from loguru import logger

# ── spaCy model (loaded once at import) ──────────────────────────────────────
try:
    _nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("spaCy model not found – run: python -m spacy download en_core_web_sm")
    _nlp = None

# ── Regex patterns ───────────────────────────────────────────────────────────
_DATE_PATTERNS = [
    # 12 March 2025 / March 12, 2025 / 12-03-2025 / 2025-03-12
    r"\b(\d{1,2}[\s\-/]\w+[\s\-/]\d{2,4})\b",
    r"\b(\w+\s+\d{1,2},?\s+\d{4})\b",
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
]

_WEIGHT_PATTERN = re.compile(r"(\d{1,3})\s*%")

_DEADLINE_KEYWORDS = re.compile(
    r"\b(assignment|homework|quiz|midterm|final\s+exam|project|submission|"
    r"presentation|lab|report|essay|deadline|due)\b",
    re.IGNORECASE,
)

_COURSE_CODE_PATTERN = re.compile(r"\b([A-Z]{2,6}\s*\d{3,4}[A-Z]?)\b")


@dataclass
class Deadline:
    title: str
    raw_date_str: str
    parsed_date: Optional[datetime]
    deadline_type: str = "assignment"
    weight_percent: Optional[float] = None
    description: str = ""


@dataclass
class ParsedSyllabus:
    course_name: str = "Unknown Course"
    course_code: str = ""
    instructor: str = ""
    semester: str = ""
    deadlines: list[Deadline] = field(default_factory=list)
    raw_text: str = ""


class PDFProcessor:
    """Extracts structured academic data from a syllabus / rubric PDF."""

    def __init__(self) -> None:
        self.nlp = _nlp

    # ── Public API ────────────────────────────────────────────────────────────

    def process(self, pdf_path: str | Path) -> ParsedSyllabus:
        """Main entry-point. Returns a ParsedSyllabus dataclass."""
        pdf_path = Path(pdf_path)
        logger.info(f"Processing PDF: {pdf_path.name}")

        raw_text = self._extract_text(pdf_path)
        result = ParsedSyllabus(raw_text=raw_text)
        result.course_name = self._extract_course_name(raw_text, pdf_path.stem)
        result.course_code = self._extract_course_code(raw_text)
        result.instructor = self._extract_instructor(raw_text)
        result.semester = self._extract_semester(raw_text)
        result.deadlines = self._extract_deadlines(raw_text)

        logger.success(
            f"Parsed '{result.course_name}' – found {len(result.deadlines)} deadlines."
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_text(self, pdf_path: Path) -> str:
        pages: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n".join(pages)

    def _extract_course_name(self, text: str, fallback: str) -> str:
        """Grab the first meaningful line from the PDF (usually the title)."""
        for line in text.splitlines():
            line = line.strip()
            if len(line) > 8 and not line.startswith("#"):
                return line
        return fallback.replace("_", " ").title()

    def _extract_course_code(self, text: str) -> str:
        match = _COURSE_CODE_PATTERN.search(text)
        return match.group(1).replace(" ", "") if match else ""

    def _extract_instructor(self, text: str) -> str:
        """Look for 'Instructor:' or 'Professor:' label."""
        match = re.search(
            r"(?:instructor|professor|lecturer|taught by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

        # Fallback: use spaCy NER to find a PERSON near the top
        if self.nlp:
            doc = self.nlp(text[:1000])
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    return ent.text
        return ""

    def _extract_semester(self, text: str) -> str:
        match = re.search(
            r"\b(Spring|Fall|Summer|Winter)\s+(\d{4})\b", text, re.IGNORECASE
        )
        return f"{match.group(1)} {match.group(2)}" if match else ""

    def _extract_deadlines(self, text: str) -> list[Deadline]:
        deadlines: list[Deadline] = []
        lines = text.splitlines()

        for line in lines:
            if not _DEADLINE_KEYWORDS.search(line):
                continue

            raw_date = self._find_date_in_line(line)
            if not raw_date:
                continue

            parsed_date = self._parse_date(raw_date)
            weight_match = _WEIGHT_PATTERN.search(line)
            dtype = self._classify_type(line)

            deadlines.append(
                Deadline(
                    title=line.strip()[:200],
                    raw_date_str=raw_date,
                    parsed_date=parsed_date,
                    deadline_type=dtype,
                    weight_percent=float(weight_match.group(1)) if weight_match else None,
                )
            )

        # Deduplicate by title
        seen: set[str] = set()
        unique: list[Deadline] = []
        for d in deadlines:
            key = d.title[:60].lower()
            if key not in seen:
                seen.add(key)
                unique.append(d)

        return unique

    def _find_date_in_line(self, line: str) -> str | None:
        for pattern in _DATE_PATTERNS:
            m = re.search(pattern, line)
            if m:
                return m.group(1)
        return None

    def _parse_date(self, raw: str) -> datetime | None:
        formats = [
            "%d %B %Y", "%B %d, %Y", "%B %d %Y",
            "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
            "%d-%m-%Y", "%d %b %Y", "%b %d, %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
        return None

    def _classify_type(self, line: str) -> str:
        line_lower = line.lower()
        if "quiz" in line_lower:
            return "quiz"
        if "exam" in line_lower or "midterm" in line_lower or "final" in line_lower:
            return "exam"
        if "project" in line_lower:
            return "project"
        if "presentation" in line_lower:
            return "presentation"
        if "lab" in line_lower:
            return "assignment"
        return "assignment"
