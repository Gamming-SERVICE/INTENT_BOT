# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Leveling Cog
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import math
import time

import discord
from discord import app_commands
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.cache import xp_cooldowns
from core.permissions import require_admin
import core.embeds as emb
from core.logger import get_logger

log = get_logger("leveling")


# ── XP formula ────────────────────────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    """XP required to complete the given level."""
    return 5 * (level ** 2) + 50 * level + 100


def level_from_total_xp(total_xp: int) -> tuple[int, int]:
    """Return (level, xp_into_current_level) from total XP."""
    level = 1
    xp = total_xp
    while xp >= xp_for_level(level):
        xp -= xp_for_level(level)
        level += 1
    return level, xp


def xp_progress_bar(current: int, required: int, length: int = 20) -> str:
    filled = int((current / max(required, 1)) * length)
    bar    = "█" * filled + "░" * (length - filled)
    return f"`{bar}` {current:,}/{required:,}"


class Leveling(commands.Cog, name="Leveling"):
    """XP and level system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── on_message XP handling (called from main bot event) ───────────────────

    async def process_message_xp(self, message: discord.Message) -> None:
        """Award XP for a message. Called by the on_message event in main.py."""
        if not message.guild or message.author.bot:
            return

        gs = await GuildSettings.get(message.guild.id)
        if not gs.leveling_enabled:
            return

        key = (message.author.id, message.guild.id)
        now = time.monotonic()

        # Per-user, per-guild cooldown
        if key in xp_cooldowns and now - xp_cooldowns[key] < gs.xp_cooldown:
            return
        xp_cooldowns[key] = now

        import random
        xp_gain = random.randint(gs.xp_per_message_min, gs.xp_per_message_max)

        # Ensure user row exists
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?,?)",
            (message.author.id, message.guild.id),
        )
        row = await db.fetchone(
            "SELECT xp, level, messages FROM users WHERE user_id = ? AND guild_id = ?",
            (message.author.id, message.guild.id),
        )
        old_xp    = row["xp"]
        old_level = row["level"]
        new_xp    = old_xp + xp_gain
        new_level, _ = level_from_total_xp(new_xp)

        await db.execute(
            "UPDATE users SET xp = ?, level = ?, messages = messages + 1 WHERE user_id = ? AND guild_id = ?",
            (new_xp, new_level, message.author.id, message.guild.id),
        )

        if new_level > old_level:
            await self._announce_level_up(message, new_level, gs)

    async def _announce_level_up(self, message: discord.Message, level: int, gs: GuildSettings) -> None:
        text = gs.level_up_message.format(user=message.author.mention, level=level)
        embed = emb.build(title="🎉 Level Up!", description=text, color=discord.Color.gold())
        target_id = gs.level_up_channel
        if target_id:
            channel = message.guild.get_channel(target_id)
        else:
            channel = message.channel
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="rank", aliases=["level", "xp"], description="Check your rank and XP progress")
    @app_commands.describe(member="Member to check (defaults to you)")
    @commands.guild_only()
    async def rank(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        gs     = await GuildSettings.get(ctx.guild.id)
        if not gs.leveling_enabled:
            return await ctx.send(embed=emb.error("Leveling is disabled on this server."))
        target = member or ctx.author
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?,?)",
            (target.id, ctx.guild.id),
        )
        row = await db.fetchone(
            "SELECT xp, messages FROM users WHERE user_id = ? AND guild_id = ?",
            (target.id, ctx.guild.id),
        )
        total_xp = row["xp"]
        msgs     = row["messages"]
        level, current_xp = level_from_total_xp(total_xp)
        required          = xp_for_level(level)
        bar               = xp_progress_bar(current_xp, required)

        # Rank position
        rank_row = await db.fetchone(
            "SELECT COUNT(*) AS r FROM users WHERE guild_id = ? AND xp > ?",
            (ctx.guild.id, total_xp),
        )
        rank_pos = (rank_row["r"] + 1) if rank_row else 1

        embed = emb.build(
            title=f"⭐ {target.display_name}'s Rank",
            color=discord.Color.blurple(),
            thumbnail=target.display_avatar.url,
            fields=[
                ("Level",    str(level),             True),
                ("Rank",     f"#{rank_pos}",         True),
                ("Messages", f"{msgs:,}",            True),
                ("XP",       bar,                    False),
                ("Total XP", f"{total_xp:,}",        True),
            ],
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leveltop", aliases=["xplb"], description="Top 10 most leveled members")
    @commands.guild_only()
    async def leveltop(self, ctx: commands.Context) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        if not gs.leveling_enabled:
            return await ctx.send(embed=emb.error("Leveling is disabled on this server."))
        rows = await db.fetchall(
            "SELECT user_id, xp, level FROM users WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No data yet."))
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, row in enumerate(rows):
            medal  = medals[i] if i < 3 else f"**{i+1}.**"
            member = ctx.guild.get_member(row["user_id"])
            name   = member.display_name if member else f"Unknown ({row['user_id']})"
            lines.append(f"{medal} {name} — Lv. {row['level']} ({row['xp']:,} XP)")
        await ctx.send(
            embed=emb.build(title="⭐ Level Leaderboard", description="\n".join(lines), color=discord.Color.blurple())
        )

    @commands.hybrid_command(name="setxp", description="[Admin] Set a member's total XP")
    @app_commands.describe(member="Member", xp="Total XP to set")
    @require_admin()
    @commands.guild_only()
    async def setxp(self, ctx: commands.Context, member: discord.Member, xp: int) -> None:
        if xp < 0:
            return await ctx.send(embed=emb.error("XP cannot be negative."))
        level, _ = level_from_total_xp(xp)
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?,?)",
            (member.id, ctx.guild.id),
        )
        await db.execute(
            "UPDATE users SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?",
            (xp, level, member.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"Set {member.mention}'s XP to **{xp:,}** (Level {level})"))

    @commands.hybrid_command(name="resetxp", description="[Admin] Reset a member's XP and level")
    @app_commands.describe(member="Member to reset")
    @require_admin()
    @commands.guild_only()
    async def resetxp(self, ctx: commands.Context, member: discord.Member) -> None:
        await db.execute(
            "UPDATE users SET xp = 0, level = 1, messages = 0 WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"XP data reset for {member.mention}"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leveling(bot))
    log.info("Leveling cog loaded")
