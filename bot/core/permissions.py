# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Permission Helpers
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

from typing import Callable

import discord
from discord.ext import commands

from core.logger import get_logger

log = get_logger("permissions")


# ── Context helpers ───────────────────────────────────────────────────────────

def is_mod_or_admin(member: discord.Member) -> bool:
    """True if the member has Manage Messages or Administrator permission."""
    perms = member.guild_permissions
    return perms.administrator or perms.manage_messages or perms.manage_guild


def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator


def can_moderate(actor: discord.Member, target: discord.Member) -> bool:
    """True if actor's top role is above target's top role."""
    if target.guild.owner_id == target.id:
        return False
    return actor.top_role > target.top_role


def bot_can_moderate(guild: discord.Guild, target: discord.Member) -> bool:
    me = guild.me
    return me.top_role > target.top_role and me.guild_permissions.manage_roles


# ── Check factories ───────────────────────────────────────────────────────────

def require_mod() -> Callable:
    """Command check: user must have Manage Messages or higher."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if is_mod_or_admin(ctx.author):
            return True
        raise commands.MissingPermissions(["manage_messages"])
    return commands.check(predicate)


def require_admin() -> Callable:
    """Command check: user must be administrator."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if is_admin(ctx.author):
            return True
        raise commands.MissingPermissions(["administrator"])
    return commands.check(predicate)


def guild_only() -> Callable:
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True
    return commands.check(predicate)


# ── Interaction (slash command) checks ────────────────────────────────────────

async def interaction_is_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        return False
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ You need Administrator permission.", ephemeral=True)
        return False
    return True


async def interaction_is_mod(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        return False
    if not is_mod_or_admin(interaction.user):
        await interaction.response.send_message("❌ You need Manage Messages permission.", ephemeral=True)
        return False
    return True
