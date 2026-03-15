import aiosqlite

DB_PATH = "bot_database.db"


async def init_database() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                balance INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                daily_claimed TEXT,
                work_claimed TEXT,
                inventory TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS invite_stats (
                guild_id INTEGER,
                inviter_id INTEGER,
                total_invites INTEGER DEFAULT 0,
                fake_invites INTEGER DEFAULT 0,
                left_invites INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, inviter_id)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS invite_joins (
                guild_id INTEGER,
                joined_user_id INTEGER,
                inviter_id INTEGER,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, joined_user_id)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS market_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                category TEXT DEFAULT 'misc',
                description TEXT DEFAULT '',
                emoji TEXT DEFAULT '📦',
                base_price INTEGER DEFAULT 100,
                current_price REAL DEFAULT 100.0,
                total_bought INTEGER DEFAULT 0,
                total_sold INTEGER DEFAULT 0
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_items (
                user_id INTEGER,
                guild_id INTEGER,
                item_id INTEGER,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id, item_id)
            )
            """
        )
        await db.commit()


async def get_user_data(user_id: int, guild_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        row = await cursor.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO users (user_id, guild_id) VALUES (?, ?)",
                (user_id, guild_id),
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            row = await cursor.fetchone()
        return dict(row)


async def update_user_data(user_id: int, guild_id: int, **kwargs) -> None:
    if not kwargs:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [user_id, guild_id]
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE user_id = ? AND guild_id = ?",
            values,
        )
        await db.commit()
