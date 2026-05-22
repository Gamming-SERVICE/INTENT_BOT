# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — main.py (Fixed)
# Run with:  python main.py
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import datetime
import logging
import sys
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


class IntentBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=self._get_prefix,
            intents=intents,
            help_command=None,
            owner_ids=set(config.OWNER_IDS) if config.OWNER_IDS else None,
            case_insensitive=True,
            strip_after_prefix=True,
        )
        self._start_time: datetime.datetime = datetime.datetime.utcnow()
        self._status_index: int = 0
        self._status_task: asyncio.Task | None = None

    # ── Dynamic prefix ─────────────────────────────────────────────────────────

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

    # ── Setup hook (runs before on_ready) ─────────────────────────────────────

    async def setup_hook(self) -> None:
        log.info("Running setup_hook…")

        # Database must be connected before any cog loads
        await db.connect()

        # Load all cogs
        failed: list[str] = []
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("  ✅ %s", cog)
            except Exception as e:
                log.error("  ❌ %s — %s", cog, e, exc_info=True)
                failed.append(cog)

        if failed:
            log.warning("Failed cogs: %s", ", ".join(failed))

        # Warm up caches
        await load_reaction_roles_into_cache()
        await load_custom_commands_into_cache()

        # Register persistent views so buttons survive bot restarts
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())

        # Re-register per-guild color role panel views
        try:
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
        except Exception as e:
            log.warning("Could not re-register color role views: %s", e)

        # Start background tasks
        scheduler.start()
        updater.start()

        # Sync slash commands globally (rate-limited by Discord — only needed once per deploy)
        try:
            synced = await self.tree.sync()
            log.info("Synced %d slash commands globally", len(synced))
        except discord.HTTPException as e:
            log.error("Slash command sync failed: %s", e)

    # ── on_ready ───────────────────────────────────────────────────────────────

    async def on_ready(self) -> None:
        log.info("═" * 54)
        log.info("  %s  v%s", BOT_NAME, BOT_VERSION)
        log.info("  Bot:    %s  (ID: %d)", self.user, self.user.id)
        log.info("  Guilds: %d   Users: %d", len(self.guilds), sum(g.member_count for g in self.guilds))
        log.info("  discord.py v%s", discord.__version__)
        log.info("═" * 54)

        if self._status_task is None or self._status_task.done():
            self._status_task = asyncio.create_task(self._rotate_status(), name="status_rotation")

    async def _rotate_status(self) -> None:
        while not self.is_closed():
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
            try:
                await utility_cog.handle_afk(message)
            except Exception as e:
                log.warning("AFK handler error: %s", e)

        # Custom command check (guild only, non-empty message)
        if message.guild and message.content:
            try:
                gs = await GuildSettings.get(message.guild.id)
                prefix = gs.prefix
                content = message.content
                if content.startswith(prefix) and len(content) > len(prefix):
                    cmd_name = content[len(prefix):].split()[0].lower()
                    response = custom_commands_cache.get((message.guild.id, cmd_name))
                    if response:
                        await message.channel.send(response)
                        await db.execute(
                            "UPDATE custom_commands SET uses = uses + 1 WHERE name = ? AND guild_id = ?",
                            (cmd_name, message.guild.id),
                        )
                        return
            except Exception as e:
                log.warning("Custom command check error: %s", e)

        # AutoMod (must run before process_commands)
        automod_cog = self.get_cog("AutoMod")
        if automod_cog:
            try:
                blocked = await automod_cog.process(message)
                if blocked:
                    return
            except Exception as e:
                log.warning("AutoMod error: %s", e)

        # XP / Leveling
        leveling_cog = self.get_cog("Leveling")
        if leveling_cog:
            try:
                await leveling_cog.process_message_xp(message)
            except Exception as e:
                log.warning("Leveling XP error: %s", e)

        await self.process_commands(message)

    # ── Reaction role handlers ─────────────────────────────────────────────────

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
                    await member.remove_roles(role, reason="Reaction role removed")
                except discord.HTTPException:
                    pass

    # ── Guild lifecycle ────────────────────────────────────────────────────────

    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info("Joined guild: %s (%d) | Members: %d", guild.name, guild.id, guild.member_count)
        try:
            await GuildSettings.get(guild.id)   # pre-create settings row
        except Exception as e:
            log.warning("Could not pre-create settings for guild %d: %s", guild.id, e)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        log.info("Left guild: %s (%d)", guild.name, guild.id)
        GuildSettings.invalidate(guild.id)

    # ── Centralised error handler ──────────────────────────────────────────────

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return   # Silently ignore unknown commands
        if isinstance(error, commands.NoPrivateMessage):
            return await ctx.send(embed=_err("This command can only be used inside a server."))
        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in error.missing_permissions)
            return await ctx.send(embed=_err(f"You need: {perms}"))
        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in error.missing_permissions)
            return await ctx.send(embed=_err(f"I'm missing: {perms}"))
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(embed=_err(f"Missing argument: `{error.param.name}`\nUse `/help` or check the command description."))
        if isinstance(error, (commands.BadArgument, commands.BadUnionArgument)):
            return await ctx.send(embed=_err(f"Invalid argument: {error}"))
        if isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(embed=_err(f"⏱️ Cooldown! Try again in **{error.retry_after:.1f}s**"), delete_after=5)
        if isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
            return await ctx.send(embed=_err("Member/user not found."))
        if isinstance(error, commands.RoleNotFound):
            return await ctx.send(embed=_err("Role not found."))
        if isinstance(error, commands.ChannelNotFound):
            return await ctx.send(embed=_err("Channel not found."))
        if isinstance(error, commands.NotOwner):
            return await ctx.send(embed=_err("This command is restricted to bot owners."))
        if isinstance(error, commands.CheckFailure):
            return  # Permission denied — already handled by check decorator

        # Unexpected error — log full traceback
        log.error(
            "Unhandled command error in %s (guild=%s, user=%s): %s",
            ctx.command, getattr(ctx.guild, "id", "DM"), ctx.author.id, error,
            exc_info=error,
        )
        try:
            await ctx.send(embed=_err("An unexpected error occurred. Please try again later."))
        except discord.HTTPException:
            pass

    async def on_error(self, event: str, *args, **kwargs) -> None:
        log.exception("Unhandled exception in event '%s'", event)

    # ── Graceful shutdown ──────────────────────────────────────────────────────

    async def close(self) -> None:
        log.info("Shutting down Intent BOT…")
        if self._status_task and not self._status_task.done():
            self._status_task.cancel()
        try:
            await scheduler.stop()
        except Exception:
            pass
        try:
            await updater.stop()
        except Exception:
            pass
        try:
            await db.close()
        except Exception:
            pass
        await super().close()
        log.info("Shutdown complete.")


def _err(msg: str) -> discord.Embed:
    return discord.Embed(title="❌ Error", description=msg, color=discord.Color.red())


def main() -> None:
    # Ensure required directories exist
    Path("data/backups").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    level = logging.DEBUG if config.DEBUG else logging.INFO
    setup_logging(level=level)

    bot = IntentBot()
    try:
        bot.run(config.TOKEN, log_handler=None, reconnect=True)
    except KeyboardInterrupt:
        log.info("Received keyboard interrupt — stopping.")
    except discord.LoginFailure:
        log.critical("Invalid bot token! Check your DISCORD_TOKEN in .env")
        sys.exit(1)


if __name__ == "__main__":
    main()
