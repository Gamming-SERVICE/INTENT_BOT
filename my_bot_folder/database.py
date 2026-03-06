import aiosqlite
import datetime

# Database Initialization (Your exact logic)
async def init_database():
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                balance INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                daily_claimed TEXT,
                work_claimed TEXT,
                inventory TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # ... [Rest of your CREATE TABLE statements from your code] ...
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # [Add all your other CREATE TABLE statements here exactly as they were]
        await db.commit()
    print("✅ Database connection verified and tables checked.")

# Helper functions you use everywhere
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
