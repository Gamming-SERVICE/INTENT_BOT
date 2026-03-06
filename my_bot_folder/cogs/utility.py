import discord
import aiosqlite
import datetime
import re
import math

# Your exact CONFIG
CONFIG = {
    "TOKEN": "DISCORD_TOKEN", 
    "GUILD_ID": 1429056625183948882,
    "PREFIX": "!",
    "OWNER_IDS": [],
    "WELCOME_ENABLED": True,
    "LEVELING_ENABLED": True,
    "ECONOMY_ENABLED": True,
    "AUTOMOD_ENABLED": True,
    "LOGGING_ENABLED": True,
    "MUSIC_ENABLED": True,
    "CURRENCY_NAME": "coins",
    "CURRENCY_SYMBOL": "🪙",
    "DAILY_AMOUNT": 100,
    "WORK_MIN": 50,
    "WORK_MAX": 200,
    "WORK_COOLDOWN": 3600,
    "XP_PER_MESSAGE": (15, 25),
    "XP_COOLDOWN": 60,
    "LEVEL_UP_MESSAGE": "🎉 Congratulations {user}! You've reached level **{level}**!",
}

async def init_database():
    async with aiosqlite.connect("bot_database.db") as db:
        # User Data Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, guild_id INTEGER,
                xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0, balance INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0, daily_claimed TEXT,
                work_claimed TEXT, inventory TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        # Warnings Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                guild_id INTEGER, moderator_id INTEGER, reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        # Marketplace Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS market_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
                category TEXT DEFAULT 'misc', description TEXT DEFAULT '',
                emoji TEXT DEFAULT '📦', base_price INTEGER DEFAULT 100,
                current_price REAL DEFAULT 100.0, total_bought INTEGER DEFAULT 0,
                total_sold INTEGER DEFAULT 0, rarity TEXT DEFAULT 'common',
                tradeable INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        await db.commit()

# --- Helpers ---
def get_level_xp(level): return 5 * (level ** 2) + 50 * level + 100

def get_level_from_xp(xp):
    level, temp_xp = 1, xp
    while temp_xp >= get_level_xp(level):
        temp_xp -= get_level_xp(level)
        level += 1
    return level, temp_xp

async def get_user_data(user_id, guild_id):
    async with aiosqlite.connect("bot_database.db") as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT INTO users (user_id, guild_id) VALUES (?, ?)", (user_id, guild_id))
            await db.commit()
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            row = await cursor.fetchone()
        return dict(row)

async def update_user_data(user_id, guild_id, **kwargs):
    async with aiosqlite.connect("bot_database.db") as db:
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [user_id, guild_id]
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ? AND guild_id = ?", values)
        await db.commit()

def create_embed(title, description=None, color=discord.Color.blue(), **kwargs):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.datetime.utcnow()
    return embed

def parse_time(time_str):
    time_regex = re.compile(r"(\d+)([smhdw])")
    matches = time_regex.findall(time_str.lower())
    if not matches: return None
    total_seconds = 0
    for value, unit in matches:
        value = int(value)
        if unit == "s": total_seconds += value
        elif unit == "m": total_seconds += value * 60
        elif unit == "h": total_seconds += value * 3600
        elif unit == "d": total_seconds += value * 86400
    return total_seconds
