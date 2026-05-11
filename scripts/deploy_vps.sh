#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/finance-report-agents}"
SCREEN_NAME="${SCREEN_NAME:-finance_report_bot}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$APP_DIR"

echo "==> Pull latest code"
git pull --ff-only

echo "==> Ensure virtualenv"
if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

echo "==> Install dependencies"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "==> Check .env"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Fill secrets before starting the bot."
  exit 1
fi

echo "==> Restart bot"
if screen -list | grep -q "\\.${SCREEN_NAME}[[:space:]]"; then
  screen -S "$SCREEN_NAME" -X quit || true
  sleep 2
fi

mkdir -p logs
screen -dmS "$SCREEN_NAME" .venv/bin/python -m finance_agent.telegram_bot

echo "==> Bot status"
screen -ls
echo "Deploy complete."
