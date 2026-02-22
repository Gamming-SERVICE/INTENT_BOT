import aiosqlite
import asyncio

DB_NAME = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            prefix TEXT DEFAULT '!'
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            guild_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            balance INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        )
        """)

        await db.commit()


async def get_prefix(guild_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT prefix FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row[0]
        return "!"


async def set_prefix(guild_id, prefix):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        INSERT INTO guild_settings (guild_id, prefix)
        VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix
        """, (guild_id, prefix))
        await db.commit()
