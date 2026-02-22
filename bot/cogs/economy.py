from discord.ext import commands
import aiosqlite

DB = "database.db"


class Economy(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def ensure_user(self, user_id):
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, balance, bank)
                VALUES (?, 0, 0)
            """, (user_id,))
            await db.commit()

    @commands.command()
    async def balance(self, ctx, member: commands.MemberConverter = None):
        user = member or ctx.author

        await self.ensure_user(user.id)

        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute(
                "SELECT balance, bank FROM users WHERE user_id = ?",
                (user.id,)
            )
            row = await cursor.fetchone()

        await ctx.send(
            f"💰 Wallet: {row[0]}\n🏦 Bank: {row[1]}"
        )

    @commands.command()
    async def deposit(self, ctx, amount: int):
        await self.ensure_user(ctx.author.id)

        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (ctx.author.id,)
            )
            row = await cursor.fetchone()

            if row[0] < amount:
                return await ctx.send("Not enough money.")

            await db.execute(
                "UPDATE users SET balance = balance - ?, bank = bank + ? WHERE user_id = ?",
                (amount, amount, ctx.author.id)
            )
            await db.commit()

        await ctx.send("Deposited successfully.")

    @commands.command()
    async def withdraw(self, ctx, amount: int):
        await self.ensure_user(ctx.author.id)

        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute(
                "SELECT bank FROM users WHERE user_id = ?",
                (ctx.author.id,)
            )
            row = await cursor.fetchone()

            if row[0] < amount:
                return await ctx.send("Not enough bank balance.")

            await db.execute(
                "UPDATE users SET balance = balance + ?, bank = bank - ? WHERE user_id = ?",
                (amount, amount, ctx.author.id)
            )
            await db.commit()

        await ctx.send("Withdraw successful.")

    @commands.command()
    async def give(self, ctx, member: commands.MemberConverter, amount: int):
        await self.ensure_user(ctx.author.id)
        await self.ensure_user(member.id)

        async with aiosqlite.connect(DB) as db:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (ctx.author.id,)
            )
            row = await cursor.fetchone()

            if row[0] < amount:
                return await ctx.send("Not enough money.")

            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, ctx.author.id)
            )
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, member.id)
            )

            await db.commit()

        await ctx.send(f"Transferred {amount} coins.")

async def setup(bot):
    await bot.add_cog(Economy(bot))
