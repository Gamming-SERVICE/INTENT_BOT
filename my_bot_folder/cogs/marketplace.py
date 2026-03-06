import discord
from discord.ext import commands
import math
import aiosqlite
import datetime
from database import get_user_data, update_user_data

class Marketplace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def calculate_market_price(self, base_price, total_bought, total_sold):
        demand_ratio = (total_bought + 1) / (total_sold + 1)
        multiplier = math.log(demand_ratio + 1, 2) + 0.5
        return round(base_price * max(0.3, min(multiplier, 5.0)), 2)

    @commands.command(aliases=["shop"])
    async def market(self, ctx, category: str = None):
        async with aiosqlite.connect("bot_database.db") as db:
            query = "SELECT * FROM market_items"
            params = []
            if category:
                query += " WHERE LOWER(category) = ?"
                params.append(category.lower())
            
            cursor = await db.execute(query, params)
            items = await cursor.fetchall()

        if not items:
            return await ctx.send("❌ No items found in this category.")

        embed = discord.Embed(title="🛒 Marketplace", color=discord.Color.teal())
        for item in items[:10]: # Showing first 10 items
            price = round(item[6])
            embed.add_field(
                name=f"{item[4]} {item[1]} (ID: {item[0]})",
                value=f"Price: {self.bot.config['CURRENCY_SYMBOL']} {price:,}\nCategory: {item[2]}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command()
    async def mbuy(self, ctx, item_id: int, quantity: int = 1):
        if quantity <= 0: return await ctx.send("❌ Quantity must be positive.")

        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT * FROM market_items WHERE item_id = ?", (item_id,))
            item = await cursor.fetchone()
            if not item: return await ctx.send("❌ Item not found.")

            total_cost = round(item[6]) * quantity
            user_data = await get_user_data(ctx.author.id, ctx.guild.id)

            if user_data["balance"] < total_cost:
                return await ctx.send(f"❌ Need {self.bot.config['CURRENCY_SYMBOL']} {total_cost:,}")

            # Update Bal & Inventory
            await update_user_data(ctx.author.id, ctx.guild.id, balance=user_data["balance"] - total_cost)
            await db.execute("""INSERT INTO user_items (user_id, guild_id, item_id, quantity) VALUES (?, ?, ?, ?)
                               ON CONFLICT(user_id, guild_id, item_id) DO UPDATE SET quantity = quantity + ?""",
                            (ctx.author.id, ctx.guild.id, item_id, quantity, quantity))
            
            # Update Market Price
            new_bought = item[7] + quantity
            new_price = self.calculate_market_price(item[5], new_bought, item[8])
            await db.execute("UPDATE market_items SET total_bought = ?, current_price = ? WHERE item_id = ?",
                            (new_bought, new_price, item_id))
            await db.commit()

        await ctx.send(f"✅ Bought {quantity}x **{item[1]}** for {self.bot.config['CURRENCY_SYMBOL']} {total_cost:,}")

async def setup(bot):
    await bot.add_cog(Marketplace(bot))
