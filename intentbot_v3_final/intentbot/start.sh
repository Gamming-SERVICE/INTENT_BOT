#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — start.sh
# Direct run script (without systemd).
# Usage:  ./start.sh
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

if [[ ! -f ".env" ]]; then
    echo "ERROR: .env not found. Run ./setup.sh first or copy .env.example to .env"
    exit 1
fi

if [[ -d "venv" ]]; then
    source venv/bin/activate
    echo "[Intent BOT] Starting with virtual environment…"
else
    echo "[Intent BOT] Starting without virtual environment…"
fi

exec python main.py
