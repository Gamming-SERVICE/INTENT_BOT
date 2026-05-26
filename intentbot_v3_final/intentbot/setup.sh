#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — setup.sh
# One-command setup for Ubuntu/Debian VPS.
# Usage:  chmod +x setup.sh && ./setup.sh
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Check OS ──────────────────────────────────────────────────────────────────
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    warn "This script is designed for Linux. On macOS/Windows, use Docker instead."
fi

# ── Python version check ──────────────────────────────────────────────────────
info "Checking Python version…"
PYTHON=$(command -v python3.11 || command -v python3 || echo "")
if [[ -z "$PYTHON" ]]; then
    error "Python 3.11+ is required. Install it first."
fi
PY_VER=$($PYTHON --version 2>&1 | awk '{print $2}')
info "Found Python $PY_VER"

# ── System packages ───────────────────────────────────────────────────────────
info "Installing system packages…"
if command -v apt-get &>/dev/null; then
    sudo apt-get update -q
    sudo apt-get install -y -q python3-pip python3-venv ffmpeg libsodium-dev git
    ok "System packages installed"
else
    warn "apt-get not found — skipping system package install. Install ffmpeg and libsodium-dev manually."
fi

# ── Virtual environment ───────────────────────────────────────────────────────
info "Creating Python virtual environment…"
if [[ ! -d "venv" ]]; then
    $PYTHON -m venv venv
    ok "Virtual environment created at ./venv"
else
    ok "Virtual environment already exists"
fi

source venv/bin/activate

# ── Python packages ───────────────────────────────────────────────────────────
info "Installing Python packages…"
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Python packages installed"

# ── Environment file ──────────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
    cp .env.example .env
    warn ".env created from .env.example"
    warn "IMPORTANT: Edit .env and add your DISCORD_TOKEN before starting!"
else
    ok ".env already exists"
fi

# ── Directories ───────────────────────────────────────────────────────────────
mkdir -p data/backups logs
ok "Runtime directories ready"

# ── Systemd service ───────────────────────────────────────────────────────────
BOT_DIR=$(pwd)
BOT_USER=$(whoami)

info "Installing systemd service…"
SERVICE_FILE="/etc/systemd/system/intentbot.service"
sudo tee "$SERVICE_FILE" > /dev/null << SERVICE
[Unit]
Description=Intent BOT v3.0
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$BOT_USER
WorkingDirectory=$BOT_DIR
ExecStart=$BOT_DIR/venv/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable intentbot
ok "Systemd service installed and enabled"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  Intent™ BOT v3.0 Setup Complete! ✅${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit .env and set your DISCORD_TOKEN"
echo "  2. Start the bot:   sudo systemctl start intentbot"
echo "  3. View logs:       sudo journalctl -u intentbot -f"
echo "  OR run directly:    ./start.sh"
echo ""
