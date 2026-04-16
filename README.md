# 🎓 Academic Orchestrator
### 100% Free AI-Powered Academic Assistant

Runs on **Linux, Windows, and Mac**. Handles deadline tracking, research synthesis, code review, and team coordination — all autonomously using Google Gemini (free).

---

## Platform Support

| Feature | Linux | Windows | Mac |
|---------|-------|---------|-----|
| Flask Dashboard | ✅ | ✅ | ✅ |
| PDF Syllabus Parser | ✅ | ✅ | ✅ |
| Gemini Research Agent | ✅ | ✅ | ✅ |
| Code Reviewer | ✅ | ✅ | ✅ |
| Scrum Master Agent | ✅ | ✅ | ✅ |
| Discord Notifications | ✅ | ✅ | ✅ |
| MySQL Database | ✅ | ✅ | ✅ |
| Folder Watcher (watchdog) | ✅ | ✅ | ✅ |
| Linux Cron Job Reminders | ✅ | ❌ | ❌ |
| Daily Digest Scheduler | ✅ | ✅ | ✅ |

> **Note:** Cron jobs are Linux-only. On Windows/Mac, deadline reminders still fire through the built-in Python `schedule` library at your configured `morning_digest_time`.

---

## Project Structure

```
academic_orchestrator/
├── agents/
│   ├── researcher.py        # GitHub + Serper web search + Gemini synthesis
│   ├── code_reviewer.py     # pylint + bandit + lizard + Gemini review
│   └── scrum_master.py      # GitHub monitoring + Gemini nudge messages
├── config/
│   ├── .env                 # ← Your API keys go here
│   ├── settings.yaml        # Preferences, timing, thresholds
│   └── database_schema.sql  # MySQL table definitions
├── core/
│   ├── pdf_processor.py     # Syllabus PDF → deadlines (spaCy + regex)
│   ├── scheduler.py         # Cron (Linux) + schedule library + notifications
│   └── database_manager.py  # All MySQL operations
├── dashboard/
│   ├── app.py               # Flask app + REST API (10 endpoints)
│   ├── static/              # style.css + app.js
│   └── templates/           # 4 HTML pages (dark theme)
├── data/
│   ├── raw_syllabi/         # ← DROP YOUR PDF SYLLABI HERE
│   ├── research_notes/      # Agent-generated summaries
│   └── vector_db/           # ChromaDB for semantic search
├── scripts/
│   ├── setup_env.sh         # Linux/Mac one-command installer
│   ├── watch_folder.sh      # Linux shell watcher (alternative)
│   ├── process_pdf.py       # Manual one-off PDF processor
│   └── send_reminder.py     # Called by cron jobs (Linux only)
├── logs/
├── Procfile                 # Render.com deployment
├── render.yaml              # Render.com auto-deploy config
├── main.py                  # Entry point
└── requirements.txt
```

---

## Free API Keys You Need

| Key | Where to get it | Free limit |
|-----|----------------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key | 1500 requests/day |
| `GITHUB_TOKEN` | GitHub → Settings → Developer Settings → Personal Access Tokens (classic) | Unlimited |
| `DISCORD_BOT_TOKEN` | [discord.com/developers](https://discord.com/developers/applications) → New App → Bot | Unlimited |
| `DISCORD_CHANNEL_ID` | Discord → Settings → Advanced → Enable Developer Mode → right-click channel → Copy ID | — |
| `SERPER_API_KEY` | [serper.dev](https://serper.dev) → Sign up | 2500 searches/month |
| `DB_PASSWORD` | Your local MySQL install | Unlimited (local) |

---

## Setup — Linux 🐧

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv mysql-server inotify-tools git
```

### 2. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/academic_orchestrator.git
cd academic_orchestrator
bash scripts/setup_env.sh
```

The setup script automatically:
- Creates a Python virtual environment
- Installs all pip packages
- Downloads the spaCy language model
- Installs Playwright browser
- Sets up the MySQL database schema
- Creates all required directories

### 3. Configure MySQL

```bash
sudo mysql_secure_installation   # set a root password when prompted

sudo mysql -u root -p
```

Inside MySQL shell:

```sql
CREATE DATABASE academic_orchestrator;
CREATE USER 'orchestrator_user'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON academic_orchestrator.* TO 'orchestrator_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

-- Apply schema
mysql -u orchestrator_user -p academic_orchestrator < config/database_schema.sql
```

### 4. Add your API keys

```bash
nano config/.env
```

Fill in all 6 keys (see table above).

### 5. Run

```bash
source .venv/bin/activate
python main.py                    # Full stack (all phases)
python main.py --dashboard-only   # Just the web UI
python main.py --phase 1          # Watchdog + notifications only
```

Dashboard → **http://localhost:5000**

---

## Setup — Windows 🪟

### 1. Install prerequisites

- **Python 3.10+** → [python.org/downloads](https://python.org/downloads) — tick *"Add Python to PATH"* during install
- **MySQL 8.0** → [dev.mysql.com/downloads/installer](https://dev.mysql.com/downloads/installer) — choose "MySQL Server" during install, set a root password
- **Git** → [git-scm.com](https://git-scm.com)

### 2. Clone the repo

Open **Command Prompt** or **PowerShell**:

```cmd
git clone https://github.com/YOUR_USERNAME/academic_orchestrator.git
cd academic_orchestrator
```

### 3. Create virtual environment and install packages

```cmd
python -m venv .venv
.venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 4. Set up MySQL

Open **MySQL Command Line Client** (installed with MySQL) and run:

```sql
CREATE DATABASE academic_orchestrator;
CREATE USER 'orchestrator_user'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON academic_orchestrator.* TO 'orchestrator_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Then apply the schema. In Command Prompt:

```cmd
mysql -u orchestrator_user -p academic_orchestrator < config\database_schema.sql
```

### 5. Add your API keys

Open `config\.env` in Notepad or VS Code and fill in all 6 keys.

```cmd
notepad config\.env
```

### 6. Run

```cmd
.venv\Scripts\activate
python main.py --dashboard-only
```

Dashboard → **http://localhost:5000**

> **Note for Windows users:** Cron-based reminders are not available. Deadline reminders will fire through the daily digest at your configured `morning_digest_time` in `settings.yaml`. Everything else works identically.

---

## Setup — Mac 🍎

### 1. Install prerequisites

Install **Homebrew** if you don't have it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install dependencies:

```bash
brew install python@3.11 mysql git
brew services start mysql
```

### 2. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/academic_orchestrator.git
cd academic_orchestrator

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
python3 -m spacy download en_core_web_sm
```

### 3. Set up MySQL

```bash
mysql_secure_installation   # follow the prompts, set a root password

mysql -u root -p
```

Inside MySQL shell:

```sql
CREATE DATABASE academic_orchestrator;
CREATE USER 'orchestrator_user'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON academic_orchestrator.* TO 'orchestrator_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Apply the schema:

```bash
mysql -u orchestrator_user -p academic_orchestrator < config/database_schema.sql
```

### 4. Add your API keys

```bash
nano config/.env    # or open in VS Code: code config/.env
```

Fill in all 6 keys.

### 5. Run

```bash
source .venv/bin/activate
python main.py --dashboard-only
```

Dashboard → **http://localhost:5000**

> **Note for Mac users:** Cron-based reminders are Linux-only. Deadline reminders fire through the daily digest scheduler instead. Everything else works identically.

---

## Usage Guide

### Phase 1 — Automatic Deadline Tracking

Drop any syllabus PDF into the watch folder:

```bash
# Linux / Mac
cp ~/Downloads/CS301_Syllabus.pdf data/raw_syllabi/

# Windows
copy C:\Users\YourName\Downloads\CS301_Syllabus.pdf data\raw_syllabi\
```

The orchestrator instantly:
- Extracts course name, instructor, all deadlines, types, and weights
- Saves everything to MySQL
- Schedules reminders (cron on Linux, daily digest on Windows/Mac)
- Sends a Discord summary notification

### Phase 2 — AI Research

Via dashboard at `/research`, or CLI:

```bash
python main.py --research "Dijkstra algorithm in C with priority queue"
```

Returns GitHub repos + web articles + a Gemini-written research brief saved to MySQL and ChromaDB.

### Phase 3 — Code Review

```bash
python main.py --review-pr 15
```

Runs pylint + bandit + complexity analysis, generates a Gemini review, and posts it as a GitHub PR comment.

### Phase 3 — Scrum Check

```bash
python main.py --sprint-check
```

Finds stale issues, inactive contributors, and drafts polite nudge messages via Gemini.

---

## Dashboard Pages

| Page | URL | What's there |
|------|-----|-------------|
| Deadlines | `/` | Upcoming deadlines, urgency colours, mark-done |
| Research | `/research` | Query box, history, semantic search |
| Code Review | `/reviews` | Paste code or trigger PR review |
| Scrum Board | `/scrum` | Team commits, stale issues, nudge messages |

---

## CLI Reference

```bash
python main.py                           # Full stack
python main.py --phase 1                 # Watchdog + notifications only
python main.py --phase 2                 # + Research + Dashboard
python main.py --dashboard-only          # Just the web UI
python main.py --research "your query"   # One-off research
python main.py --review-pr 42            # One-off PR review
python main.py --sprint-check            # One-off scrum report
```

---

## Cloud Deployment (Render — Free)

To run 24/7 on the internet for free:

1. Push your repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → connect your repo
3. Set build command: `pip install -r requirements.txt && python -m spacy download en_core_web_sm`
4. Set start command: `gunicorn dashboard.app:app --bind 0.0.0.0:$PORT`
5. Add all your API keys under the **Environment** tab
6. For MySQL, use [railway.app](https://railway.app) free tier → create a MySQL service → copy connection details

Your app will be live at `https://your-app.onrender.com`

---

## Tech Stack — All Free

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 1.5 Flash |
| PDF parsing | pdfplumber |
| NLP | spaCy en_core_web_sm |
| Database | MySQL 8 |
| Vector store | ChromaDB + sentence-transformers |
| Web search | Serper API |
| GitHub | PyGithub |
| Static analysis | pylint + bandit + lizard |
| Notifications | discord.py + smtplib |
| Scheduler | python-crontab (Linux) + schedule |
| File watching | watchdog (cross-platform) |
| Dashboard | Flask + Vanilla JS |
| Logging | loguru |

**Total monthly cost: $0**