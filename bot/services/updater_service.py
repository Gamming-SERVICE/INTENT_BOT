# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Auto-Updater Service
#
# Checks https://update.bot.int.yt every hour.
# Parses version= and zip= from the page body.
# Downloads, backs up, extracts, preserves database/config/logs, restarts.
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

from core.constants import BOT_VERSION, UPDATE_CHECK_URL, BACKUP_DIR
from core.logger import get_logger
from core.scheduler import scheduler

log = get_logger("updater")

# Files / folders that must NEVER be touched during an update
_PRESERVE = {
    "data/database.db",
    "data/backups",
    ".env",
    "logs",
    "config.py",     # runtime config kept
}

_CHECK_INTERVAL = 3600   # 1 hour


def _parse_update_page(html: str) -> tuple[str | None, str | None]:
    """Extract version= and zip= from the update server's HTML."""
    version_match = re.search(r"version=([0-9]+\.[0-9]+\.[0-9]+)", html)
    zip_match     = re.search(r"zip=(https?://[^\s<\"']+)", html)
    version = version_match.group(1) if version_match else None
    zip_url = zip_match.group(1)     if zip_match     else None
    return version, zip_url


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def _backup_current(root: Path) -> Path:
    """Create a timestamped ZIP backup of the current bot files."""
    backup_dir = root / BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp       = time.strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"backup_{stamp}.zip"
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in root.rglob("*"):
            # Skip data dir, logs, __pycache__, and the backup dir itself
            rel = item.relative_to(root)
            parts = rel.parts
            if parts and parts[0] in ("data", "logs", "__pycache__", ".git"):
                continue
            if item.suffix == ".pyc":
                continue
            if item.is_file():
                zf.write(item, rel)
    log.info("Backup created: %s", backup_path)
    return backup_path


def _apply_update(root: Path, zip_path: Path) -> None:
    """Extract update ZIP into the bot directory, skipping preserved files."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        # GitHub ZIPs have a top-level folder — detect and strip it
        top_level_dirs = {n.split("/")[0] for n in names if "/" in n}
        strip_prefix   = top_level_dirs.pop() + "/" if len(top_level_dirs) == 1 else ""

        for member in names:
            if member.endswith("/"):
                continue
            # Strip top-level GitHub folder prefix
            rel = member[len(strip_prefix):] if strip_prefix and member.startswith(strip_prefix) else member
            if not rel:
                continue
            # Check against preserved files
            if any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in _PRESERVE):
                log.debug("Skipping preserved file: %s", rel)
                continue
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            log.debug("Updated: %s", rel)


async def check_for_update(session: aiohttp.ClientSession, root: Path) -> None:
    log.info("Checking for updates at %s …", UPDATE_CHECK_URL)
    try:
        async with session.get(UPDATE_CHECK_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                log.warning("Update server returned HTTP %d", resp.status)
                return
            html = await resp.text()
    except Exception as e:
        log.warning("Could not reach update server: %s", e)
        return

    remote_version, zip_url = _parse_update_page(html)
    if not remote_version:
        log.warning("Could not parse version from update server")
        return

    log.info("Current: v%s | Remote: v%s", BOT_VERSION, remote_version)

    if _version_tuple(remote_version) <= _version_tuple(BOT_VERSION):
        log.info("✅ Already on the latest version (v%s)", BOT_VERSION)
        return

    if not zip_url:
        log.warning("New version found but no ZIP URL provided")
        return

    log.info("🔔 New version v%s available — starting update …", remote_version)

    # Download ZIP
    try:
        async with session.get(zip_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                log.error("Failed to download update ZIP (HTTP %d)", resp.status)
                return
            zip_data = await resp.read()
    except Exception as e:
        log.error("Failed to download update: %s", e)
        return

    # Validate ZIP
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp.write(zip_data)
        tmp_path = Path(tmp.name)

    if not zipfile.is_zipfile(tmp_path):
        log.error("Downloaded file is not a valid ZIP — aborting update")
        tmp_path.unlink(missing_ok=True)
        return

    # Backup current installation
    try:
        _backup_current(root)
    except Exception as e:
        log.error("Backup failed — aborting update: %s", e)
        tmp_path.unlink(missing_ok=True)
        return

    # Apply update
    try:
        _apply_update(root, tmp_path)
    except Exception as e:
        log.error("Update extraction failed: %s — check backup and restore manually", e)
        tmp_path.unlink(missing_ok=True)
        return
    finally:
        tmp_path.unlink(missing_ok=True)

    log.info("✅ Update to v%s applied successfully — restarting …", remote_version)
    await asyncio.sleep(2)
    # Restart: replace current process with a fresh Python invocation
    os.execv(sys.executable, [sys.executable] + sys.argv)


class UpdaterService:
    """
    Background update checker.  Call `start()` once on bot startup.
    Keeps a single aiohttp.ClientSession for the lifetime of the process.
    """

    def __init__(self) -> None:
        self._root    = Path(__file__).parent.parent.resolve()
        self._session: aiohttp.ClientSession | None = None
        self._task:    asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="updater")
        log.info("Auto-updater started (check every %ds)", _CHECK_INTERVAL)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._session:
            await self._session.close()

    async def _loop(self) -> None:
        await asyncio.sleep(60)   # Wait 1 minute after startup before first check
        self._session = aiohttp.ClientSession(headers={"User-Agent": f"IntentBOT/{BOT_VERSION}"})
        while True:
            try:
                await check_for_update(self._session, self._root)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.exception("Unexpected error in updater: %s", e)
            await asyncio.sleep(_CHECK_INTERVAL)


updater = UpdaterService()
