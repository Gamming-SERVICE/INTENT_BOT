# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Moderation Cog
# Commands: ban, unban, kick, mute, unmute, timeout, warn, warnings,
#           clearwarns, purge, slowmode, lock, unlock, nick, role, modlogs
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.permissions import require_mod, require_admin, can_moderate, bot_can_moderate
import core.embeds as emb
from core.logger import get_logger

log = get_logger("moderation")


def parse_duration(s: str) -> int | None:
    """Parse a duration string like 10m, 2h, 1d. Returns total seconds or None."""
    pattern = re.compile(r"(\d+)([smhdw])")
    matches = pattern.findall(s.lower())
    if not matches:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return sum(int(v) * units[u] for v, u in matches)


async def _log_mod_action(
    guild_id: int,
    user_id: int,
    moderator_id: int,
    action: str,
    reason: str | None,
    duration: str | None = None,
) -> None:
    await db.execute(
        """INSERT INTO mod_logs (guild_id, user_id, moderator_id, action, reason, duration)
           VALUES (?,?,?,?,?,?)""",
        (guild_id, user_id, moderator_id, action, reason or "No reason provided", duration),
    )


async def _send_log(guild: discord.Guild, embed: discord.Embed) -> None:
    gs = await GuildSettings.get(guild.id)
    if not gs.logging_enabled:
        return
    cid = gs.log_channel
    if not cid:
        return
    ch = guild.get_channel(cid)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.HTTPException:
            pass


class Moderation(commands.Cog, name="Moderation"):
    """Server moderation commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Ban ────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for the ban", delete_days="Days of messages to delete (0–7)")
    @require_mod()
    @commands.guild_only()
    async def ban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        delete_days: int = 0,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        if not bot_can_moderate(ctx.guild, member):
            return await ctx.send(embed=emb.error("I cannot ban this member (check my role position)."))
        try:
            await member.send(embed=emb.error(f"You have been **banned** from **{ctx.guild.name}**.\nReason: {reason}"))
        except Exception:
            pass
        await member.ban(reason=f"{ctx.author}: {reason}", delete_message_days=min(delete_days, 7))
        await _log_mod_action(ctx.guild.id, member.id, ctx.author.id, "ban", reason)
        embed = emb.build(
            title="🔨 Member Banned",
            color=discord.Color.red(),
            fields=[
                ("User",       f"{member} ({member.id})", True),
                ("Moderator",  ctx.author.mention,        True),
                ("Reason",     reason,                    False),
            ],
        )
        await ctx.send(embed=embed)
        await _send_log(ctx.guild, embed)

    # ── Unban ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="unban", description="Unban a user by ID or username#discriminator")
    @app_commands.describe(user_id="User ID to unban", reason="Reason for unban")
    @require_mod()
    @commands.guild_only()
    async def unban(self, ctx: commands.Context, user_id: str, *, reason: str = "No reason provided") -> None:
        try:
            uid = int(user_id)
            user = await self.bot.fetch_user(uid)
            await ctx.guild.unban(user, reason=f"{ctx.author}: {reason}")
        except (ValueError, discord.NotFound):
            return await ctx.send(embed=emb.error("User not found or not banned."))
        embed = emb.build(
            title="✅ Member Unbanned",
            color=discord.Color.green(),
            fields=[
                ("User",      f"{user} ({user.id})", True),
                ("Moderator", ctx.author.mention,    True),
                ("Reason",    reason,                False),
            ],
        )
        await ctx.send(embed=embed)
        await _send_log(ctx.guild, embed)

    # ── Kick ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @require_mod()
    @commands.guild_only()
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        if not bot_can_moderate(ctx.guild, member):
            return await ctx.send(embed=emb.error("I cannot kick this member (check my role position)."))
        try:
            await member.send(embed=emb.error(f"You have been **kicked** from **{ctx.guild.name}**.\nReason: {reason}"))
        except Exception:
            pass
        await member.kick(reason=f"{ctx.author}: {reason}")
        await _log_mod_action(ctx.guild.id, member.id, ctx.author.id, "kick", reason)
        embed = emb.build(
            title="👢 Member Kicked",
            color=discord.Color.orange(),
            fields=[
                ("User",      f"{member} ({member.id})", True),
                ("Moderator", ctx.author.mention,        True),
                ("Reason",    reason,                    False),
            ],
        )
        await ctx.send(embed=embed)
        await _send_log(ctx.guild, embed)

    # ── Timeout ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="timeout", description="Timeout a member (e.g. 10m, 1h, 2d)")
    @app_commands.describe(member="Member to timeout", duration="Duration (10m, 1h, 2d, etc.)", reason="Reason")
    @require_mod()
    @commands.guild_only()
    async def timeout_member(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        *,
        reason: str = "No reason provided",
    ) -> None:
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        seconds = parse_duration(duration)
        if seconds is None or seconds < 1:
            return await ctx.send(embed=emb.error("Invalid duration. Use format like `10m`, `1h`, `2d`."))
        if seconds > 28 * 86400:
            return await ctx.send(embed=emb.error("Timeout cannot exceed 28 days."))
        until = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
        await member.timeout(until, reason=f"{ctx.author}: {reason}")
        await _log_mod_action(ctx.guild.id, member.id, ctx.author.id, "timeout", reason, duration)
        embed = emb.build(
            title="⏰ Member Timed Out",
            color=discord.Color.yellow(),
            fields=[
                ("User",      f"{member} ({member.id})", True),
                ("Moderator", ctx.author.mention,        True),
                ("Duration",  duration,                  True),
                ("Expires",   f"<t:{int(until.timestamp())}:R>", True),
                ("Reason",    reason,                    False),
            ],
        )
        await ctx.send(embed=embed)
        await _send_log(ctx.guild, embed)

    @commands.hybrid_command(name="untimeout", description="Remove a member's timeout")
    @app_commands.describe(member="Member to un-timeout")
    @require_mod()
    @commands.guild_only()
    async def untimeout(self, ctx: commands.Context, member: discord.Member) -> None:
        await member.timeout(None)
        embed = emb.success(f"Timeout removed from {member.mention}")
        await ctx.send(embed=embed)

    # ── Mute (role-based) ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="mute", description="Mute a member using the mute role")
    @app_commands.describe(member="Member to mute", reason="Reason")
    @require_mod()
    @commands.guild_only()
    async def mute(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        if not gs.mute_role:
            return await ctx.send(embed=emb.error("No mute role configured. Use `/setmuterole` first."))
        role = ctx.guild.get_role(gs.mute_role)
        if not role:
            return await ctx.send(embed=emb.error("Mute role not found — it may have been deleted."))
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        await member.add_roles(role, reason=f"{ctx.author}: {reason}")
        await _log_mod_action(ctx.guild.id, member.id, ctx.author.id, "mute", reason)
        embed = emb.build(
            title="🔇 Member Muted",
            color=discord.Color.dark_grey(),
            fields=[
                ("User",      f"{member} ({member.id})", True),
                ("Moderator", ctx.author.mention,        True),
                ("Reason",    reason,                    False),
            ],
        )
        await ctx.send(embed=embed)
        await _send_log(ctx.guild, embed)

    @commands.hybrid_command(name="unmute", description="Unmute a member")
    @app_commands.describe(member="Member to unmute")
    @require_mod()
    @commands.guild_only()
    async def unmute(self, ctx: commands.Context, member: discord.Member) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        if not gs.mute_role:
            return await ctx.send(embed=emb.error("No mute role configured."))
        role = ctx.guild.get_role(gs.mute_role)
        if role and role in member.roles:
            await member.remove_roles(role)
            await ctx.send(embed=emb.success(f"{member.mention} has been unmuted."))
        else:
            await ctx.send(embed=emb.warning(f"{member.mention} is not muted."))

    # ── Warn ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @require_mod()
    @commands.guild_only()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
        if member.bot:
            return await ctx.send(embed=emb.error("You cannot warn a bot."))
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        await db.execute(
            "INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?,?,?,?)",
            (member.id, ctx.guild.id, ctx.author.id, reason),
        )
        cursor = await db.fetchone(
            "SELECT COUNT(*) AS c FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id),
        )
        total = cursor["c"] if cursor else 1
        try:
            await member.send(
                embed=emb.warning(f"You received a warning in **{ctx.guild.name}**.\nReason: {reason}\nTotal warnings: {total}")
            )
        except Exception:
            pass
        embed = emb.build(
            title="⚠️ Member Warned",
            color=discord.Color.yellow(),
            fields=[
                ("User",        f"{member} ({member.id})", True),
                ("Moderator",   ctx.author.mention,        True),
                ("Reason",      reason,                    False),
                ("Total Warns", str(total),                True),
            ],
        )
        await ctx.send(embed=embed)
        await _send_log(ctx.guild, embed)

    @commands.hybrid_command(name="warnings", description="Check warnings for a member")
    @app_commands.describe(member="Member to check")
    @require_mod()
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, member: discord.Member) -> None:
        rows = await db.fetchall(
            "SELECT reason, moderator_id, created_at FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC",
            (member.id, ctx.guild.id),
        )
        if not rows:
            return await ctx.send(embed=emb.info(f"{member.mention} has no warnings."))
        lines = [
            f"**{i}.** {r['reason']} — <@{r['moderator_id']}> — <t:{int(datetime.datetime.fromisoformat(r['created_at']).timestamp())}:R>"
            for i, r in enumerate(rows, 1)
        ]
        embed = emb.build(
            title=f"⚠️ Warnings — {member}",
            description="\n".join(lines[:20]),
            color=discord.Color.yellow(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearwarns", description="Clear all warnings for a member")
    @app_commands.describe(member="Member to clear warnings for")
    @require_admin()
    @commands.guild_only()
    async def clearwarns(self, ctx: commands.Context, member: discord.Member) -> None:
        await db.execute(
            "DELETE FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"All warnings cleared for {member.mention}"))

    # ── Purge ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="purge", description="Bulk-delete messages")
    @app_commands.describe(amount="Number of messages to delete (1–200)", member="Only delete messages from this member")
    @require_mod()
    @commands.guild_only()
    async def purge(self, ctx: commands.Context, amount: int, member: discord.Member | None = None) -> None:
        if not 1 <= amount <= 200:
            return await ctx.send(embed=emb.error("Amount must be between 1 and 200."))
        check = (lambda m: m.author == member) if member else None
        try:
            await ctx.message.delete()
        except Exception:
            pass
        deleted = await ctx.channel.purge(limit=amount, check=check, bulk=True)
        await ctx.send(
            embed=emb.success(f"Deleted **{len(deleted)}** messages" + (f" from {member.mention}" if member else "")),
            delete_after=5,
        )

    # ── Slowmode ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="slowmode", description="Set channel slowmode delay")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable, max 21600)")
    @require_mod()
    @commands.guild_only()
    async def slowmode(self, ctx: commands.Context, seconds: int = 0) -> None:
        if not 0 <= seconds <= 21600:
            return await ctx.send(embed=emb.error("Slowmode must be between 0 and 21600 seconds."))
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(embed=emb.success("Slowmode disabled."))
        else:
            await ctx.send(embed=emb.success(f"Slowmode set to **{seconds}s**."))

    # ── Lock / Unlock ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name="lock", description="Lock a channel (deny @everyone from sending)")
    @app_commands.describe(channel="Channel to lock (defaults to current)", reason="Reason")
    @require_mod()
    @commands.guild_only()
    async def lock(self, ctx: commands.Context, channel: discord.TextChannel | None = None, *, reason: str = "No reason") -> None:
        target = channel or ctx.channel
        everyone = ctx.guild.default_role
        await target.set_permissions(everyone, send_messages=False, reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=emb.success(f"🔒 {target.mention} has been locked."))

    @commands.hybrid_command(name="unlock", description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock (defaults to current)")
    @require_mod()
    @commands.guild_only()
    async def unlock(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        target = channel or ctx.channel
        everyone = ctx.guild.default_role
        await target.set_permissions(everyone, send_messages=None)
        await ctx.send(embed=emb.success(f"🔓 {target.mention} has been unlocked."))

    # ── Nickname ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="nick", description="Change a member's nickname")
    @app_commands.describe(member="Member", nickname="New nickname (leave blank to reset)")
    @require_mod()
    @commands.guild_only()
    async def nick(self, ctx: commands.Context, member: discord.Member, *, nickname: str | None = None) -> None:
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot modify someone with a higher or equal role."))
        await member.edit(nick=nickname)
        if nickname:
            await ctx.send(embed=emb.success(f"Nickname of {member.mention} changed to **{nickname}**"))
        else:
            await ctx.send(embed=emb.success(f"Nickname of {member.mention} has been reset."))

    # ── Role ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="role", description="Add or remove a role from a member")
    @app_commands.describe(member="Member", role="Role to add or remove")
    @require_mod()
    @commands.guild_only()
    async def role(self, ctx: commands.Context, member: discord.Member, role: discord.Role) -> None:
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=emb.error("I cannot manage that role (it's above mine)."))
        if role in member.roles:
            await member.remove_roles(role)
            await ctx.send(embed=emb.success(f"Removed {role.mention} from {member.mention}"))
        else:
            await member.add_roles(role)
            await ctx.send(embed=emb.success(f"Added {role.mention} to {member.mention}"))

    # ── Mod logs ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="modlogs", description="View recent mod actions for a user")
    @app_commands.describe(member="Member to look up")
    @require_mod()
    @commands.guild_only()
    async def modlogs(self, ctx: commands.Context, member: discord.Member) -> None:
        rows = await db.fetchall(
            "SELECT action, reason, moderator_id, created_at FROM mod_logs WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC LIMIT 15",
            (member.id, ctx.guild.id),
        )
        if not rows:
            return await ctx.send(embed=emb.info(f"No mod logs found for {member.mention}"))
        lines = [
            f"**{i}.** `{r['action'].upper()}` — {r['reason']} — <@{r['moderator_id']}> — <t:{int(datetime.datetime.fromisoformat(r['created_at']).timestamp())}:R>"
            for i, r in enumerate(rows, 1)
        ]
        embed = emb.build(
            title=f"📋 Mod Logs — {member}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            thumbnail=member.display_avatar.url,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
    log.info("Moderation cog loaded")
