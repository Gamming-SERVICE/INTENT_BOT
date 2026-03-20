import aiosqlite
import discord
from discord.ext import commands

from config import CONFIG
from database import DB_PATH, get_user_data, update_user_data


class Market(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(aliases=["shop"])
    async def market(self, ctx: commands.Context, category: str | None = None) -> None:
        query = "SELECT item_id, name, category, emoji, current_price FROM market_items"
        params: tuple = ()
        if category:
            query += " WHERE LOWER(category) = ?"
            params = (category.lower(),)

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(query, params)
            items = await cursor.fetchall()

        if not items:
            await ctx.send("No items found.")
            return

        embed = discord.Embed(title="🛒 Market", color=discord.Color.teal())
        for item_id, name, item_category, emoji, price in items[:10]:
            embed.add_field(
                name=f"{emoji} {name} (ID: {item_id})",
                value=f"Category: {item_category}\nPrice: {CONFIG['CURRENCY_SYMBOL']} {round(price):,}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.command()
    async def mbuy(self, ctx: commands.Context, item_id: int, quantity: int = 1) -> None:
        if quantity <= 0:
            await ctx.send("Quantity must be greater than 0.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name, current_price FROM market_items WHERE item_id = ?",
                (item_id,),
            )
            item = await cursor.fetchone()
            if not item:
                await ctx.send("Item not found.")
                return

            total_cost = round(item[1]) * quantity
            data = await get_user_data(ctx.author.id, ctx.guild.id)
            if data["balance"] < total_cost:
                await ctx.send("Insufficient balance.")
                return

            await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] - total_cost)
            await db.execute(
                """
                INSERT INTO user_items (user_id, guild_id, item_id, quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id, item_id)
                DO UPDATE SET quantity = quantity + excluded.quantity
                """,
                (ctx.author.id, ctx.guild.id, item_id, quantity),
            )
            await db.commit()

        await ctx.send(f"✅ Purchased {quantity}x {item[0]} for {CONFIG['CURRENCY_SYMBOL']} {total_cost:,}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Market(bot))
