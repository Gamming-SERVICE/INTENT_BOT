# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Logging Cog
#                   PREFIX-ONLY | No slash commands
#
# Handles all server event logging to the configured log channel.
# Covers: messages, members, roles, voice, channels, bans.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime

import discord
from discord.ext import commands

from core.settings import GuildSettings
import core.embeds as emb
from core.logger import get_logger

log = get_logger("logging_cog")


async def _get_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Return the configured log channel, or None if not set / disabled."""
    try:
        gs = await GuildSettings.fetch(guild.id)
        if not gs.logging_enabled or not gs.log_channel:
            return None
        ch = guild.get_channel(gs.log_channel)
        return ch if isinstance(ch, discord.TextChannel) else None
    except Exception as e:
        log.warning("Failed to get log channel for guild %d: %s", guild.id, e)
        return None


async def _send_log(guild: discord.Guild, embed: discord.Embed) -> None:
    """Send an embed to the guild's log channel, silently ignoring errors."""
    ch = await _get_log_channel(guild)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.HTTPException:
            pass


class Logging(commands.Cog, name="Logging"):
    """
    Server event logging.

    Logged events:
    - Message edit / delete
    - Member join / leave
    - Member update (roles, nickname)
    - Voice state changes
    - Ban / unban
    - Channel create / delete / update
    - Role create / delete
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Message events ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        content = message.content or "*[no text content]*"
        embed = emb.build(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            fields=[
                ("Author",  f"{message.author.mention} (`{message.author}`, ID: {message.author.id})", True),
                ("Channel", message.channel.mention,                                                    True),
                ("Content", content[:1000],                                                             False),
            ],
        )
        await _send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        embed = emb.build(
            title="✏️ Message Edited",
            color=discord.Color.yellow(),
            fields=[
                ("Author",  f"{before.author.mention} (`{before.author}`)", True),
                ("Channel", before.channel.mention,                          True),
                ("Before",  (before.content[:500] or "*empty*"),            False),
                ("After",   (after.content[:500] or "*empty*"),             False),
                ("Jump",    f"[Click here]({after.jump_url})",              True),
            ],
        )
        await _send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]) -> None:
        if not messages or not messages[0].guild:
            return
        guild   = messages[0].guild
        channel = messages[0].channel
        embed   = emb.build(
            title="🗑️ Bulk Message Delete",
            description=f"**{len(messages)}** messages were bulk-deleted in {channel.mention}.",
            color=discord.Color.dark_red(),
        )
        await _send_log(guild, embed)

    # ── Member events ──────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        created_ts = int(member.created_at.timestamp())
        embed = emb.build(
            title="📥 Member Joined",
            description=f"{member.mention} (`{member}`, ID: `{member.id}`)",
            color=discord.Color.green(),
            thumbnail=member.display_avatar.url,
            fields=[
                ("Account Created", f"<t:{created_ts}:R>", True),
                ("Members Now",     str(member.guild.member_count), True),
            ],
        )
        await _send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        roles = [r.mention for r in reversed(member.roles) if r != member.guild.default_role]
        embed = emb.build(
            title="📤 Member Left",
            description=f"`{member}` (ID: `{member.id}`)",
            color=discord.Color.red(),
            thumbnail=member.display_avatar.url,
            fields=[
                ("Roles", (", ".join(roles[:10]) if roles else "None"), False),
                ("Members Now", str(member.guild.member_count), True),
            ],
        )
        await _send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        # Role changes
        added   = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)

        if added:
            embed = emb.build(
                title="🎭 Role Added",
                description=after.mention,
                color=discord.Color.green(),
                fields=[("Roles Added", ", ".join(r.mention for r in added), False)],
            )
            await _send_log(after.guild, embed)

        if removed:
            embed = emb.build(
                title="🎭 Role Removed",
                description=after.mention,
                color=discord.Color.red(),
                fields=[("Roles Removed", ", ".join(r.mention for r in removed), False)],
            )
            await _send_log(after.guild, embed)

        # Nickname changes
        if before.nick != after.nick:
            embed = emb.build(
                title="📝 Nickname Changed",
                description=after.mention,
                color=discord.Color.blue(),
                fields=[
                    ("Before", before.nick or "*(none)*", True),
                    ("After",  after.nick  or "*(none)*", True),
                ],
            )
            await _send_log(after.guild, embed)

    # ── Voice events ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if before.channel == after.channel:
            return

        if after.channel and not before.channel:
            action = f"joined **{after.channel.name}**"
            color  = discord.Color.green()
        elif before.channel and not after.channel:
            action = f"left **{before.channel.name}**"
            color  = discord.Color.red()
        else:
            action = f"moved **{before.channel.name}** → **{after.channel.name}**"
            color  = discord.Color.yellow()

        embed = emb.build(
            title="🔊 Voice State Update",
            description=f"{member.mention} {action}",
            color=color,
        )
        await _send_log(member.guild, embed)

    # ── Ban / Unban ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        embed = emb.build(
            title="🔨 Member Banned",
            description=f"{user.mention} (`{user}`, ID: `{user.id}`)",
            color=discord.Color.dark_red(),
            thumbnail=user.display_avatar.url,
        )
        await _send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        embed = emb.build(
            title="✅ Member Unbanned",
            description=f"{user.mention} (`{user}`, ID: `{user.id}`)",
            color=discord.Color.green(),
        )
        await _send_log(guild, embed)

    # ── Channel events ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        embed = emb.build(
            title="📌 Channel Created",
            description=f"{channel.mention} (`{channel.name}`)",
            color=discord.Color.green(),
            fields=[("Type", str(channel.type).title(), True)],
        )
        await _send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        embed = emb.build(
            title="🗑️ Channel Deleted",
            description=f"`{channel.name}` (ID: `{channel.id}`)",
            color=discord.Color.red(),
            fields=[("Type", str(channel.type).title(), True)],
        )
        await _send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        if before.name != after.name:
            embed = emb.build(
                title="✏️ Channel Renamed",
                description=after.mention,
                color=discord.Color.yellow(),
                fields=[
                    ("Before", f"`{before.name}`", True),
                    ("After",  f"`{after.name}`",  True),
                ],
            )
            await _send_log(after.guild, embed)

    # ── Role events ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        embed = emb.build(
            title="🎨 Role Created",
            description=f"{role.mention} (`{role.name}`)",
            color=discord.Color.green(),
        )
        await _send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        embed = emb.build(
            title="🗑️ Role Deleted",
            description=f"`{role.name}` (ID: `{role.id}`)",
            color=discord.Color.red(),
        )
        await _send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        changes = []
        if before.name != after.name:
            changes.append(f"Name: `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"Color: `{before.color}` → `{after.color}`")
        if before.permissions != after.permissions:
            changes.append("Permissions updated")
        if before.hoist != after.hoist:
            changes.append(f"Hoisted: {before.hoist} → {after.hoist}")
        if not changes:
            return
        embed = emb.build(
            title="✏️ Role Updated",
            description=after.mention,
            color=discord.Color.yellow(),
            fields=[("Changes", "\n".join(changes), False)],
        )
        await _send_log(after.guild, embed)

    # ── Invite events ──────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        if not invite.guild:
            return
        creator = invite.inviter.mention if invite.inviter else "Unknown"
        embed = emb.build(
            title="🔗 Invite Created",
            color=discord.Color.blurple(),
            fields=[
                ("Code",    f"`{invite.code}`",                           True),
                ("Creator", creator,                                       True),
                ("Channel", invite.channel.mention if invite.channel else "N/A", True),
                ("Max Uses", str(invite.max_uses or "∞"),                 True),
                ("Expires",  f"<t:{int(invite.expires_at.timestamp())}:R>" if invite.expires_at else "Never", True),
            ],
        )
        await _send_log(invite.guild, embed)

    # ── Admin commands ─────────────────────────────────────────────────────────

    @commands.command(name="logtest")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def logtest(self, ctx: commands.Context) -> None:
        """Send a test message to the log channel. Usage: !logtest"""
        from core.settings import GuildSettings
        gs = await GuildSettings.fetch(ctx.guild.id)
        if not gs.log_channel:
            return await ctx.send(embed=emb.error(
                "No log channel configured. Use `!setlog #channel` first."
            ))
        embed = emb.build(
            title="✅ Log Test",
            description="This is a test log message. If you see this, logging is working correctly!",
            color=discord.Color.green(),
            fields=[("Triggered by", ctx.author.mention, True)],
        )
        await _send_log(ctx.guild, embed)
        await ctx.send(embed=emb.success("Test log message sent!"), delete_after=5)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Logging(bot))
    log.info("Logging cog loaded")
