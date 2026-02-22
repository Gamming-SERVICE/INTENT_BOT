import aiosqlite
import json

DB_PATH = "database.db"


async def get_prefix(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT settings FROM server_settings WHERE guild_id = ?",
            (guild_id,)
        )
        row = await cursor.fetchone()

        if row and row[0]:
            settings = json.loads(row[0])
            return settings.get("prefix", "!")

        return "!"


async def set_prefix(guild_id, prefix):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT settings FROM server_settings WHERE guild_id = ?",
            (guild_id,)
        )
        row = await cursor.fetchone()

        settings = {}
        if row and row[0]:
            settings = json.loads(row[0])

        settings["prefix"] = prefix

        await db.execute(
            """
            INSERT INTO server_settings (guild_id, settings)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET settings=excluded.settings
            """,
            (guild_id, json.dumps(settings))
        )
        await db.commit()
