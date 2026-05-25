# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Moderation Cog
#                   PREFIX-ONLY | No slash commands
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import re

import discord
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.permissions import require_mod, require_admin, can_moderate, bot_can_moderate
import core.embeds as emb
from core.logger import get_logger

log = get_logger("moderation")


def parse_duration(s: str) -> int | None:
    """Parse 10m, 2h, 1d, 1w → seconds."""
    matches = re.findall(r"(\d+)([smhdw])", s.lower())
    if not matches:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return sum(int(v) * units[u] for v, u in matches)


async def _log_mod_action(
    guild_id: int, user_id: int, mod_id: int, action: str, reason: str, duration: str = None
) -> None:
    await db.execute(
        "INSERT INTO mod_logs (guild_id, user_id, moderator_id, action, reason, duration) VALUES (?,?,?,?,?,?)",
        (guild_id, user_id, mod_id, action, reason or "No reason provided", duration),
    )


async def _send_to_log(guild: discord.Guild, embed: discord.Embed) -> None:
    gs = await GuildSettings.fetch(guild.id)
    if not gs.logging_enabled or not gs.log_channel:
        return
    ch = guild.get_channel(gs.log_channel)
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

    @commands.command(name="ban")
    @require_mod()
    @commands.guild_only()
    async def ban(self, ctx: commands.Context, member: discord.Member, delete_days: int = 0, *, reason: str = "No reason provided") -> None:
        """Ban a member. Usage: !ban @user [delete_days] [reason]"""
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        if not bot_can_moderate(ctx.guild, member):
            return await ctx.send(embed=emb.error("I cannot ban this member — check my role position."))
        try:
            await member.send(embed=emb.error(
                f"You have been **banned** from **{ctx.guild.name}**.\nReason: {reason}"
            ))
        except Exception:
            pass
        await member.ban(reason=f"{ctx.author}: {reason}", delete_message_days=min(max(delete_days, 0), 7))
        await _log_mod_action(ctx.guild.id, member.id, ctx.author.id, "ban", reason)
        embed = emb.build(
            title="🔨 Member Banned",
            color=discord.Color.red(),
            fields=[
                ("User",      f"{member} ({member.id})", True),
                ("Moderator", ctx.author.mention,        True),
                ("Reason",    reason,                    False),
            ],
        )
        await ctx.send(embed=embed)
        await _send_to_log(ctx.guild, embed)

    # ── Unban ──────────────────────────────────────────────────────────────────

    @commands.command(name="unban")
    @require_mod()
    @commands.guild_only()
    async def unban(self, ctx: commands.Context, user_id: str, *, reason: str = "No reason provided") -> None:
        """Unban a user by ID. Usage: !unban <user_id> [reason]"""
        try:
            uid  = int(user_id)
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
        await _send_to_log(ctx.guild, embed)

    # ── Kick ───────────────────────────────────────────────────────────────────

    @commands.command(name="kick")
    @require_mod()
    @commands.guild_only()
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        """Kick a member. Usage: !kick @user [reason]"""
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        if not bot_can_moderate(ctx.guild, member):
            return await ctx.send(embed=emb.error("I cannot kick this member — check my role position."))
        try:
            await member.send(embed=emb.error(
                f"You have been **kicked** from **{ctx.guild.name}**.\nReason: {reason}"
            ))
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
        await _send_to_log(ctx.guild, embed)

    # ── Timeout ────────────────────────────────────────────────────────────────

    @commands.command(name="timeout", aliases=["to"])
    @require_mod()
    @commands.guild_only()
    async def timeout_cmd(self, ctx: commands.Context, member: discord.Member, duration: str, *, reason: str = "No reason provided") -> None:
        """Timeout a member. Usage: !timeout @user 10m [reason]"""
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        seconds = parse_duration(duration)
        if not seconds or seconds < 1:
            return await ctx.send(embed=emb.error("Invalid duration. Examples: `10m`, `1h`, `2d`"))
        if seconds > 28 * 86400:
            return await ctx.send(embed=emb.error("Timeout cannot exceed 28 days."))
        until = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
        await member.timeout(until, reason=f"{ctx.author}: {reason}")
        await _log_mod_action(ctx.guild.id, member.id, ctx.author.id, "timeout", reason, duration)
        embed = emb.build(
            title="⏰ Member Timed Out",
            color=discord.Color.yellow(),
            fields=[
                ("User",      f"{member} ({member.id})",          True),
                ("Moderator", ctx.author.mention,                  True),
                ("Duration",  duration,                            True),
                ("Expires",   f"<t:{int(until.timestamp())}:R>",  True),
                ("Reason",    reason,                              False),
            ],
        )
        await ctx.send(embed=embed)
        await _send_to_log(ctx.guild, embed)

    @commands.command(name="untimeout", aliases=["uto"])
    @require_mod()
    @commands.guild_only()
    async def untimeout(self, ctx: commands.Context, member: discord.Member) -> None:
        """Remove a member's timeout. Usage: !untimeout @user"""
        await member.timeout(None)
        await ctx.send(embed=emb.success(f"Timeout removed from {member.mention}."))

    # ── Mute (role-based) ──────────────────────────────────────────────────────

    @commands.command(name="mute")
    @require_mod()
    @commands.guild_only()
    async def mute(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        """Mute a member using the mute role. Usage: !mute @user [reason]"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        if not gs.mute_role:
            return await ctx.send(embed=emb.error("No mute role set. Use `!setmuterole @Role` first."))
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
        await _send_to_log(ctx.guild, embed)

    @commands.command(name="unmute")
    @require_mod()
    @commands.guild_only()
    async def unmute(self, ctx: commands.Context, member: discord.Member) -> None:
        """Unmute a member. Usage: !unmute @user"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        if not gs.mute_role:
            return await ctx.send(embed=emb.error("No mute role configured."))
        role = ctx.guild.get_role(gs.mute_role)
        if role and role in member.roles:
            await member.remove_roles(role)
            await ctx.send(embed=emb.success(f"{member.mention} has been unmuted."))
        else:
            await ctx.send(embed=emb.warning(f"{member.mention} is not muted."))

    # ── Warn ───────────────────────────────────────────────────────────────────

    @commands.command(name="warn")
    @require_mod()
    @commands.guild_only()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
        """Warn a member. Usage: !warn @user <reason>"""
        if member.bot:
            return await ctx.send(embed=emb.error("You cannot warn a bot."))
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot moderate someone with a higher or equal role."))
        await db.execute(
            "INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?,?,?,?)",
            (member.id, ctx.guild.id, ctx.author.id, reason),
        )
        row = await db.fetchone(
            "SELECT COUNT(*) AS c FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id),
        )
        total = row["c"] if row else 1
        try:
            await member.send(embed=emb.warning(
                f"You received a warning in **{ctx.guild.name}**.\n"
                f"Reason: {reason}\nTotal warnings: {total}"
            ))
        except Exception:
            pass
        embed = emb.build(
            title="⚠️ Member Warned",
            color=discord.Color.yellow(),
            fields=[
                ("User",        f"{member} ({member.id})", True),
                ("Moderator",   ctx.author.mention,        True),
                ("Total Warns", str(total),                True),
                ("Reason",      reason,                    False),
            ],
        )
        await ctx.send(embed=embed)
        await _send_to_log(ctx.guild, embed)

    @commands.command(name="warnings")
    @require_mod()
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, member: discord.Member) -> None:
        """View warnings for a member. Usage: !warnings @user"""
        rows = await db.fetchall(
            "SELECT reason, moderator_id, created_at FROM warnings "
            "WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC",
            (member.id, ctx.guild.id),
        )
        if not rows:
            return await ctx.send(embed=emb.info(f"{member.mention} has no warnings."))
        lines = []
        for i, r in enumerate(rows, 1):
            try:
                dt = datetime.datetime.fromisoformat(r["created_at"])
                ts = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
                time_str = f"<t:{ts}:R>"
            except Exception:
                time_str = r["created_at"]
            lines.append(f"**{i}.** {r['reason']} — <@{r['moderator_id']}> — {time_str}")
        await ctx.send(embed=emb.build(
            title=f"⚠️ Warnings — {member}",
            description="\n".join(lines[:20]),
            color=discord.Color.yellow(),
        ))

    @commands.command(name="clearwarns")
    @require_admin()
    @commands.guild_only()
    async def clearwarns(self, ctx: commands.Context, member: discord.Member) -> None:
        """Clear all warnings for a member. Usage: !clearwarns @user"""
        await db.execute(
            "DELETE FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id),
        )
        await ctx.send(embed=emb.success(f"All warnings cleared for {member.mention}."))

    # ── Purge ──────────────────────────────────────────────────────────────────

    @commands.command(name="purge", aliases=["clear", "prune"])
    @require_mod()
    @commands.guild_only()
    async def purge(self, ctx: commands.Context, amount: int, member: discord.Member = None) -> None:
        """Bulk-delete messages. Usage: !purge <amount> [@user]"""
        if not 1 <= amount <= 200:
            return await ctx.send(embed=emb.error("Amount must be between 1 and 200."))
        check = (lambda m: m.author == member) if member else None
        try:
            await ctx.message.delete()
        except Exception:
            pass
        deleted = await ctx.channel.purge(limit=amount, check=check, bulk=True)
        suffix = f" from {member.mention}" if member else ""
        await ctx.send(
            embed=emb.success(f"Deleted **{len(deleted)}** messages{suffix}."),
            delete_after=5,
        )

    # ── Slowmode ───────────────────────────────────────────────────────────────

    @commands.command(name="slowmode", aliases=["slow"])
    @require_mod()
    @commands.guild_only()
    async def slowmode(self, ctx: commands.Context, seconds: int = 0) -> None:
        """Set channel slowmode delay. Usage: !slowmode [seconds]"""
        if not 0 <= seconds <= 21600:
            return await ctx.send(embed=emb.error("Slowmode must be between 0 and 21600 seconds."))
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(embed=emb.success("Slowmode disabled."))
        else:
            await ctx.send(embed=emb.success(f"Slowmode set to **{seconds}s**."))

    # ── Lock / Unlock ──────────────────────────────────────────────────────────

    @commands.command(name="lock")
    @require_mod()
    @commands.guild_only()
    async def lock(self, ctx: commands.Context, channel: discord.TextChannel = None, *, reason: str = "No reason") -> None:
        """Lock a channel. Usage: !lock [#channel] [reason]"""
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, send_messages=False, reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=emb.success(f"🔒 {target.mention} has been locked.\nReason: {reason}"))

    @commands.command(name="unlock")
    @require_mod()
    @commands.guild_only()
    async def unlock(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        """Unlock a channel. Usage: !unlock [#channel]"""
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(embed=emb.success(f"🔓 {target.mention} has been unlocked."))

    # ── Nickname ───────────────────────────────────────────────────────────────

    @commands.command(name="nick")
    @require_mod()
    @commands.guild_only()
    async def nick(self, ctx: commands.Context, member: discord.Member, *, nickname: str = None) -> None:
        """Change a member's nickname. Usage: !nick @user [new nickname]"""
        if not can_moderate(ctx.author, member):
            return await ctx.send(embed=emb.error("You cannot modify someone with a higher or equal role."))
        await member.edit(nick=nickname)
        if nickname:
            await ctx.send(embed=emb.success(f"Nickname of {member.mention} set to **{nickname}**."))
        else:
            await ctx.send(embed=emb.success(f"Nickname of {member.mention} has been reset."))

    # ── Role add/remove ────────────────────────────────────────────────────────

    @commands.command(name="role")
    @require_mod()
    @commands.guild_only()
    async def role(self, ctx: commands.Context, member: discord.Member, role: discord.Role) -> None:
        """Add or remove a role from a member. Usage: !role @user @Role"""
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=emb.error("I cannot manage that role — it's above mine."))
        if role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            return await ctx.send(embed=emb.error("You cannot assign a role equal to or above yours."))
        if role in member.roles:
            await member.remove_roles(role)
            await ctx.send(embed=emb.success(f"Removed {role.mention} from {member.mention}."))
        else:
            await member.add_roles(role)
            await ctx.send(embed=emb.success(f"Added {role.mention} to {member.mention}."))

    # ── Mod logs ───────────────────────────────────────────────────────────────

    @commands.command(name="modlogs", aliases=["history"])
    @require_mod()
    @commands.guild_only()
    async def modlogs(self, ctx: commands.Context, member: discord.Member) -> None:
        """View mod action history for a user. Usage: !modlogs @user"""
        rows = await db.fetchall(
            "SELECT action, reason, moderator_id, created_at FROM mod_logs "
            "WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC LIMIT 15",
            (member.id, ctx.guild.id),
        )
        if not rows:
            return await ctx.send(embed=emb.info(f"No mod logs found for {member.mention}."))
        lines = []
        for i, r in enumerate(rows, 1):
            try:
                dt = datetime.datetime.fromisoformat(r["created_at"])
                ts = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
                time_str = f"<t:{ts}:R>"
            except Exception:
                time_str = r["created_at"]
            lines.append(
                f"**{i}.** `{r['action'].upper()}` — {r['reason']} — <@{r['moderator_id']}> {time_str}"
            )
        await ctx.send(embed=emb.build(
            title=f"📋 Mod Logs — {member}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            thumbnail=member.display_avatar.url,
        ))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
    log.info("Moderation cog loaded")
