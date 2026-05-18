# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — In-Process Cache
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Any, Callable, Generic, Hashable, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """
    Thread-safe async TTL cache backed by an OrderedDict.

    Entries expire after `ttl` seconds. The cache is capped at `maxsize`
    entries; oldest entries are evicted when the cap is reached.
    """

    def __init__(self, maxsize: int = 1024, ttl: float = 300.0) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: OrderedDict[Hashable, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: Hashable) -> T | None:
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._data[key]
                return None
            # Move to end (LRU ordering)
            self._data.move_to_end(key)
            return value

    async def set(self, key: Hashable, value: T, ttl: float | None = None) -> None:
        async with self._lock:
            expires_at = time.monotonic() + (ttl if ttl is not None else self._ttl)
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (value, expires_at)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    async def delete(self, key: Hashable) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()

    async def purge_expired(self) -> int:
        now = time.monotonic()
        async with self._lock:
            expired = [k for k, (_, exp) in self._data.items() if now > exp]
            for k in expired:
                del self._data[k]
        return len(expired)

    def __len__(self) -> int:
        return len(self._data)


# ── Shared caches (module-level singletons) ───────────────────────────────────

# Spam tracker: guild_id → {user_id: [timestamps]}  (short TTL, fast access)
spam_tracker: dict[int, dict[int, list[float]]] = {}

# XP cooldowns: (guild_id, user_id) → float (unix ts of last XP grant)
xp_cooldowns: dict[tuple[int, int], float] = {}

# AFK users: user_id → {"reason": str, "since": float}
afk_users: dict[int, dict] = {}

# Reaction-role map: (message_id, emoji_str) → role_id
reaction_roles_cache: dict[tuple[int, str], int] = {}

# Custom commands per guild: (guild_id, name) → response
custom_commands_cache: dict[tuple[int, str], str] = {}

# Active giveaways: message_id → giveaway data dict
active_giveaways_cache: dict[int, dict] = {}

# User data cache: (user_id, guild_id) → dict
user_cache: TTLCache[dict] = TTLCache(maxsize=4096, ttl=120)

# Guild settings cache is handled in core/settings.py


async def load_reaction_roles_into_cache() -> None:
    """Populate reaction_roles_cache from database on startup."""
    from core.database import db

    rows = await db.fetchall("SELECT message_id, emoji, role_id FROM reaction_roles")
    reaction_roles_cache.clear()
    for row in rows:
        reaction_roles_cache[(row["message_id"], row["emoji"])] = row["role_id"]


async def load_custom_commands_into_cache() -> None:
    """Populate custom_commands_cache from database on startup."""
    from core.database import db

    rows = await db.fetchall("SELECT guild_id, name, response FROM custom_commands")
    custom_commands_cache.clear()
    for row in rows:
        custom_commands_cache[(row["guild_id"], row["name"])] = row["response"]
