# 🎓 Academic Orchestrator
### 100% Free AI-Powered Academic Assistant for Linux

Runs on your own Linux server. Handles deadline tracking, research synthesis, code review, and team coordination — all autonomously.

**AI Engine: Google Gemini (free tier) | Zero paid APIs required**

---

## What It Does

| Phase | Feature | How |
|-------|---------|-----|
| 1 | Drop a syllabus PDF → deadlines auto-extracted & scheduled | pdfplumber + spaCy + cron |
| 1 | Discord/email reminders days before each deadline | discord.py + smtplib |
| 2 | Type a research query → GitHub repos + web articles + AI brief | Serper + PyGithub + Gemini |
| 2 | Web dashboard to view everything | Flask |
| 3 | Auto code review on GitHub PRs | pylint + bandit + Gemini |
| 3 | Scrum master monitors team, drafts nudge messages | PyGithub + Gemini |

---

## Project Structure

```
academic_orchestrator/
├── agents/
│   ├── researcher.py        # GitHub + web search + Gemini synthesis
│   ├── code_reviewer.py     # pylint + bandit + lizard + Gemini review
│   └── scrum_master.py      # GitHub monitoring + Gemini nudge messages
├── config/
│   ├── .env                 # ← Your API keys go here
│   ├── settings.yaml        # Preferences, timing, thresholds
│   └── database_schema.sql  # MySQL table definitions
├── core/
│   ├── pdf_processor.py     # Syllabus PDF → deadlines (spaCy + regex)
│   ├── scheduler.py         # Linux cron jobs + Discord/email dispatch
│   └── database_manager.py  # All MySQL operations
├── dashboard/
│   ├── app.py               # Flask REST API (10 endpoints)
│   ├── static/              # style.css + app.js
│   └── templates/           # 4 HTML pages (dark theme)
├── data/
│   ├── raw_syllabi/         # ← DROP YOUR PDF SYLLABI HERE
│   ├── research_notes/      # Agent-generated summaries
│   └── vector_db/           # ChromaDB for semantic search
├── scripts/
│   ├── setup_env.sh         # One-command installer
│   ├── watch_folder.sh      # Shell-based folder watcher (alternative)
│   ├── process_pdf.py       # Manual one-off PDF processor
│   └── send_reminder.py     # Called by cron jobs
├── logs/
├── main.py                  # Entry point
└── requirements.txt
```

---

## Completely Free API Keys

| Key | Where to get it | Free limit |
|-----|----------------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key | 1500 requests/day |
| `GITHUB_TOKEN` | GitHub → Settings → Developer Settings → PAT (classic) | Unlimited |
| `DISCORD_BOT_TOKEN` | [discord.com/developers](https://discord.com/developers/applications) → New App → Bot | Unlimited |
| `SERPER_API_KEY` | [serper.dev](https://serper.dev) → Sign up | 2500 searches/month |
| MySQL password | Local install — `sudo apt install mysql-server` | Unlimited (local) |
| Gmail app password | Google Account → Security → App Passwords | Unlimited |

---

## Setup (3 Steps)

### Step 1 — Install

```bash
git clone <your-repo-url>
cd academic_orchestrator
bash scripts/setup_env.sh
```

### Step 2 — Add Your Keys

Open `config/.env` and fill in these 6 values:

```env
GEMINI_API_KEY=AIza...          # from aistudio.google.com
GITHUB_TOKEN=ghp_...            # from github.com/settings/tokens
DISCORD_BOT_TOKEN=...           # from discord.com/developers
DISCORD_CHANNEL_ID=...          # right-click channel in Discord → Copy ID
SERPER_API_KEY=...              # from serper.dev
DB_PASSWORD=your_mysql_password
```

### Step 3 — Run

```bash
source .venv/bin/activate
python main.py
```

Dashboard → **http://localhost:5000**

---

## Usage

### Phase 1 — Automatic Deadline Tracking

Just copy any PDF into the watch folder:

```bash
cp ~/Downloads/CS301_Syllabus.pdf data/raw_syllabi/
```

The orchestrator instantly:
- Extracts course name, instructor, deadlines, types, and weights
- Saves everything to MySQL
- Creates cron jobs to remind you 7, 3, and 1 day before each deadline
- Sends you a Discord summary

### Phase 2 — AI Research (Gemini powered)

Via dashboard at `/research`, or:

```bash
python main.py --research "Dijkstra's algorithm implementation in C with priority queue"
```

Gets GitHub repos + web articles + a full Gemini-written research brief, saved and searchable.

### Phase 3 — Code Review

```bash
python main.py --review-pr 15
```

Runs pylint + bandit + complexity analysis, sends to Gemini for a structured review, posts a comment on the GitHub PR automatically.

### Phase 3 — Scrum Check

```bash
python main.py --sprint-check
```

Scans your repo for stale issues, inactive contributors, and Gemini drafts polite follow-up messages.

---

## Dashboard Pages

| Page | URL | What's there |
|------|-----|-------------|
| Deadlines | `/` | All upcoming deadlines, urgency colours, mark-done button |
| Research | `/research` | Query box, history, semantic search across past notes |
| Code Review | `/reviews` | Paste code or enter PR number, view past reviews |
| Scrum Board | `/scrum` | Team commits, stale issues, AI nudge messages |

---

## CLI Commands

```bash
python main.py                          # Full stack (all phases)
python main.py --phase 1               # Watchdog + notifications only
python main.py --phase 2               # + Research + Dashboard
python main.py --dashboard-only        # Just the Flask UI
python main.py --research "your query" # One-off research and exit
python main.py --review-pr 42          # One-off PR review and exit
python main.py --sprint-check          # One-off scrum report and exit
```

---

## Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| LLM | Google Gemini 1.5 Flash | **Free** |
| PDF parsing | pdfplumber | Free |
| NLP | spaCy en_core_web_sm | Free |
| Database | MySQL 8 (local) | Free |
| Vector store | ChromaDB + sentence-transformers | Free |
| Web search | Serper API | Free (2500/month) |
| GitHub | PyGithub | Free |
| Static analysis | pylint + bandit + lizard | Free |
| Notifications | discord.py + smtplib | Free |
| Cron | python-crontab | Free |
| File watching | watchdog | Free |
| Dashboard | Flask + Vanilla JS | Free |

**Total monthly cost: $0**
