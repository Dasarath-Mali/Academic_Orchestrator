#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Academic Orchestrator — One-Command Setup Script
#  Run: bash scripts/setup_env.sh
#  Everything installed is FREE and open source.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; CYAN="\033[36m"; RESET="\033[0m"
info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error() { echo -e "${RED}[ERROR]${RESET} $*"; exit 1; }
head()  { echo -e "\n${CYAN}── $* ──${RESET}"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   🎓 Academic Orchestrator Setup      ║"
echo "  ║      100% Free Stack  (Gemini AI)     ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${RESET}"

# ── Python check ──────────────────────────────────────────────────────────────
head "Checking Python"
if ! command -v python3 &>/dev/null; then
  error "Python 3.10+ is required. Install: sudo apt install python3"
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$(echo "$PY_VER" | cut -d. -f1)
MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [[ "$MAJOR" -lt 3 || ("$MAJOR" -eq 3 && "$MINOR" -lt 10) ]]; then
  error "Python 3.10+ required, found $PY_VER"
fi
info "Python $PY_VER ✓"

# ── Virtual environment ───────────────────────────────────────────────────────
head "Virtual Environment"
if [ ! -d ".venv" ]; then
  info "Creating .venv…"
  python3 -m venv .venv
fi
source .venv/bin/activate
info "Activated .venv ✓"

# ── Pip dependencies ──────────────────────────────────────────────────────────
head "Installing Python Packages"
pip install --upgrade pip -q
pip install -r requirements.txt -q
info "All packages installed ✓"

# ── spaCy language model ──────────────────────────────────────────────────────
head "Downloading spaCy Model"
python3 -m spacy download en_core_web_sm -q && info "spaCy model ready ✓" \
  || warn "spaCy model failed — run: python3 -m spacy download en_core_web_sm"

# ── Playwright (optional, for scraping) ───────────────────────────────────────
head "Playwright Browsers"
playwright install chromium --quiet && info "Playwright chromium ready ✓" \
  || warn "Playwright failed — skipping (not required for core features)"

# ── MySQL ─────────────────────────────────────────────────────────────────────
head "MySQL Setup"
if command -v mysql &>/dev/null; then
  if [ -f "config/.env" ]; then
    set -a; source config/.env; set +a
    mysql -h "${DB_HOST:-localhost}" \
          -u "${DB_USER:-root}" \
          -p"${DB_PASSWORD:-}" \
          "${DB_NAME:-academic_orchestrator}" \
          < config/database_schema.sql 2>/dev/null \
      && info "Database schema applied ✓" \
      || warn "Schema apply failed — run config/database_schema.sql manually in MySQL"
  else
    warn "config/.env missing — apply schema manually after filling in credentials"
  fi
else
  warn "MySQL not found. Install: sudo apt install mysql-server"
  warn "Then run: mysql -u root -p < config/database_schema.sql"
fi

# ── inotify-tools ─────────────────────────────────────────────────────────────
head "System Tools"
if command -v apt-get &>/dev/null; then
  sudo apt-get install -y inotify-tools -q 2>/dev/null \
    && info "inotify-tools installed ✓" \
    || warn "Could not install inotify-tools (optional — Python watchdog is used by default)"
fi

# ── Create directories ────────────────────────────────────────────────────────
head "Creating Directories"
mkdir -p data/{raw_syllabi,research_notes,vector_db} logs
info "Directories ready ✓"

# ── Make scripts executable ───────────────────────────────────────────────────
chmod +x scripts/*.sh
info "Scripts made executable ✓"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║  ✅ Setup Complete!                           ║${RESET}"
echo -e "${GREEN}╚═══════════════════════════════════════════════╝${RESET}"
echo ""
echo "  Next steps:"
echo ""
echo -e "  1. ${CYAN}nano config/.env${RESET}  ← Add your 6 free API keys"
echo ""
echo "     GEMINI_API_KEY  → aistudio.google.com (free)"
echo "     GITHUB_TOKEN    → github.com/settings/tokens (free)"
echo "     DISCORD_BOT_TOKEN / DISCORD_CHANNEL_ID  → discord.com/developers (free)"
echo "     SERPER_API_KEY  → serper.dev (free, 2500/mo)"
echo "     DB_PASSWORD     → your local MySQL password"
echo ""
echo -e "  2. ${CYAN}source .venv/bin/activate${RESET}"
echo -e "  3. ${CYAN}python main.py${RESET}"
echo ""
echo "  Then open http://localhost:5000 in your browser"
echo "  and drop a PDF into data/raw_syllabi/"
echo ""
