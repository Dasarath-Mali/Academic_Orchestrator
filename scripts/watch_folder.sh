#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Academic Orchestrator — Folder Watcher (inotifywait fallback)
#  Use this if you prefer a shell-based watcher instead of the Python watchdog.
#  Run: bash scripts/watch_folder.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WATCH_DIR="$ROOT_DIR/data/raw_syllabi"
VENV="$ROOT_DIR/.venv/bin/python3"
PROCESSOR="$ROOT_DIR/scripts/process_pdf.py"
LOG="$ROOT_DIR/logs/watcher.log"

mkdir -p "$WATCH_DIR" "$ROOT_DIR/logs"

echo "[$(date '+%H:%M:%S')] 👁  Watching: $WATCH_DIR" | tee -a "$LOG"

if ! command -v inotifywait &>/dev/null; then
  echo "[ERROR] inotifywait not found. Install: sudo apt-get install inotify-tools" | tee -a "$LOG"
  exit 1
fi

inotifywait -m -e close_write,moved_to --format '%w%f' "$WATCH_DIR" | while read -r FILEPATH; do
  EXT="${FILEPATH##*.}"
  if [[ "${EXT,,}" == "pdf" ]]; then
    echo "[$(date '+%H:%M:%S')] 📄 New PDF: $FILEPATH" | tee -a "$LOG"
    "$VENV" "$PROCESSOR" --file "$FILEPATH" >> "$LOG" 2>&1 &
  fi
done
