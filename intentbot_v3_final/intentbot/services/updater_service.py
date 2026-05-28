# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Auto-Updater Service
#
# Checks UPDATE_CHECK_URL every hour for a new version.
# Expected page format (plain text anywhere in the HTML body):
#   version=3.0.1
#   zip=https://github.com/example/repo/archive/main.zip
#
# What is preserved during update (never overwritten):
#   data/database.db  |  data/backups/  |  .env  |  logs/  |  config.py
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import aiohttp

from core.constants import BOT_VERSION, BACKUP_DIR
from core.logger import get_logger

log = get_logger("updater")

# Load UPDATE_CHECK_URL from config (has fallback)
try:
    from config import UPDATE_CHECK_URL as _CFG_URL
    UPDATE_CHECK_URL: str = _CFG_URL
except Exception:
    UPDATE_CHECK_URL = "https://update.bot.int.yt"

_CHECK_INTERVAL = 3600  # 1 hour

# Files / folders that must NEVER be touched during an update
_PRESERVE = frozenset([
    "data/database.db",
    "data/backups",
    ".env",
    "logs",
    "config.py",
])


def _parse_update_page(html: str) -> tuple[str | None, str | None]:
    """Extract version= and zip= from the update server response body."""
    version_match = re.search(r"version=([0-9]+\.[0-9]+\.[0-9]+)", html)
    zip_match     = re.search(r"zip=(https?://[^\s<\"'\r\n]+)", html)
    version = version_match.group(1) if version_match else None
    zip_url = zip_match.group(1).strip()  if zip_match     else None
    return version, zip_url


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _backup_current(root: Path) -> Path:
    """Create a timestamped ZIP of current bot files, excluding data/logs."""
    backup_dir = root / BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp       = time.strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"pre_update_{stamp}.zip"

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in root.rglob("*"):
            rel = item.relative_to(root)
            parts = rel.parts
            if not parts:
                continue
            # Skip data dir, logs, cache dirs, git
            if parts[0] in ("data", "logs", "__pycache__", ".git", "venv", ".venv"):
                continue
            if item.suffix in (".pyc", ".pyo"):
                continue
            if item.is_file():
                zf.write(item, rel)

    log.info("Backup created: %s (%.1f KB)", backup_path, backup_path.stat().st_size / 1024)
    return backup_path


def _apply_update(root: Path, zip_path: Path) -> None:
    """
    Extract update ZIP into the bot directory.
    - Strips the top-level GitHub folder prefix automatically.
    - Skips all preserved paths.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

        # GitHub archives wrap everything in a top-level "repo-main/" folder
        # Detect it: find the common prefix of all paths
        top_dirs = set()
        for n in names:
            if "/" in n:
                top_dirs.add(n.split("/")[0])
        strip_prefix = (top_dirs.pop() + "/") if len(top_dirs) == 1 else ""

        for member in names:
            if member.endswith("/"):
                continue  # skip directory entries

            # Strip the repo wrapper folder
            rel = member[len(strip_prefix):] if strip_prefix and member.startswith(strip_prefix) else member
            if not rel:
                continue

            # Skip preserved files
            should_preserve = any(
                rel == p or rel.startswith(p.rstrip("/") + "/")
                for p in _PRESERVE
            )
            if should_preserve:
                log.debug("Preserving: %s", rel)
                continue

            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)

    log.info("Update files extracted successfully")


async def check_for_update(session: aiohttp.ClientSession, root: Path) -> None:
    """Perform a single update check cycle."""
    if not UPDATE_CHECK_URL or not UPDATE_CHECK_URL.startswith("http"):
        log.debug("No valid UPDATE_CHECK_URL configured — skipping update check")
        return

    log.info("Checking for updates at %s …", UPDATE_CHECK_URL)

    try:
        async with session.get(
            UPDATE_CHECK_URL,
            timeout=aiohttp.ClientTimeout(total=15),
            allow_redirects=True,
        ) as resp:
            if resp.status != 200:
                log.warning("Update server returned HTTP %d — skipping", resp.status)
                return
            html = await resp.text()
    except asyncio.TimeoutError:
        log.warning("Update check timed out — skipping")
        return
    except Exception as e:
        log.warning("Could not reach update server: %s", e)
        return

    remote_version, zip_url = _parse_update_page(html)

    if not remote_version:
        log.debug("Could not parse version from update server response — skipping")
        return

    log.info("Current: v%s | Remote: v%s", BOT_VERSION, remote_version)

    if _version_tuple(remote_version) <= _version_tuple(BOT_VERSION):
        log.info("✅ Already on the latest version (v%s)", BOT_VERSION)
        return

    if not zip_url:
        log.warning("New version v%s found but no ZIP URL in update page — skipping", remote_version)
        return

    log.info("🔔 New version v%s available — downloading from %s …", remote_version, zip_url)

    # Download the ZIP into a temp file
    tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".zip")
    tmp_path = Path(tmp_path_str)
    os.close(tmp_fd)

    try:
        async with session.get(
            zip_url,
            timeout=aiohttp.ClientTimeout(total=180),   # 3 min download timeout
            allow_redirects=True,
        ) as resp:
            if resp.status != 200:
                log.error("Failed to download update ZIP (HTTP %d) — aborting", resp.status)
                return

            # Validate Content-Type hint
            ctype = resp.headers.get("Content-Type", "")
            # Write in chunks to avoid memory spikes
            with open(tmp_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)

    except asyncio.TimeoutError:
        log.error("Download timed out — aborting update")
        tmp_path.unlink(missing_ok=True)
        return
    except Exception as e:
        log.error("Failed to download update ZIP: %s — aborting", e)
        tmp_path.unlink(missing_ok=True)
        return

    # Validate the downloaded file is actually a ZIP
    if tmp_path.stat().st_size < 100:
        log.error("Downloaded file is too small (%d bytes) — likely an error page, aborting", tmp_path.stat().st_size)
        tmp_path.unlink(missing_ok=True)
        return

    if not zipfile.is_zipfile(tmp_path):
        log.error("Downloaded file is not a valid ZIP archive — aborting update")
        tmp_path.unlink(missing_ok=True)
        return

    log.info("Downloaded %s (%.1f KB)", tmp_path.name, tmp_path.stat().st_size / 1024)

    # Backup current installation before touching anything
    try:
        _backup_current(root)
    except Exception as e:
        log.error("Backup failed: %s — aborting update to keep bot safe", e)
        tmp_path.unlink(missing_ok=True)
        return

    # Apply the update
    try:
        _apply_update(root, tmp_path)
    except Exception as e:
        log.error("Update extraction failed: %s — check backup in data/backups/", e)
        tmp_path.unlink(missing_ok=True)
        return
    finally:
        tmp_path.unlink(missing_ok=True)

    log.info("✅ Update to v%s applied successfully — restarting in 3 seconds …", remote_version)
    await asyncio.sleep(3)

    # Replace the running process with a fresh Python invocation
    os.execv(sys.executable, [sys.executable] + sys.argv)


class UpdaterService:
    """
    Background hourly update checker.

    Usage:
        updater = UpdaterService()
        updater.start()   # call once from setup_hook
        await updater.stop()  # call in bot.close()
    """

    def __init__(self) -> None:
        self._root:    Path = Path(__file__).parent.parent.resolve()
        self._session: aiohttp.ClientSession | None = None
        self._task:    asyncio.Task | None = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="updater")
        log.info("Auto-updater started (interval: %ds, URL: %s)", _CHECK_INTERVAL, UPDATE_CHECK_URL)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()
        log.info("Auto-updater stopped")

    async def _loop(self) -> None:
        # Wait 90 seconds after startup before the first check
        await asyncio.sleep(90)

        self._session = aiohttp.ClientSession(
            headers={
                "User-Agent": f"IntentBOT/{BOT_VERSION} (+https://github.com/intentbot)",
            }
        )

        while True:
            try:
                await check_for_update(self._session, self._root)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.exception("Unexpected error in updater loop: %s", e)
            await asyncio.sleep(_CHECK_INTERVAL)


# Module-level singleton — imported by main.py
updater = UpdaterService()
