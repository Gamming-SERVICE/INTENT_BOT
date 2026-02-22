from discord.ext import commands
import aiosqlite

DB = "database.db"


class Market(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def market(self, ctx):
        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute(
                "SELECT item_id, name, price FROM market_items"
            )
            rows = await cursor.fetchall()

        if not rows:
            return await ctx.send("Market empty.")

        msg = ""
        for item in rows:
            msg += f"ID: {item[0]} | {item[1]} — {item[2]}\n"

        await ctx.send(msg)

    @commands.command()
    async def buy(self, ctx, item_id: int):
        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute(
                "SELECT name, price FROM market_items WHERE item_id = ?",
                (item_id,)
            )
            item = await cursor.fetchone()

            if not item:
                return await ctx.send("Invalid item.")

            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (ctx.author.id,)
            )
            user = await cursor.fetchone()

            if not user or user[0] < item[1]:
                return await ctx.send("Not enough coins.")

            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (item[1], ctx.author.id)
            )

            await db.execute(
                "INSERT INTO user_items (user_id, item_id) VALUES (?, ?)",
                (ctx.author.id, item_id)
            )

            await db.commit()

        await ctx.send(f"You bought {item[0]}.")
