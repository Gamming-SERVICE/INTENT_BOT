# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — Bot Config
#
# This file contains ONLY bot-level settings (token, owner IDs, etc.).
# ALL guild/server settings are stored per-guild in the database.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env file if present (before any os.getenv calls)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass   # python-dotenv not installed — rely on real env vars


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"❌  Required environment variable {name!r} is not set.")
        print("    Copy .env.example to .env and fill in your values.")
        sys.exit(1)
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _int_list(name: str) -> list[int]:
    raw = os.getenv(name, "")
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


# ─── Required ─────────────────────────────────────────────────────────────────
TOKEN: str = _require("DISCORD_TOKEN")

# ─── Optional ─────────────────────────────────────────────────────────────────
OWNER_IDS: list[int] = _int_list("OWNER_IDS")
DEFAULT_PREFIX: str = _optional("DEFAULT_PREFIX", "!")

# ─── Lavalink / Music ─────────────────────────────────────────────────────────
LAVALINK_URI: str      = _optional("LAVALINK_URI",      "http://localhost:2333")
LAVALINK_PASSWORD: str = _optional("LAVALINK_PASSWORD", "youshallnotpass")

# ─── Update endpoint ──────────────────────────────────────────────────────────
UPDATE_CHECK_URL: str = _optional("UPDATE_CHECK_URL", "https://update.bot.int.yt")

# ─── Debug ────────────────────────────────────────────────────────────────────
DEBUG: bool = _optional("DEBUG", "false").lower() in ("1", "true", "yes")
