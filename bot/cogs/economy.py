# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Economy Cog
# Commands: balance, daily, work, pay, rob, deposit, withdraw,
#           richlist, addmoney, removemoney, resetbalance
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import random

import discord
from discord import app_commands
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.permissions import require_admin
from core.constants import WORK_RESPONSES
import core.embeds as emb
from core.logger import get_logger

log = get_logger("economy")

_ROBBER_WIN_CHANCE = 0.4     # 40% success on rob
_ROB_FINE_PERCENT  = 0.25    # 25% of balance fined on failed rob


async def _ensure_user(user_id: int, guild_id: int) -> dict:
    row = await db.fetchone(
        "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    if row is None:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?,?)",
            (user_id, guild_id),
        )
        row = await db.fetchone(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
    return row


async def _add_balance(user_id: int, guild_id: int, amount: int) -> int:
    await db.execute(
        "UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ? AND guild_id = ?",
        (amount, user_id, guild_id),
    )
    row = await db.fetchone(
        "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    return row["balance"] if row else 0


class Economy(commands.Cog, name="Economy"):
    """Virtual economy commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _check_enabled(self, ctx: commands.Context) -> bool:
        gs = await GuildSettings.get(ctx.guild.id)
        if not gs.economy_enabled:
            await ctx.send(embed=emb.error("The economy system is disabled on this server."))
            return False
        return True

    # ── Balance ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="balance", aliases=["bal", "wallet"], description="Check your or another member's balance")
    @app_commands.describe(member="Member to check (defaults to you)")
    @commands.guild_only()
    async def balance(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        if not await self._check_enabled(ctx): return
        target = member or ctx.author
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(target.id, ctx.guild.id)
        embed = emb.build(
            title=f"💰 {target.display_name}'s Wallet",
            color=discord.Color.gold(),
            thumbnail=target.display_avatar.url,
            fields=[
                ("Wallet", f"{gs.currency_symbol} {data['balance']:,}", True),
                ("Bank",   f"{gs.currency_symbol} {data['bank']:,}",    True),
                ("Total",  f"{gs.currency_symbol} {data['balance'] + data['bank']:,}", True),
            ],
        )
        await ctx.send(embed=embed)

    # ── Daily ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="daily", description="Claim your daily coins")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def daily(self, ctx: commands.Context) -> None:
        if not await self._check_enabled(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        now  = datetime.datetime.utcnow()

        if data["daily_at"]:
            last = datetime.datetime.fromisoformat(data["daily_at"])
            diff = now - last
            if diff.total_seconds() < 86400:
                remaining = 86400 - diff.total_seconds()
                h, rem = divmod(int(remaining), 3600)
                m = rem // 60
                return await ctx.send(
                    embed=emb.warning(f"You already claimed your daily reward!\nNext claim in **{h}h {m}m**.")
                )

        amount = gs.daily_amount
        await db.execute(
            "UPDATE users SET balance = balance + ?, daily_at = ? WHERE user_id = ? AND guild_id = ?",
            (amount, now.isoformat(), ctx.author.id, ctx.guild.id),
        )
        embed = emb.build(
            title="🎁 Daily Reward",
            description=f"You claimed **{gs.currency_symbol} {amount:,}**!",
            color=discord.Color.gold(),
            author=ctx.author,
        )
        await ctx.send(embed=embed)

    # ── Work ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="work", description="Work to earn coins (1 hour cooldown)")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def work(self, ctx: commands.Context) -> None:
        if not await self._check_enabled(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        now  = datetime.datetime.utcnow()

        if data["work_at"]:
            last = datetime.datetime.fromisoformat(data["work_at"])
            diff = now - last
            if diff.total_seconds() < 3600:
                remaining = 3600 - diff.total_seconds()
                m = int(remaining // 60)
                s = int(remaining % 60)
                return await ctx.send(
                    embed=emb.warning(f"You need a break!\nNext work available in **{m}m {s}s**.")
                )

        amount = random.randint(gs.work_min, gs.work_max)
        await db.execute(
            "UPDATE users SET balance = balance + ?, work_at = ? WHERE user_id = ? AND guild_id = ?",
            (amount, now.isoformat(), ctx.author.id, ctx.guild.id),
        )
        response = random.choice(WORK_RESPONSES).format(amount=f"{amount:,}", symbol=gs.currency_symbol)
        await ctx.send(embed=emb.success(response, title="💼 Work"))

    # ── Pay ────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="pay", aliases=["give"], description="Transfer coins to another member")
    @app_commands.describe(member="Recipient", amount="Amount to send")
    @commands.guild_only()
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        if not await self._check_enabled(ctx): return
        if member.bot:
            return await ctx.send(embed=emb.error("You can't pay bots."))
        if member == ctx.author:
            return await ctx.send(embed=emb.error("You can't pay yourself."))
        if amount <= 0:
            return await ctx.send(embed=emb.error("Amount must be positive."))
        gs = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        if data["balance"] < amount:
            return await ctx.send(
                embed=emb.error(f"You don't have enough! Your wallet: {gs.currency_symbol} {data['balance']:,}")
            )
        await _ensure_user(member.id, ctx.guild.id)
        await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
            (amount, ctx.author.id, ctx.guild.id),
        )
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
            (amount, member.id, ctx.guild.id),
        )
        embed = emb.build(
            title="💸 Transfer Complete",
            color=discord.Color.green(),
            fields=[
                ("From",   ctx.author.mention,                        True),
                ("To",     member.mention,                            True),
                ("Amount", f"{gs.currency_symbol} {amount:,}",       True),
            ],
        )
        await ctx.send(embed=embed)

    # ── Rob ────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="rob", description="Attempt to rob another member (risky!)")
    @app_commands.describe(member="Member to rob")
    @commands.guild_only()
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def rob(self, ctx: commands.Context, member: discord.Member) -> None:
        if not await self._check_enabled(ctx): return
        if member.bot or member == ctx.author:
            return await ctx.send(embed=emb.error("You can't rob that person."))
        gs         = await GuildSettings.get(ctx.guild.id)
        victim     = await _ensure_user(member.id, ctx.guild.id)
        robber     = await _ensure_user(ctx.author.id, ctx.guild.id)

        if victim["balance"] < 100:
            return await ctx.send(embed=emb.warning(f"{member.mention} doesn't have enough to rob (minimum 100 {gs.currency_symbol})."))

        if random.random() < _ROBBER_WIN_CHANCE:
            stolen = random.randint(1, min(victim["balance"] // 2, 5000))
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
                (stolen, member.id, ctx.guild.id),
            )
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
                (stolen, ctx.author.id, ctx.guild.id),
            )
            await ctx.send(
                embed=emb.build(
                    title="🦹 Rob Successful!",
                    description=f"You stole **{gs.currency_symbol} {stolen:,}** from {member.mention}!",
                    color=discord.Color.dark_green(),
                )
            )
        else:
            fine = int(robber["balance"] * _ROB_FINE_PERCENT)
            fine = max(fine, 50)
            await db.execute(
                "UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ? AND guild_id = ?",
                (fine, ctx.author.id, ctx.guild.id),
            )
            await ctx.send(
                embed=emb.build(
                    title="🚔 You Got Caught!",
                    description=f"You failed to rob {member.mention} and were fined **{gs.currency_symbol} {fine:,}**!",
                    color=discord.Color.red(),
                )
            )

    # ── Deposit / Withdraw ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="deposit", aliases=["dep"], description="Deposit coins into your bank")
    @app_commands.describe(amount="Amount to deposit (or 'all')")
    @commands.guild_only()
    async def deposit(self, ctx: commands.Context, amount: str = "all") -> None:
        if not await self._check_enabled(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        amt  = data["balance"] if amount.lower() == "all" else int(amount)
        if amt <= 0 or amt > data["balance"]:
            return await ctx.send(embed=emb.error(f"Invalid amount. You have {gs.currency_symbol} {data['balance']:,} in your wallet."))
        await db.execute(
            "UPDATE users SET balance = balance - ?, bank = bank + ? WHERE user_id = ? AND guild_id = ?",
            (amt, amt, ctx.author.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"Deposited {gs.currency_symbol} {amt:,} into your bank."))

    @commands.hybrid_command(name="withdraw", aliases=["with"], description="Withdraw coins from your bank")
    @app_commands.describe(amount="Amount to withdraw (or 'all')")
    @commands.guild_only()
    async def withdraw(self, ctx: commands.Context, amount: str = "all") -> None:
        if not await self._check_enabled(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        data = await _ensure_user(ctx.author.id, ctx.guild.id)
        amt  = data["bank"] if amount.lower() == "all" else int(amount)
        if amt <= 0 or amt > data["bank"]:
            return await ctx.send(embed=emb.error(f"Invalid amount. You have {gs.currency_symbol} {data['bank']:,} in your bank."))
        await db.execute(
            "UPDATE users SET balance = balance + ?, bank = bank - ? WHERE user_id = ? AND guild_id = ?",
            (amt, amt, ctx.author.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"Withdrew {gs.currency_symbol} {amt:,} from your bank."))

    # ── Rich list ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="richlist", aliases=["leaderboard", "lb"], description="Top 10 richest members")
    @commands.guild_only()
    async def richlist(self, ctx: commands.Context) -> None:
        if not await self._check_enabled(ctx): return
        gs   = await GuildSettings.get(ctx.guild.id)
        rows = await db.fetchall(
            "SELECT user_id, balance + bank AS total FROM users WHERE guild_id = ? ORDER BY total DESC LIMIT 10",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No data yet."))
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            medal  = medals[i] if i < 3 else f"**{i+1}.**"
            member = ctx.guild.get_member(row["user_id"])
            name   = member.display_name if member else f"Unknown ({row['user_id']})"
            lines.append(f"{medal} {name} — {gs.currency_symbol} {row['total']:,}")
        await ctx.send(embed=emb.build(title="💰 Rich List", description="\n".join(lines), color=discord.Color.gold()))

    # ── Admin economy commands ─────────────────────────────────────────────────

    @commands.hybrid_command(name="addmoney", description="[Admin] Add coins to a member's wallet")
    @app_commands.describe(member="Member", amount="Amount to add")
    @require_admin()
    @commands.guild_only()
    async def addmoney(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        await _ensure_user(member.id, ctx.guild.id)
        new_bal = await _add_balance(member.id, ctx.guild.id, amount)
        gs = await GuildSettings.get(ctx.guild.id)
        await ctx.send(embed=emb.success(f"Added {gs.currency_symbol} {amount:,} to {member.mention}. New balance: {gs.currency_symbol} {new_bal:,}"))

    @commands.hybrid_command(name="removemoney", description="[Admin] Remove coins from a member's wallet")
    @app_commands.describe(member="Member", amount="Amount to remove")
    @require_admin()
    @commands.guild_only()
    async def removemoney(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        await _ensure_user(member.id, ctx.guild.id)
        new_bal = await _add_balance(member.id, ctx.guild.id, -amount)
        gs = await GuildSettings.get(ctx.guild.id)
        await ctx.send(embed=emb.success(f"Removed {gs.currency_symbol} {amount:,} from {member.mention}. New balance: {gs.currency_symbol} {new_bal:,}"))

    @commands.hybrid_command(name="resetbalance", description="[Admin] Reset a member's economy data")
    @app_commands.describe(member="Member to reset")
    @require_admin()
    @commands.guild_only()
    async def resetbalance(self, ctx: commands.Context, member: discord.Member) -> None:
        await db.execute(
            "UPDATE users SET balance = 0, bank = 0, daily_at = NULL, work_at = NULL WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"Economy data reset for {member.mention}"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
    log.info("Economy cog loaded")
