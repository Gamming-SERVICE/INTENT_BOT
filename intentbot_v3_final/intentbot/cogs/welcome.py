# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Welcome / Leave / Logging Cog
# ══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import discord
from discord.ext import commands

from core.settings import GuildSettings
import core.embeds as emb
from core.logger import get_logger

log = get_logger("welcome")


def _safe_count(guild: discord.Guild) -> str:
    """Return member count as string, safely handles None."""
    count = getattr(guild, "member_count", None)
    return str(count) if count is not None else "?"


def _safe_format(template: str, **kwargs) -> str:
    """Format a template string and return the raw template on KeyError."""
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError, IndexError) as e:
        log.warning("Welcome/Leave message format error: %s — template: %r", e, template)
        return template


async def _send_to_log(guild: discord.Guild, embed: discord.Embed) -> None:
    """Send embed to the guild log channel. Silently handles all failures."""
    try:
        gs = await GuildSettings.fetch(guild.id)
        if not gs.logging_enabled or not gs.log_channel:
            return
        ch = guild.get_channel(gs.log_channel)
        if not ch:
            return
        await ch.send(embed=embed)
    except discord.Forbidden:
        log.warning("Missing permissions to send to log channel in guild %d", guild.id)
    except discord.HTTPException as e:
        log.warning("HTTPException sending to log channel in guild %d: %s", guild.id, e)
    except Exception as e:
        log.exception("Unexpected error in _send_to_log for guild %d: %s", guild.id, e)


class Welcome(commands.Cog, name="Welcome"):
    """
    Member join/leave events and server-event logging.

    REQUIRES in main.py:
        intents.members = True   ← on_member_join / on_member_remove need this
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Member join ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        try:
            gs = await GuildSettings.fetch(member.guild.id)
        except Exception as e:
            log.exception("Failed to fetch settings on member join guild %d: %s", member.guild.id, e)
            return

        # ── Auto-role ──────────────────────────────────────────────────────────
        if gs.auto_role:
            try:
                role = member.guild.get_role(gs.auto_role)
                if role:
                    await member.add_roles(role, reason="Auto-role on join")
                    log.debug("Auto-role %s given to %s in guild %s", role.name, member, member.guild.name)
                else:
                    log.warning("Auto-role ID %d not found in guild %d", gs.auto_role, member.guild.id)
            except discord.Forbidden:
                log.warning("Missing permissions to assign auto-role in guild %d", member.guild.id)
            except discord.HTTPException as e:
                log.warning("Failed to assign auto-role in guild %d: %s", member.guild.id, e)

        # ── Welcome message ────────────────────────────────────────────────────
        if gs.welcome_enabled and gs.welcome_channel:
            try:
                ch = member.guild.get_channel(gs.welcome_channel)
                if ch:
                    text = _safe_format(
                        gs.welcome_message,
                        user=member.mention,
                        username=member.name,
                        server=member.guild.name,
                        count=_safe_count(member.guild),
                    )
                    embed = emb.build(
                        title="👋 Welcome!",
                        description=text,
                        color=discord.Color.green(),
                        thumbnail=member.display_avatar.url,
                        fields=[
                            ("Account Created", f"<t:{int(member.created_at.timestamp())}:R>", True),
                            ("Member Number",   f"#{_safe_count(member.guild)}",               True),
                        ],
                    )
                    await ch.send(embed=embed)
                else:
                    log.warning("Welcome channel %d not found in guild %d", gs.welcome_channel, member.guild.id)
            except discord.Forbidden:
                log.warning("Missing permissions to send welcome message in guild %d", member.guild.id)
            except discord.HTTPException as e:
                log.warning("HTTPException sending welcome message in guild %d: %s", member.guild.id, e)
            except Exception as e:
                log.exception("Unexpected error sending welcome message in guild %d: %s", member.guild.id, e)

        # ── Log ────────────────────────────────────────────────────────────────
        log_embed = emb.build(
            title="📥 Member Joined",
            description=f"{member.mention} (`{member}`, ID: `{member.id}`)",
            color=discord.Color.green(),
            thumbnail=member.display_avatar.url,
            fields=[
                ("Account Created", f"<t:{int(member.created_at.timestamp())}:R>", True),
                ("Member Count",    _safe_count(member.guild),                      True),
            ],
        )
        await _send_to_log(member.guild, log_embed)

    # ── Member leave ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        try:
            gs = await GuildSettings.fetch(member.guild.id)
        except Exception as e:
            log.exception("Failed to fetch settings on member remove guild %d: %s", member.guild.id, e)
            return

        # ── Leave message ──────────────────────────────────────────────────────
        if gs.leave_enabled and gs.leave_channel:
            try:
                ch = member.guild.get_channel(gs.leave_channel)
                if ch:
                    text = _safe_format(
                        gs.leave_message,
                        user=member.mention,
                        username=member.name,
                        server=member.guild.name,
                        count=_safe_count(member.guild),
                    )
                    embed = emb.build(
                        title="👋 Goodbye!",
                        description=text,
                        color=discord.Color.red(),
                        thumbnail=member.display_avatar.url,
                    )
                    await ch.send(embed=embed)
                else:
                    log.warning("Leave channel %d not found in guild %d", gs.leave_channel, member.guild.id)
            except discord.Forbidden:
                log.warning("Missing permissions to send leave message in guild %d", member.guild.id)
            except discord.HTTPException as e:
                log.warning("HTTPException sending leave message in guild %d: %s", member.guild.id, e)
            except Exception as e:
                log.exception("Unexpected error sending leave message in guild %d: %s", member.guild.id, e)

        # ── Log ────────────────────────────────────────────────────────────────
        log_embed = emb.build(
            title="📤 Member Left",
            description=f"`{member}` (ID: `{member.id}`)",
            color=discord.Color.red(),
        )
        await _send_to_log(member.guild, log_embed)

    # ── Message deleted ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        try:
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
            await _send_to_log(message.guild, embed)
        except Exception as e:
            log.exception("Error in on_message_delete: %s", e)

    # ── Message edited ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        try:
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
                    ("After",   (after.content[:500]  or "*(empty)*"),          False),
                    ("Jump",    f"[Click]({after.jump_url})",                   True),
                ],
            )
            await _send_to_log(before.guild, embed)
        except Exception as e:
            log.exception("Error in on_message_edit: %s", e)

    # ── Role / nickname updates ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        try:
            added   = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)

            if added:
                embed = emb.build(
                    title="🎭 Role Added",
                    description=after.mention,
                    color=discord.Color.green(),
                    fields=[("Role", ", ".join(r.mention for r in added), False)],
                )
                await _send_to_log(after.guild, embed)

            if removed:
                embed = emb.build(
                    title="🎭 Role Removed",
                    description=after.mention,
                    color=discord.Color.red(),
                    fields=[("Role", ", ".join(r.mention for r in removed), False)],
                )
                await _send_to_log(after.guild, embed)

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
                await _send_to_log(after.guild, embed)
        except Exception as e:
            log.exception("Error in on_member_update: %s", e)

    # ── Voice state ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after:  discord.VoiceState,
    ) -> None:
        try:
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
                title="🔊 Voice Update",
                description=f"{member.mention} {action}",
                color=color,
            )
            await _send_to_log(member.guild, embed)
        except Exception as e:
            log.exception("Error in on_voice_state_update: %s", e)

    # ── Ban / Unban ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        try:
            embed = emb.build(
                title="🔨 Member Banned",
                description=f"{user.mention} (`{user}`, ID: `{user.id}`)",
                color=discord.Color.dark_red(),
                thumbnail=user.display_avatar.url,
            )
            await _send_to_log(guild, embed)
        except Exception as e:
            log.exception("Error in on_member_ban: %s", e)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        try:
            embed = emb.build(
                title="✅ Member Unbanned",
                description=f"{user.mention} (`{user}`, ID: `{user.id}`)",
                color=discord.Color.green(),
            )
            await _send_to_log(guild, embed)
        except Exception as e:
            log.exception("Error in on_member_unban: %s", e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
    log.info("Welcome cog loaded")
