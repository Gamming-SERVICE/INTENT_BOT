# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — main.py
#
# Entry point.  Run with:  python main.py
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path

import discord
from discord.ext import commands

import config
from core.constants import BOT_NAME, BOT_VERSION, STATUS_MESSAGES
from core.database import db
from core.logger import setup_logging, get_logger
from core.settings import GuildSettings
from core.cache import (
    load_reaction_roles_into_cache,
    load_custom_commands_into_cache,
    reaction_roles_cache,
    custom_commands_cache,
)
from core.scheduler import scheduler
from services.updater_service import updater
from views.ticket_views import TicketPanelView, TicketControlView

log = get_logger("main")

# ── All cogs to load (order matters for startup logs, not functionality) ───────
COGS = [
    "cogs.admin",
    "cogs.moderation",
    "cogs.economy",
    "cogs.leveling",
    "cogs.automod",
    "cogs.welcome",
    "cogs.tickets",
    "cogs.giveaway",
    "cogs.marketplace",
    "cogs.utility",
    "cogs.fun",
    "cogs.ai",
]


# ══════════════════════════════════════════════════════════════════════════════
# BOT SUBCLASS
# ══════════════════════════════════════════════════════════════════════════════

class IntentBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=self._get_prefix,
            intents=intents,
            help_command=None,
            owner_ids=set(config.OWNER_IDS) if config.OWNER_IDS else None,
            case_insensitive=True,
        )

    async def _get_prefix(self, bot: "IntentBot", message: discord.Message):
        default = config.DEFAULT_PREFIX
        if not message.guild:
            return commands.when_mentioned_or(default)(bot, message)
        try:
            gs = await GuildSettings.get(message.guild.id)
            prefix = gs.prefix
        except Exception:
            prefix = default
        return commands.when_mentioned_or(prefix)(bot, message)

    # ── Setup ──────────────────────────────────────────────────────────────────

    async def setup_hook(self) -> None:
        log.info("Running setup_hook …")

        # Connect database first
        await db.connect()

        # Load all cogs
        failed = []
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("✅ Loaded cog: %s", cog)
            except Exception as e:
                log.error("❌ Failed to load cog %s: %s", cog, e)
                failed.append(cog)

        if failed:
            log.warning("The following cogs failed to load: %s", ", ".join(failed))

        # Pre-populate caches
        await load_reaction_roles_into_cache()
        await load_custom_commands_into_cache()

        # Register persistent views so buttons work after restart
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())

        # Load per-guild color-role panels
        rows = await db.fetchall("SELECT DISTINCT guild_id FROM color_roles")
        for row in rows:
            guild_rows = await db.fetchall(
                "SELECT role_id, label, emoji, style FROM color_roles WHERE guild_id = ?",
                (row["guild_id"],),
            )
            if guild_rows:
                from views.role_views import ColorRolePanelView
                data = [(r["role_id"], r["label"], r["emoji"], r["style"]) for r in guild_rows]
                self.add_view(ColorRolePanelView(data))

        # Start background scheduler
        scheduler.start()

        # Start updater
        updater.start()

        # Sync slash commands globally
        try:
            synced = await self.tree.sync()
            log.info("Synced %d slash commands globally", len(synced))
        except Exception as e:
            log.error("Failed to sync slash commands: %s", e)

    # ── on_ready ───────────────────────────────────────────────────────────────

    async def on_ready(self) -> None:
        log.info("═" * 52)
        log.info("  %s v%s", BOT_NAME, BOT_VERSION)
        log.info("  Bot user:  %s (%d)", self.user, self.user.id)
        log.info("  Servers:   %d", len(self.guilds))
        log.info("  Users:     %d", sum(g.member_count for g in self.guilds))
        log.info("  discord.py: %s", discord.__version__)
        log.info("═" * 52)
        self._status_index = 0
        self._status_task  = asyncio.create_task(self._rotate_status())

    async def _rotate_status(self) -> None:
        while True:
            try:
                msg = STATUS_MESSAGES[self._status_index % len(STATUS_MESSAGES)].format(
                    guilds=len(self.guilds),
                    users=sum(g.member_count for g in self.guilds),
                )
                await self.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.watching, name=msg),
                    status=discord.Status.online,
                )
                self._status_index += 1
            except Exception:
                pass
            await asyncio.sleep(30)

    # ── on_message ─────────────────────────────────────────────────────────────

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        # AFK handler
        utility_cog = self.get_cog("Utility")
        if utility_cog:
            await utility_cog.handle_afk(message)

        # Custom commands
        if message.guild and message.content:
            try:
                gs = await GuildSettings.get(message.guild.id)
                prefix = gs.prefix
                if message.content.startswith(prefix):
                    cmd_name = message.content[len(prefix):].split()[0].lower()
                    response = custom_commands_cache.get((message.guild.id, cmd_name))
                    if response:
                        await message.channel.send(response)
                        await db.execute(
                            "UPDATE custom_commands SET uses = uses + 1 WHERE name = ? AND guild_id = ?",
                            (cmd_name, message.guild.id),
                        )
                        return
            except Exception:
                pass

        # AutoMod
        automod_cog = self.get_cog("AutoMod")
        if automod_cog:
            blocked = await automod_cog.process(message)
            if blocked:
                return

        # XP / Leveling
        leveling_cog = self.get_cog("Leveling")
        if leveling_cog:
            await leveling_cog.process_message_xp(message)

        await self.process_commands(message)

    # ── Reaction roles ─────────────────────────────────────────────────────────

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.user.id or not payload.guild_id:
            return
        role_id = reaction_roles_cache.get((payload.message_id, str(payload.emoji)))
        if role_id:
            guild  = self.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id) if guild else None
            role   = guild.get_role(role_id) if guild else None
            if member and role:
                try:
                    await member.add_roles(role, reason="Reaction role")
                except discord.HTTPException:
                    pass

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.user.id or not payload.guild_id:
            return
        role_id = reaction_roles_cache.get((payload.message_id, str(payload.emoji)))
        if role_id:
            guild  = self.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id) if guild else None
            role   = guild.get_role(role_id) if guild else None
            if member and role:
                try:
                    await member.remove_roles(role, reason="Reaction role")
                except discord.HTTPException:
                    pass

    # ── on_guild_join / remove ─────────────────────────────────────────────────

    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info("Joined guild: %s (%d)", guild.name, guild.id)
        # Pre-create settings row so first access is fast
        await GuildSettings.get(guild.id)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        log.info("Left guild: %s (%d)", guild.name, guild.id)
        GuildSettings.invalidate(guild.id)

    # ── Error handler ──────────────────────────────────────────────────────────

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        # Unwrap CheckFailure wrappers
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send(embed=_err("This command can only be used inside a server."))
        elif isinstance(error, commands.MissingPermissions):
            perms = ", ".join(f"`{p}`" for p in error.missing_permissions)
            await ctx.send(embed=_err(f"You need these permissions: {perms}"))
        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(f"`{p}`" for p in error.missing_permissions)
            await ctx.send(embed=_err(f"I'm missing required permissions: {perms}"))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=_err(f"Missing argument: `{error.param.name}`\nUse `/help` or check the command description."))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=_err(f"Invalid argument: {error}"))
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=_err(f"Command on cooldown. Try again in **{error.retry_after:.1f}s**"))
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(embed=_err("Member not found."))
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send(embed=_err("Role not found."))
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.send(embed=_err("Channel not found."))
        elif isinstance(error, commands.NotOwner):
            await ctx.send(embed=_err("This command is owner-only."))
        else:
            log.error("Unhandled error in command %s: %s", ctx.command, error, exc_info=error)
            await ctx.send(embed=_err("An unexpected error occurred. Please try again later."))

    async def on_error(self, event: str, *args, **kwargs) -> None:
        log.exception("Unhandled exception in event %s", event)

    # ── Cleanup ────────────────────────────────────────────────────────────────

    async def close(self) -> None:
        log.info("Shutting down …")
        await scheduler.stop()
        await updater.stop()
        await db.close()
        await super().close()


# ── Inline embed helper ────────────────────────────────────────────────────────

def _err(msg: str) -> discord.Embed:
    return discord.Embed(title="❌ Error", description=msg, color=discord.Color.red())


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # Create required directories
    Path("data/backups").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    # Setup logging
    level = logging.DEBUG if config.DEBUG else logging.INFO
    setup_logging(level=level)

    bot = IntentBot()
    bot.run(config.TOKEN, log_handler=None)   # We handle logging ourselves


if __name__ == "__main__":
    main()
