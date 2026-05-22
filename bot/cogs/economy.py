# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Economy Cog
#                   PREFIX-ONLY | No slash commands
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import datetime
import random

import discord
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.permissions import require_admin
from core.constants import WORK_RESPONSES
import core.embeds as emb
from core.logger import get_logger

log = get_logger("economy")

_ROB_WIN_CHANCE     = 0.40
_ROB_FINE_PERCENT   = 0.20
_ROB_MAX_STEAL      = 5_000
_ROB_MIN_VICTIM_BAL = 200

_rob_locks: dict[tuple, asyncio.Lock] = {}


def _rob_lock(user_id: int, guild_id: int) -> asyncio.Lock:
    key = (user_id, guild_id)
    if key not in _rob_locks:
        _rob_locks[key] = asyncio.Lock()
    return _rob_locks[key]


async def _ensure_user(user_id: int, guild_id: int) -> dict:
    row = await db.fetchone(
        "SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
    )
    if row is None:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?,?)", (user_id, guild_id)
        )
        row = await db.fetchone(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
        )
    return row


async def _add_balance(user_id: int, guild_id: int, amount: int) -> int:
    await db.execute(
        "UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ? AND guild_id = ?",
        (amount, user_id, guild_id),
    )
    row = await db.fetchone(
        "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
    )
    return row["balance"] if row else 0


class Economy(commands.Cog, name="Economy"):
    """Virtual economy commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _gate(self, ctx: commands.Context) -> bool:
        gs = await GuildSettings.get(ctx.guild.id)
        if not gs.economy_enabled:
            await ctx.send(embed=emb.error("The economy system is disabled on this server."))
            return False
        return True

    # ── Balance ────────────────────────────────────────────────────────────────

    @commands.command(name="balance", aliases=["bal", "wallet"])
    @commands.guild_only()
    async def balance(self, ctx: commands.Context, member: discord.Member = None) -> None:
        """Check your or another member's balance. Usage: !balance [@user]"""
        if not await self._gate(ctx): return
        target = member or ctx.author
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(target.id, ctx.guild.id)
        await ctx.send(embed=emb.build(
            title=f"💰 {target.display_name}'s Finances",
            color=discord.Color.gold(),
            thumbnail=target.display_avatar.url,
            fields=[
                ("Wallet", f"{gs.currency_symbol} {data['balance']:,}", True),
                ("Bank",   f"{gs.currency_symbol} {data['bank']:,}",    True),
                ("Total",  f"{gs.currency_symbol} {data['balance'] + data['bank']:,}", True),
            ],
        ))

    # ── Daily ──────────────────────────────────────────────────────────────────

    @commands.command(name="daily")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def daily(self, ctx: commands.Context) -> None:
        """Claim your daily coins. Usage: !daily"""
        if not await self._gate(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        now  = datetime.datetime.utcnow()
        if data["daily_at"]:
            try:
                last = datetime.datetime.fromisoformat(data["daily_at"])
                diff = now - last
                if diff.total_seconds() < 86400:
                    remaining = 86400 - diff.total_seconds()
                    h, rem = divmod(int(remaining), 3600)
                    m = rem // 60
                    return await ctx.send(embed=emb.warning(
                        f"Already claimed today!\nNext claim in **{h}h {m}m**."
                    ))
            except ValueError:
                pass
        amount = gs.daily_amount
        new_bal = await _add_balance(ctx.author.id, ctx.guild.id, amount)
        await db.execute(
            "UPDATE users SET daily_at = ? WHERE user_id = ? AND guild_id = ?",
            (now.isoformat(), ctx.author.id, ctx.guild.id),
        )
        await db.record_transaction(ctx.guild.id, ctx.author.id, "daily", amount, new_bal)
        await ctx.send(embed=emb.build(
            title="🎁 Daily Reward Claimed!",
            description=f"You received **{gs.currency_symbol} {amount:,}**!\nNew wallet: **{gs.currency_symbol} {new_bal:,}**",
            color=discord.Color.gold(),
            author=ctx.author,
        ))

    # ── Work ───────────────────────────────────────────────────────────────────

    @commands.command(name="work")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def work(self, ctx: commands.Context) -> None:
        """Work to earn coins (1 hour cooldown). Usage: !work"""
        if not await self._gate(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        now  = datetime.datetime.utcnow()
        if data["work_at"]:
            try:
                last = datetime.datetime.fromisoformat(data["work_at"])
                diff = now - last
                if diff.total_seconds() < 3600:
                    remaining = 3600 - diff.total_seconds()
                    m = int(remaining // 60)
                    s = int(remaining % 60)
                    return await ctx.send(embed=emb.warning(
                        f"You need a break!\nWork available in **{m}m {s}s**."
                    ))
            except ValueError:
                pass
        amount  = random.randint(gs.work_min, gs.work_max)
        new_bal = await _add_balance(ctx.author.id, ctx.guild.id, amount)
        await db.execute(
            "UPDATE users SET work_at = ? WHERE user_id = ? AND guild_id = ?",
            (now.isoformat(), ctx.author.id, ctx.guild.id),
        )
        await db.record_transaction(ctx.guild.id, ctx.author.id, "work", amount, new_bal)
        response = random.choice(WORK_RESPONSES).format(amount=f"{amount:,}", symbol=gs.currency_symbol)
        await ctx.send(embed=emb.success(response, title="💼 Work Complete"))

    # ── Pay ────────────────────────────────────────────────────────────────────

    @commands.command(name="pay", aliases=["give"])
    @commands.guild_only()
    @commands.cooldown(3, 30, commands.BucketType.user)
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        """Transfer coins to another member. Usage: !pay @user <amount>"""
        if not await self._gate(ctx): return
        if member.bot: return await ctx.send(embed=emb.error("You can't pay bots."))
        if member == ctx.author: return await ctx.send(embed=emb.error("You can't pay yourself."))
        if amount <= 0: return await ctx.send(embed=emb.error("Amount must be positive."))
        if amount > 10_000_000: return await ctx.send(embed=emb.error("Maximum transfer is 10,000,000."))
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        if data["balance"] < amount:
            return await ctx.send(embed=emb.error(
                f"Insufficient funds. Wallet: {gs.currency_symbol} {data['balance']:,}"
            ))
        await _ensure_user(member.id, ctx.guild.id)
        async with db.transaction() as conn:
            row = await (await conn.execute(
                "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
                (ctx.author.id, ctx.guild.id),
            )).fetchone()
            if not row or row["balance"] < amount:
                raise ValueError("Insufficient balance")
            await conn.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
                (amount, ctx.author.id, ctx.guild.id),
            )
            await conn.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
                (amount, member.id, ctx.guild.id),
            )
        await ctx.send(embed=emb.build(
            title="💸 Transfer Complete",
            color=discord.Color.green(),
            fields=[
                ("From",   ctx.author.mention,                 True),
                ("To",     member.mention,                     True),
                ("Amount", f"{gs.currency_symbol} {amount:,}", True),
            ],
        ))

    # ── Rob ────────────────────────────────────────────────────────────────────

    @commands.command(name="rob")
    @commands.guild_only()
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def rob(self, ctx: commands.Context, member: discord.Member) -> None:
        """Attempt to rob another member (40% chance). Usage: !rob @user"""
        if not await self._gate(ctx): return
        if member.bot or member == ctx.author:
            return await ctx.send(embed=emb.error("Invalid target."))
        lock = _rob_lock(ctx.author.id, ctx.guild.id)
        if lock.locked():
            return await ctx.send(embed=emb.error("You're already attempting a robbery!"))
        async with lock:
            gs     = await GuildSettings.get(ctx.guild.id)
            victim = await _ensure_user(member.id, ctx.guild.id)
            robber = await _ensure_user(ctx.author.id, ctx.guild.id)
            if victim["balance"] < _ROB_MIN_VICTIM_BAL:
                return await ctx.send(embed=emb.warning(
                    f"{member.mention} doesn't have enough to rob "
                    f"(min {gs.currency_symbol} {_ROB_MIN_VICTIM_BAL:,})."
                ))
            if random.random() < _ROB_WIN_CHANCE:
                stolen = random.randint(
                    max(1, victim["balance"] // 10),
                    min(victim["balance"] // 2, _ROB_MAX_STEAL),
                )
                async with db.transaction() as conn:
                    await conn.execute(
                        "UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ? AND guild_id = ?",
                        (stolen, member.id, ctx.guild.id),
                    )
                    await conn.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
                        (stolen, ctx.author.id, ctx.guild.id),
                    )
                await ctx.send(embed=emb.build(
                    title="🦹 Robbery Successful!",
                    description=f"You stole **{gs.currency_symbol} {stolen:,}** from {member.mention}!",
                    color=discord.Color.dark_green(),
                ))
            else:
                fine    = max(50, min(int(robber["balance"] * _ROB_FINE_PERCENT), 2000))
                new_bal = await _add_balance(ctx.author.id, ctx.guild.id, -fine)
                await ctx.send(embed=emb.build(
                    title="🚔 Caught!",
                    description=(
                        f"Failed to rob {member.mention}. Fined **{gs.currency_symbol} {fine:,}**!\n"
                        f"Remaining wallet: {gs.currency_symbol} {new_bal:,}"
                    ),
                    color=discord.Color.red(),
                ))

    # ── Deposit / Withdraw ─────────────────────────────────────────────────────

    @commands.command(name="deposit", aliases=["dep"])
    @commands.guild_only()
    async def deposit(self, ctx: commands.Context, amount: str = "all") -> None:
        """Deposit coins into your bank. Usage: !deposit [amount|all]"""
        if not await self._gate(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        amt  = data["balance"] if amount.lower() == "all" else int(amount) if amount.isdigit() else -1
        if amt <= 0 or amt > data["balance"]:
            return await ctx.send(embed=emb.error(
                f"Invalid amount. Wallet: {gs.currency_symbol} {data['balance']:,}"
            ))
        await db.execute(
            "UPDATE users SET balance = balance - ?, bank = bank + ? WHERE user_id = ? AND guild_id = ?",
            (amt, amt, ctx.author.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"Deposited **{gs.currency_symbol} {amt:,}** to your bank."))

    @commands.command(name="withdraw", aliases=["with"])
    @commands.guild_only()
    async def withdraw(self, ctx: commands.Context, amount: str = "all") -> None:
        """Withdraw coins from your bank. Usage: !withdraw [amount|all]"""
        if not await self._gate(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        amt  = data["bank"] if amount.lower() == "all" else int(amount) if amount.isdigit() else -1
        if amt <= 0 or amt > data["bank"]:
            return await ctx.send(embed=emb.error(
                f"Invalid amount. Bank: {gs.currency_symbol} {data['bank']:,}"
            ))
        await db.execute(
            "UPDATE users SET balance = balance + ?, bank = bank - ? WHERE user_id = ? AND guild_id = ?",
            (amt, amt, ctx.author.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"Withdrew **{gs.currency_symbol} {amt:,}** from your bank."))

    # ── Leaderboard ────────────────────────────────────────────────────────────

    @commands.command(name="richlist", aliases=["leaderboard", "lb"])
    @commands.guild_only()
    async def richlist(self, ctx: commands.Context) -> None:
        """Show top 10 wealthiest members. Usage: !richlist"""
        if not await self._gate(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        rows = await db.fetchall(
            "SELECT user_id, balance + bank AS total FROM users WHERE guild_id = ? ORDER BY total DESC LIMIT 10",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No economy data yet."))
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, row in enumerate(rows):
            medal  = medals[i] if i < 3 else f"**{i + 1}.**"
            guild  = ctx.guild
            try:
                member = await guild.fetch_member(row["user_id"])
                name   = member.display_name
            except Exception:
                name = f"User {row['user_id']}"
            lines.append(f"{medal} {name} — {gs.currency_symbol} {row['total']:,}")
        await ctx.send(embed=emb.build(
            title="💰 Wealth Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        ))

    # ── Admin ──────────────────────────────────────────────────────────────────

    @commands.command(name="addmoney")
    @require_admin()
    @commands.guild_only()
    async def addmoney(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        """Add coins to a member's wallet. Usage: !addmoney @user <amount>"""
        if amount <= 0 or amount > 100_000_000:
            return await ctx.send(embed=emb.error("Amount must be between 1 and 100,000,000."))
        await _ensure_user(member.id, ctx.guild.id)
        new_bal = await _add_balance(member.id, ctx.guild.id, amount)
        gs = await GuildSettings.get(ctx.guild.id)
        await db.record_transaction(ctx.guild.id, member.id, "admin_add", amount, new_bal, {"by": ctx.author.id})
        await ctx.send(embed=emb.success(
            f"Added **{gs.currency_symbol} {amount:,}** to {member.mention}.\nNew wallet: {gs.currency_symbol} {new_bal:,}"
        ))

    @commands.command(name="removemoney")
    @require_admin()
    @commands.guild_only()
    async def removemoney(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        """Remove coins from a member's wallet. Usage: !removemoney @user <amount>"""
        if amount <= 0:
            return await ctx.send(embed=emb.error("Amount must be positive."))
        await _ensure_user(member.id, ctx.guild.id)
        new_bal = await _add_balance(member.id, ctx.guild.id, -amount)
        gs = await GuildSettings.get(ctx.guild.id)
        await ctx.send(embed=emb.success(
            f"Removed **{gs.currency_symbol} {amount:,}** from {member.mention}.\nNew wallet: {gs.currency_symbol} {new_bal:,}"
        ))

    @commands.command(name="resetbalance")
    @require_admin()
    @commands.guild_only()
    async def resetbalance(self, ctx: commands.Context, member: discord.Member) -> None:
        """Reset a member's economy data. Usage: !resetbalance @user"""
        await db.execute(
            "UPDATE users SET balance = 0, bank = 0, daily_at = NULL, work_at = NULL WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"Economy data reset for {member.mention}."))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
    log.info("Economy cog loaded")
