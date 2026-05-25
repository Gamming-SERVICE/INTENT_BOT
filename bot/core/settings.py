# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Per-Guild Settings Manager
# ══════════════════════════════════════════════════════════════════════════════
# BUG FIX: classmethod renamed from `get` → `fetch` to prevent Python's
# descriptor resolution from silently preferring the instance method `get()`
# over the classmethod, which caused the runtime error:
#   "GuildSettings.get() missing 1 required positional argument: 'key'"
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import json
from typing import Any

from core.constants import DEFAULT_GUILD_SETTINGS
from core.database import db
from core.logger import get_logger

log = get_logger("settings")


class GuildSettings:
    """
    Per-guild settings backed by SQLite.

    Usage:
        gs = await GuildSettings.fetch(guild_id)   # ← always use fetch()
        gs.prefix           # property shortcut
        gs.get("key")       # dict-style instance access
        await gs.set("key", value)
    """

    _cache: dict[int, "GuildSettings"] = {}
    _cache_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, guild_id: int, data: dict[str, Any]) -> None:
        self._guild_id = guild_id
        self._data: dict[str, Any] = data

    # ── Factory ───────────────────────────────────────────────────────────────
    #  Named `fetch` (not `get`) to avoid shadowing the instance method get().

    @classmethod
    async def fetch(cls, guild_id: int) -> "GuildSettings":
        """Load settings for a guild, using in-process cache."""
        async with cls._cache_lock:
            if guild_id not in cls._cache:
                cls._cache[guild_id] = await cls._load(guild_id)
            return cls._cache[guild_id]

    @classmethod
    async def _load(cls, guild_id: int) -> "GuildSettings":
        row = await db.fetchone(
            "SELECT settings_json FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        )
        if row is None:
            data = dict(DEFAULT_GUILD_SETTINGS)
            await db.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id, settings_json) VALUES (?,?)",
                (guild_id, json.dumps(data)),
            )
        else:
            stored = json.loads(row["settings_json"])
            data = {**DEFAULT_GUILD_SETTINGS, **stored}
        log.debug("Loaded settings for guild %d", guild_id)
        return cls(guild_id, data)

    @classmethod
    def invalidate(cls, guild_id: int) -> None:
        """Remove a guild from the cache so the next fetch() re-reads DB."""
        cls._cache.pop(guild_id, None)

    @classmethod
    async def invalidate_all(cls) -> None:
        async with cls._cache_lock:
            cls._cache.clear()

    # ── Instance accessors ────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """dict-style access: gs.get('prefix', '!')"""
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    # ── Mutators ──────────────────────────────────────────────────────────────

    async def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        await self._persist()

    async def set_many(self, **kwargs: Any) -> None:
        self._data.update(kwargs)
        await self._persist()

    async def reset(self, key: str) -> None:
        self._data[key] = DEFAULT_GUILD_SETTINGS.get(key)
        await self._persist()

    async def reset_all(self) -> None:
        self._data = dict(DEFAULT_GUILD_SETTINGS)
        await self._persist()
        log.info("Guild %d settings reset to defaults", self._guild_id)

    async def _persist(self) -> None:
        await db.execute(
            "INSERT INTO guild_settings (guild_id, settings_json) VALUES (?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET settings_json = excluded.settings_json",
            (self._guild_id, json.dumps(self._data)),
        )

    # ── Convenience properties ─────────────────────────────────────────────────

    @property
    def prefix(self) -> str:
        return self._data.get("prefix", "!")

    @property
    def welcome_channel(self) -> int | None:
        return self._data.get("welcome_channel")

    @property
    def leave_channel(self) -> int | None:
        return self._data.get("leave_channel")

    @property
    def log_channel(self) -> int | None:
        return self._data.get("log_channel")

    @property
    def level_up_channel(self) -> int | None:
        return self._data.get("level_up_channel")

    @property
    def ticket_category(self) -> int | None:
        return self._data.get("ticket_category")

    @property
    def mute_role(self) -> int | None:
        return self._data.get("mute_role")

    @property
    def auto_role(self) -> int | None:
        return self._data.get("auto_role")

    @property
    def welcome_enabled(self) -> bool:
        return bool(self._data.get("welcome_enabled", True))

    @property
    def leave_enabled(self) -> bool:
        return bool(self._data.get("leave_enabled", True))

    @property
    def leveling_enabled(self) -> bool:
        return bool(self._data.get("leveling_enabled", True))

    @property
    def economy_enabled(self) -> bool:
        return bool(self._data.get("economy_enabled", True))

    @property
    def automod_enabled(self) -> bool:
        return bool(self._data.get("automod_enabled", True))

    @property
    def logging_enabled(self) -> bool:
        return bool(self._data.get("logging_enabled", True))

    @property
    def anti_spam_enabled(self) -> bool:
        return bool(self._data.get("anti_spam_enabled", True))

    @property
    def anti_link_enabled(self) -> bool:
        return bool(self._data.get("anti_link_enabled", False))

    @property
    def max_mentions(self) -> int:
        return int(self._data.get("max_mentions", 5))

    @property
    def spam_threshold(self) -> int:
        return int(self._data.get("spam_threshold", 5))

    @property
    def spam_interval(self) -> int:
        return int(self._data.get("spam_interval", 5))

    @property
    def banned_words(self) -> list[str]:
        return list(self._data.get("banned_words", []))

    @property
    def currency_name(self) -> str:
        return self._data.get("currency_name", "coins")

    @property
    def currency_symbol(self) -> str:
        return self._data.get("currency_symbol", "🪙")

    @property
    def daily_amount(self) -> int:
        return int(self._data.get("daily_amount", 100))

    @property
    def work_min(self) -> int:
        return int(self._data.get("work_min", 50))

    @property
    def work_max(self) -> int:
        return int(self._data.get("work_max", 200))

    @property
    def xp_per_message_min(self) -> int:
        return int(self._data.get("xp_per_message_min", 15))

    @property
    def xp_per_message_max(self) -> int:
        return int(self._data.get("xp_per_message_max", 25))

    @property
    def xp_cooldown(self) -> int:
        return int(self._data.get("xp_cooldown", 60))

    @property
    def level_up_message(self) -> str:
        return self._data.get("level_up_message", "🎉 {user} reached level **{level}**!")

    @property
    def welcome_message(self) -> str:
        return self._data.get(
            "welcome_message",
            "Welcome to **{server}**, {user}! You are member #{count}.",
        )

    @property
    def leave_message(self) -> str:
        return self._data.get(
            "leave_message",
            "**{username}** has left. We now have {count} members.",
        )

    def __repr__(self) -> str:
        return f"<GuildSettings guild_id={self._guild_id}>"
