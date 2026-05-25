# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Marketplace Cog
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.constants import RARITY_COLORS, RARITY_STARS
import core.embeds as emb
from core.logger import get_logger
from views.market_views import TradeConfirmView
from views.role_views import PaginatorView

log = get_logger("marketplace")

ITEMS_PER_PAGE = 12


class Marketplace(commands.Cog, name="Marketplace"):
    """Global item marketplace with buying, selling, inventory, and trading."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _check_economy(self, ctx: commands.Context) -> bool:
        gs = await GuildSettings.fetch(ctx.guild.id)
        if not gs.economy_enabled:
            await ctx.send(embed=emb.error("Economy is disabled on this server."))
            return False
        return True

    # ── Shop ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="shop", description="Browse the item shop")
    @app_commands.describe(category="Filter by category (fish, minerals, food, tools, etc.)")
    @commands.guild_only()
    async def shop(self, ctx: commands.Context, category: str | None = None) -> None:
        if not await self._check_economy(ctx): return
        gs = await GuildSettings.fetch(ctx.guild.id)

        if category:
            rows = await db.fetchall(
                "SELECT * FROM market_items WHERE category = ? ORDER BY base_price ASC",
                (category.lower(),),
            )
        else:
            rows = await db.fetchall("SELECT * FROM market_items ORDER BY category, base_price ASC")

        if not rows:
            return await ctx.send(embed=emb.error("No items found" + (f" in category **{category}**" if category else "") + "."))

        chunks = [rows[i:i + ITEMS_PER_PAGE] for i in range(0, len(rows), ITEMS_PER_PAGE)]
        pages  = []
        for i, chunk in enumerate(chunks, 1):
            lines = [
                f"{r['emoji']} **{r['name']}** — {gs.currency_symbol} {int(r['current_price']):,} "
                f"[{RARITY_STARS.get(r['rarity'], '⚪')} {r['rarity']}]"
                for r in chunk
            ]
            embed = emb.build(
                title="🛒 Item Shop" + (f" — {category.title()}" if category else ""),
                description="\n".join(lines),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text=f"Page {i}/{len(chunks)} • Use /buy <item name> to purchase")
            pages.append(embed)

        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            await ctx.send(embed=pages[0], view=PaginatorView(pages, ctx.author.id))

    # ── Buy ────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(item="Item name", quantity="How many to buy (default 1)")
    @commands.guild_only()
    async def buy(self, ctx: commands.Context, quantity: int = 1, *, item: str) -> None:
        if not await self._check_economy(ctx): return
        gs   = await GuildSettings.fetch(ctx.guild.id)
        row  = await db.fetchone(
            "SELECT * FROM market_items WHERE LOWER(name) = LOWER(?)",
            (item,),
        )
        if not row:
            return await ctx.send(embed=emb.error(f"Item **{item}** not found. Check `/shop` for the list."))
        if quantity < 1:
            return await ctx.send(embed=emb.error("Quantity must be at least 1."))

        total_cost = int(row["current_price"]) * quantity
        user = await db.fetchone(
            "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
            (ctx.author.id, ctx.guild.id),
        )
        if not user:
            await db.execute("INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?,?)", (ctx.author.id, ctx.guild.id))
            user = {"balance": 0}

        if user["balance"] < total_cost:
            return await ctx.send(
                embed=emb.error(
                    f"You need **{gs.currency_symbol} {total_cost:,}** but have **{gs.currency_symbol} {user['balance']:,}**."
                )
            )

        # Deduct balance, add item to inventory
        await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
            (total_cost, ctx.author.id, ctx.guild.id),
        )
        await db.execute(
            """INSERT INTO user_items (user_id, guild_id, item_id, quantity) VALUES (?,?,?,?)
               ON CONFLICT(user_id, guild_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity""",
            (ctx.author.id, ctx.guild.id, row["item_id"], quantity),
        )
        await db.execute(
            "UPDATE market_items SET total_bought = total_bought + ? WHERE item_id = ?",
            (quantity, row["item_id"]),
        )
        await ctx.send(
            embed=emb.build(
                title="✅ Purchase Successful",
                color=RARITY_COLORS.get(row["rarity"], discord.Color.green()),
                fields=[
                    ("Item",  f"{row['emoji']} {row['name']} ×{quantity}", True),
                    ("Paid",  f"{gs.currency_symbol} {total_cost:,}",      True),
                ],
            )
        )

    # ── Sell ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="sell", description="Sell an item from your inventory")
    @app_commands.describe(item="Item name", quantity="How many to sell")
    @commands.guild_only()
    async def sell(self, ctx: commands.Context, quantity: int = 1, *, item: str) -> None:
        if not await self._check_economy(ctx): return
        gs      = await GuildSettings.fetch(ctx.guild.id)
        mrow    = await db.fetchone("SELECT * FROM market_items WHERE LOWER(name) = LOWER(?)", (item,))
        if not mrow:
            return await ctx.send(embed=emb.error(f"Item **{item}** not found."))

        inv_row = await db.fetchone(
            "SELECT quantity FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (ctx.author.id, ctx.guild.id, mrow["item_id"]),
        )
        if not inv_row or inv_row["quantity"] < quantity:
            return await ctx.send(embed=emb.error(f"You don't have {quantity}× **{mrow['name']}**."))

        sell_price = int(mrow["current_price"] * 0.7) * quantity   # 70% of current price
        new_qty    = inv_row["quantity"] - quantity
        if new_qty <= 0:
            await db.execute(
                "DELETE FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                (ctx.author.id, ctx.guild.id, mrow["item_id"]),
            )
        else:
            await db.execute(
                "UPDATE user_items SET quantity = ? WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                (new_qty, ctx.author.id, ctx.guild.id, mrow["item_id"]),
            )
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
            (sell_price, ctx.author.id, ctx.guild.id),
        )
        await db.execute(
            "UPDATE market_items SET total_sold = total_sold + ? WHERE item_id = ?",
            (quantity, mrow["item_id"]),
        )
        await ctx.send(
            embed=emb.success(
                f"Sold {mrow['emoji']} **{mrow['name']}** ×{quantity} for **{gs.currency_symbol} {sell_price:,}**!"
            )
        )

    # ── Inventory ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="inventory", aliases=["inv", "bag"], description="View your item inventory")
    @app_commands.describe(member="Member to check (defaults to you)")
    @commands.guild_only()
    async def inventory(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        if not await self._check_economy(ctx): return
        target = member or ctx.author

        rows = await db.fetchall(
            """SELECT mi.name, mi.emoji, mi.rarity, ui.quantity
               FROM user_items ui
               JOIN market_items mi ON ui.item_id = mi.item_id
               WHERE ui.user_id = ? AND ui.guild_id = ?
               ORDER BY mi.rarity DESC, mi.name ASC""",
            (target.id, ctx.guild.id),
        )
        if not rows:
            owner_str = "Your" if target == ctx.author else f"{target.display_name}'s"
            return await ctx.send(embed=emb.info(f"{owner_str} inventory is empty."))

        lines  = [f"{r['emoji']} **{r['name']}** ×{r['quantity']} [{RARITY_STARS.get(r['rarity'], '⚪')}]" for r in rows]
        chunks = [lines[i:i + 15] for i in range(0, len(lines), 15)]
        pages  = [
            emb.build(
                title=f"🎒 {target.display_name}'s Inventory",
                description="\n".join(chunk),
                color=discord.Color.blurple(),
                thumbnail=target.display_avatar.url,
            )
            for chunk in chunks
        ]
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            await ctx.send(embed=pages[0], view=PaginatorView(pages, ctx.author.id))

    # ── Trade ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="trade", description="Send a trade offer to another member")
    @app_commands.describe(member="Member to trade with", item="Item to trade", quantity="Quantity", price="Price you want")
    @commands.guild_only()
    async def trade(
        self,
        ctx: commands.Context,
        member: discord.Member,
        quantity: int,
        price: int,
        *,
        item: str,
    ) -> None:
        if not await self._check_economy(ctx): return
        if member.bot or member == ctx.author:
            return await ctx.send(embed=emb.error("Invalid trade target."))
        if quantity < 1 or price < 0:
            return await ctx.send(embed=emb.error("Invalid quantity or price."))

        gs   = await GuildSettings.fetch(ctx.guild.id)
        mrow = await db.fetchone("SELECT * FROM market_items WHERE LOWER(name) = LOWER(?)", (item,))
        if not mrow:
            return await ctx.send(embed=emb.error(f"Item **{item}** not found."))
        if not mrow["tradeable"]:
            return await ctx.send(embed=emb.error("That item is not tradeable."))

        inv = await db.fetchone(
            "SELECT quantity FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (ctx.author.id, ctx.guild.id, mrow["item_id"]),
        )
        if not inv or inv["quantity"] < quantity:
            return await ctx.send(embed=emb.error(f"You don't have {quantity}× **{mrow['name']}**."))

        trade_id = await db.execute_returning_id(
            "INSERT INTO trades (guild_id, sender_id, receiver_id, item_id, quantity, price) VALUES (?,?,?,?,?,?)",
            (ctx.guild.id, ctx.author.id, member.id, mrow["item_id"], quantity, price),
        )

        embed = emb.build(
            title="🤝 Trade Offer",
            description=f"{ctx.author.mention} wants to sell {member.mention}:",
            color=discord.Color.blurple(),
            fields=[
                ("Item",     f"{mrow['emoji']} {mrow['name']} ×{quantity}", True),
                ("Price",    f"{gs.currency_symbol} {price:,}",             True),
            ],
        )
        view = TradeConfirmView(trade_id, ctx.author, member, mrow["name"], quantity, price, gs.currency_symbol)
        await ctx.send(content=member.mention, embed=embed, view=view)

    # ── Item info ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="iteminfo", description="Get details about a shop item")
    @app_commands.describe(item="Item name")
    @commands.guild_only()
    async def iteminfo(self, ctx: commands.Context, *, item: str) -> None:
        gs  = await GuildSettings.fetch(ctx.guild.id)
        row = await db.fetchone("SELECT * FROM market_items WHERE LOWER(name) = LOWER(?)", (item,))
        if not row:
            return await ctx.send(embed=emb.error(f"Item **{item}** not found."))
        embed = emb.build(
            title=f"{row['emoji']} {row['name']}",
            description=row["description"],
            color=RARITY_COLORS.get(row["rarity"], discord.Color.blurple()),
            fields=[
                ("Category",   row["category"].title(),                   True),
                ("Rarity",     f"{RARITY_STARS.get(row['rarity'], '⚪')} {row['rarity'].title()}", True),
                ("Buy Price",  f"{gs.currency_symbol} {int(row['current_price']):,}", True),
                ("Sell Price", f"{gs.currency_symbol} {int(row['current_price'] * 0.7):,}", True),
                ("Tradeable",  "✅ Yes" if row["tradeable"] else "❌ No", True),
                ("Total Bought", f"{row['total_bought']:,}",              True),
            ],
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Marketplace(bot))
    log.info("Marketplace cog loaded")
