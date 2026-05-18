# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — Database
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import aiosqlite

from core.constants import DB_PATH, MARKET_ITEMS
from core.logger import get_logger

log = get_logger("database")


# ── Schema version — bump this each time you add a migration ──────────────────
_SCHEMA_VERSION = 3


class Database:
    """
    Async SQLite database manager.

    • WAL mode for concurrent reads
    • Foreign keys enforced
    • Automatic schema migrations (never drops data)
    • Single persistent connection shared across the process
    """

    _instance: "Database | None" = None

    def __init__(self) -> None:
        self._path = DB_PATH
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    # ── Singleton accessor ────────────────────────────────────────────────────
    @classmethod
    def get(cls) -> "Database":
        if cls._instance is None:
            cls._instance = Database()
        return cls._instance

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def connect(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA cache_size=-32000")   # 32 MB page cache
        await self._conn.execute("PRAGMA temp_store=MEMORY")
        await self._conn.commit()
        log.info("Database connected: %s", self._path)
        await self._run_migrations()
        await self._seed_market_items()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            log.info("Database connection closed")

    # ── Context manager for ad-hoc connections ────────────────────────────────
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Yield the shared connection (thread-safe via asyncio lock)."""
        async with self._lock:
            if self._conn is None:
                raise RuntimeError("Database not connected — call connect() first")
            yield self._conn

    # ── Generic helpers ───────────────────────────────────────────────────────
    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        async with self.acquire() as db:
            cursor = await db.execute(sql, params)
            await db.commit()
            return cursor

    async def executemany(self, sql: str, data: list[tuple]) -> None:
        async with self.acquire() as db:
            await db.executemany(sql, data)
            await db.commit()

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        async with self.acquire() as db:
            cursor = await db.execute(sql, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        async with self.acquire() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Migration system ──────────────────────────────────────────────────────
    async def _run_migrations(self) -> None:
        async with self.acquire() as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
            )
            row = await (await db.execute("SELECT version FROM schema_version")).fetchone()
            current = row[0] if row else 0

        for v in range(current + 1, _SCHEMA_VERSION + 1):
            method = getattr(self, f"_migration_v{v}", None)
            if method:
                log.info("Running DB migration v%d …", v)
                await method()
                async with self.acquire() as db:
                    await db.execute("DELETE FROM schema_version")
                    await db.execute("INSERT INTO schema_version VALUES (?)", (v,))
                    await db.commit()
                log.info("Migration v%d complete", v)

    async def _migration_v1(self) -> None:
        """Initial full schema."""
        async with self.acquire() as db:
            # guild_settings — all per-guild configuration
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id        INTEGER PRIMARY KEY,
                    settings_json   TEXT    NOT NULL DEFAULT '{}'
                )
            """)
            # users
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER,
                    guild_id    INTEGER,
                    xp          INTEGER NOT NULL DEFAULT 0,
                    level       INTEGER NOT NULL DEFAULT 1,
                    messages    INTEGER NOT NULL DEFAULT 0,
                    balance     INTEGER NOT NULL DEFAULT 0,
                    bank        INTEGER NOT NULL DEFAULT 0,
                    daily_at    TEXT,
                    work_at     TEXT,
                    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_guild ON users(guild_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_xp    ON users(guild_id, xp DESC)")
            # warnings
            await db.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL,
                    guild_id     INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    reason       TEXT    NOT NULL,
                    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_warn_user ON warnings(guild_id, user_id)")
            # mod_logs
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mod_logs (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id     INTEGER NOT NULL,
                    user_id      INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    action       TEXT    NOT NULL,
                    reason       TEXT,
                    duration     TEXT,
                    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # tickets
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER UNIQUE NOT NULL,
                    user_id    INTEGER NOT NULL,
                    guild_id   INTEGER NOT NULL,
                    status     TEXT    NOT NULL DEFAULT 'open',
                    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    closed_at  TEXT
                )
            """)
            # giveaways
            await db.execute("""
                CREATE TABLE IF NOT EXISTS giveaways (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id   INTEGER UNIQUE NOT NULL,
                    channel_id   INTEGER NOT NULL,
                    guild_id     INTEGER NOT NULL,
                    prize        TEXT    NOT NULL,
                    winners      INTEGER NOT NULL DEFAULT 1,
                    host_id      INTEGER NOT NULL,
                    end_time     TEXT    NOT NULL,
                    ended        INTEGER NOT NULL DEFAULT 0,
                    participants TEXT    NOT NULL DEFAULT '[]'
                )
            """)
            # reaction_roles
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER NOT NULL,
                    emoji      TEXT    NOT NULL,
                    role_id    INTEGER NOT NULL,
                    guild_id   INTEGER NOT NULL,
                    PRIMARY KEY (message_id, emoji)
                )
            """)
            # color_roles
            await db.execute("""
                CREATE TABLE IF NOT EXISTS color_roles (
                    guild_id INTEGER NOT NULL,
                    role_id  INTEGER NOT NULL,
                    label    TEXT    NOT NULL,
                    emoji    TEXT    NOT NULL DEFAULT '🎨',
                    style    INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            # reminders
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    guild_id   INTEGER NOT NULL,
                    reminder   TEXT    NOT NULL,
                    remind_at  TEXT    NOT NULL,
                    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # custom_commands
            await db.execute("""
                CREATE TABLE IF NOT EXISTS custom_commands (
                    name       TEXT    NOT NULL,
                    guild_id   INTEGER NOT NULL,
                    response   TEXT    NOT NULL,
                    created_by INTEGER NOT NULL,
                    uses       INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (name, guild_id)
                )
            """)
            # market_items (global catalog)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS market_items (
                    item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          TEXT    UNIQUE NOT NULL,
                    category      TEXT    NOT NULL DEFAULT 'misc',
                    description   TEXT    NOT NULL DEFAULT '',
                    emoji         TEXT    NOT NULL DEFAULT '📦',
                    base_price    INTEGER NOT NULL DEFAULT 100,
                    current_price REAL    NOT NULL DEFAULT 100.0,
                    total_bought  INTEGER NOT NULL DEFAULT 0,
                    total_sold    INTEGER NOT NULL DEFAULT 0,
                    rarity        TEXT    NOT NULL DEFAULT 'common',
                    tradeable     INTEGER NOT NULL DEFAULT 1,
                    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # user_items
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_items (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    guild_id    INTEGER NOT NULL,
                    item_id     INTEGER NOT NULL,
                    quantity    INTEGER NOT NULL DEFAULT 1,
                    acquired_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, guild_id, item_id),
                    FOREIGN KEY (item_id) REFERENCES market_items(item_id)
                )
            """)
            # trades
            await db.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id    INTEGER NOT NULL,
                    sender_id   INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    item_id     INTEGER NOT NULL,
                    quantity    INTEGER NOT NULL DEFAULT 1,
                    price       INTEGER NOT NULL DEFAULT 0,
                    status      TEXT    NOT NULL DEFAULT 'pending',
                    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TEXT
                )
            """)
            # ai_tokens
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ai_tokens (
                    guild_id   INTEGER NOT NULL,
                    provider   TEXT    NOT NULL,
                    token      TEXT    NOT NULL,
                    added_by   INTEGER NOT NULL,
                    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, provider)
                )
            """)
            # music_settings
            await db.execute("""
                CREATE TABLE IF NOT EXISTS music_settings (
                    guild_id    INTEGER PRIMARY KEY,
                    vc_channel  INTEGER,
                    volume      INTEGER NOT NULL DEFAULT 50,
                    loop_mode   TEXT    NOT NULL DEFAULT 'off'
                )
            """)
            await db.commit()

    async def _migration_v2(self) -> None:
        """Add automod_rules table."""
        async with self.acquire() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_rules (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id    INTEGER NOT NULL,
                    rule_type   TEXT    NOT NULL,
                    value       TEXT    NOT NULL,
                    action      TEXT    NOT NULL DEFAULT 'delete',
                    created_by  INTEGER NOT NULL,
                    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def _migration_v3(self) -> None:
        """Add waifu_collection table."""
        async with self.acquire() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS waifu_collection (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL,
                    guild_id     INTEGER NOT NULL,
                    waifu_name   TEXT    NOT NULL,
                    waifu_url    TEXT    NOT NULL,
                    waifu_type   TEXT    NOT NULL,
                    rarity       TEXT    NOT NULL DEFAULT 'common',
                    collected_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    # ── Market seeding ────────────────────────────────────────────────────────
    async def _seed_market_items(self) -> None:
        count = await self.fetchone("SELECT COUNT(*) AS c FROM market_items")
        if count and count["c"] > 0:
            return

        rows = [
            (name, cat, desc, emoji, price, float(price), rarity)
            for name, cat, desc, emoji, price, rarity in MARKET_ITEMS
        ]
        await self.executemany(
            """INSERT OR IGNORE INTO market_items
               (name, category, description, emoji, base_price, current_price, rarity)
               VALUES (?,?,?,?,?,?,?)""",
            rows,
        )
        log.info("Seeded %d market items", len(rows))


# ── Module-level shortcut ─────────────────────────────────────────────────────
db: Database = Database.get()
