# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — Logger
# ══════════════════════════════════════════════════════════════════════════════

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from core.constants import LOG_DIR


# ─── ANSI color codes ─────────────────────────────────────────────────────────
class _Colors:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    YELLOW  = "\033[93m"
    GREEN   = "\033[92m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    GREY    = "\033[90m"
    WHITE   = "\033[97m"


_LEVEL_COLORS = {
    logging.DEBUG:    _Colors.GREY,
    logging.INFO:     _Colors.CYAN,
    logging.WARNING:  _Colors.YELLOW,
    logging.ERROR:    _Colors.RED,
    logging.CRITICAL: _Colors.RED + _Colors.BOLD,
}


class _ColoredFormatter(logging.Formatter):
    """Console formatter with ANSI colors and emoji prefixes."""

    _PREFIX = {
        logging.DEBUG:    "🔍",
        logging.INFO:     "ℹ️ ",
        logging.WARNING:  "⚠️ ",
        logging.ERROR:    "❌",
        logging.CRITICAL: "💥",
    }

    def format(self, record: logging.LogRecord) -> str:
        color  = _LEVEL_COLORS.get(record.levelno, _Colors.WHITE)
        prefix = self._PREFIX.get(record.levelno, "  ")
        ts     = self.formatTime(record, "%H:%M:%S")

        name_short = record.name.split(".")[-1][:16].ljust(16)

        msg = super().format(record)
        # strip the default formatting parts we re-add manually
        msg = record.getMessage()

        line = (
            f"{_Colors.GREY}{ts}{_Colors.RESET} "
            f"{color}{prefix} {record.levelname:<8}{_Colors.RESET} "
            f"{_Colors.BLUE}[{name_short}]{_Colors.RESET} "
            f"{color}{msg}{_Colors.RESET}"
        )
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class _PlainFormatter(logging.Formatter):
    """Plain formatter for file output."""
    _FMT = "%(asctime)s | %(levelname)-8s | %(name)-24s | %(message)s"
    _DATE = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self._FMT, datefmt=self._DATE)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure rotating file handlers + colorised console handler.
    Returns the root 'intentbot' logger.
    """
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("intentbot")
    root.setLevel(level)

    if root.handlers:          # already configured (hot-reload guard)
        return root

    # ── Console handler ───────────────────────────────────────────────────────
    console_h = logging.StreamHandler(sys.stdout)
    console_h.setLevel(level)
    console_h.setFormatter(_ColoredFormatter())
    root.addHandler(console_h)

    # ── Main rotating log ─────────────────────────────────────────────────────
    main_h = logging.handlers.RotatingFileHandler(
        filename=os.path.join(LOG_DIR, "intentbot.log"),
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=7,
        encoding="utf-8",
    )
    main_h.setLevel(logging.DEBUG)
    main_h.setFormatter(_PlainFormatter())
    root.addHandler(main_h)

    # ── Error-only rotating log ───────────────────────────────────────────────
    error_h = logging.handlers.RotatingFileHandler(
        filename=os.path.join(LOG_DIR, "errors.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_h.setLevel(logging.ERROR)
    error_h.setFormatter(_PlainFormatter())
    root.addHandler(error_h)

    # ── Silence noisy third-party loggers ────────────────────────────────────
    for noisy in ("discord", "discord.http", "discord.gateway", "aiosqlite", "aiohttp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return root


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'intentbot' namespace."""
    return logging.getLogger(f"intentbot.{name}")
