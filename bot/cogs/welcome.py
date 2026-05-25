# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Welcome / Leave / Logging Cog
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime

import discord
from discord.ext import commands

from core.settings import GuildSettings
from core.database import db
import core.embeds as emb
from core.logger import get_logger

log = get_logger("welcome")


async def send_to_log(guild: discord.Guild, embed: discord.Embed) -> None:
    gs = await GuildSettings.fetch(guild.id)
    if not gs.logging_enabled or not gs.log_channel:
        return
    ch = guild.get_channel(gs.log_channel)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.HTTPException:
            pass


class Welcome(commands.Cog, name="Welcome"):
    """Member join/leave events and server-event logging."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Member join ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        gs = await GuildSettings.fetch(member.guild.id)

        # Auto-role
        if gs.auto_role:
            role = member.guild.get_role(gs.auto_role)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except discord.HTTPException:
                    pass

        # Welcome message
        if gs.welcome_enabled and gs.welcome_channel:
            ch = member.guild.get_channel(gs.welcome_channel)
            if ch:
                text = gs.welcome_message.format(
                    user=member.mention,
                    username=member.name,
                    server=member.guild.name,
                    count=member.guild.member_count,
                )
                embed = emb.build(
                    title="👋 Welcome!",
                    description=text,
                    color=discord.Color.green(),
                    thumbnail=member.display_avatar.url,
                    fields=[("Account Created", f"<t:{int(member.created_at.timestamp())}:R>", True)],
                )
                try:
                    await ch.send(embed=embed)
                except discord.HTTPException:
                    pass

        # Log
        log_embed = emb.build(
            title="📥 Member Joined",
            description=f"{member.mention} (`{member}`)",
            color=discord.Color.green(),
            thumbnail=member.display_avatar.url,
            fields=[
                ("Account Age", f"<t:{int(member.created_at.timestamp())}:R>", True),
                ("Members",     str(member.guild.member_count),                True),
            ],
        )
        await send_to_log(member.guild, log_embed)

    # ── Member leave ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        gs = await GuildSettings.fetch(member.guild.id)

        if gs.leave_enabled and gs.leave_channel:
            ch = member.guild.get_channel(gs.leave_channel)
            if ch:
                text = gs.leave_message.format(
                    user=member.mention,
                    username=member.name,
                    server=member.guild.name,
                    count=member.guild.member_count,
                )
                embed = emb.build(
                    title="👋 Goodbye!",
                    description=text,
                    color=discord.Color.red(),
                    thumbnail=member.display_avatar.url,
                )
                try:
                    await ch.send(embed=embed)
                except discord.HTTPException:
                    pass

        log_embed = emb.build(
            title="📤 Member Left",
            description=f"`{member}` ({member.id})",
            color=discord.Color.red(),
        )
        await send_to_log(member.guild, log_embed)

    # ── Message events ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        embed = emb.build(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            fields=[
                ("Author",  f"{message.author.mention} (`{message.author}`)", True),
                ("Channel", message.channel.mention,                           True),
                ("Content", (message.content[:1000] or "*(no text content)*"), False),
            ],
        )
        await send_to_log(message.guild, embed)

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
                ("Before",  (before.content[:500] or "*(empty)*"),          False),
                ("After",   (after.content[:500] or "*(empty)*"),           False),
                ("Jump",    f"[Click]({after.jump_url})",                   True),
            ],
        )
        await send_to_log(before.guild, embed)

    # ── Role / nickname updates ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        added   = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)

        if added:
            embed = emb.build(
                title="🎭 Role Added",
                description=after.mention,
                color=discord.Color.green(),
                fields=[("Role", ", ".join(r.mention for r in added), False)],
            )
            await send_to_log(after.guild, embed)

        if removed:
            embed = emb.build(
                title="🎭 Role Removed",
                description=after.mention,
                color=discord.Color.red(),
                fields=[("Role", ", ".join(r.mention for r in removed), False)],
            )
            await send_to_log(after.guild, embed)

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
            await send_to_log(after.guild, embed)

    # ── Voice state ────────────────────────────────────────────────────────────

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
        elif before.channel and not after.channel:
            action = f"left **{before.channel.name}**"
        else:
            action = f"moved from **{before.channel.name}** → **{after.channel.name}**"

        embed = emb.build(
            title="🔊 Voice Update",
            description=f"{member.mention} {action}",
            color=discord.Color.blurple(),
        )
        await send_to_log(member.guild, embed)

    # ── Ban / unban ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        embed = emb.build(
            title="🔨 Member Banned",
            description=f"{user.mention} (`{user}`)",
            color=discord.Color.dark_red(),
            thumbnail=user.display_avatar.url,
        )
        await send_to_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        embed = emb.build(
            title="✅ Member Unbanned",
            description=f"{user.mention} (`{user}`)",
            color=discord.Color.green(),
        )
        await send_to_log(guild, embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
    log.info("Welcome/Logging cog loaded")
