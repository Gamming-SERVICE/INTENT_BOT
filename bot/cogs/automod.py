# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — AutoMod Cog
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import time
from collections import defaultdict

import discord
from discord.ext import commands

from core.settings import GuildSettings
import core.embeds as emb
from core.logger import get_logger

log = get_logger("automod")

# guild_id → user_id → [timestamps]
_spam_tracker: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
INVITE_RE = re.compile(r"discord(?:\.gg|app\.com/invite)/\S+", re.IGNORECASE)


class AutoMod(commands.Cog, name="AutoMod"):
    """Automatic message moderation (runs inside on_message)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def process(self, message: discord.Message) -> bool:
        """
        Run all automod checks.
        Returns True if the message was deleted/actioned (caller should stop processing).
        """
        if not message.guild:
            return False
        if message.author.bot:
            return False
        member = message.author
        if member.guild_permissions.administrator:
            return False

        gs = await GuildSettings.get(message.guild.id)
        if not gs.automod_enabled:
            return False

        # ── Spam check ─────────────────────────────────────────────────────────
        if gs.anti_spam_enabled:
            now = time.monotonic()
            guild_tracker = _spam_tracker[message.guild.id]
            guild_tracker[member.id].append(now)
            guild_tracker[member.id] = [
                t for t in guild_tracker[member.id]
                if now - t < gs.spam_interval
            ]
            if len(guild_tracker[member.id]) >= gs.spam_threshold:
                guild_tracker[member.id].clear()
                try:
                    await message.channel.purge(
                        limit=gs.spam_threshold + 2,
                        check=lambda m: m.author == member,
                    )
                except discord.HTTPException:
                    pass
                await self._warn_user(message, "⚠️ Stop spamming!")
                await self._log(message.guild, message, "Anti-Spam")
                return True

        # ── Banned words ───────────────────────────────────────────────────────
        content_lower = message.content.lower()
        for word in gs.banned_words:
            if word in content_lower:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                await self._warn_user(message, "⚠️ That word is not allowed here!")
                await self._log(message.guild, message, "Banned Word")
                return True

        # ── Link / invite filter ───────────────────────────────────────────────
        if gs.anti_link_enabled:
            if URL_RE.search(message.content) or INVITE_RE.search(message.content):
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                await self._warn_user(message, "⚠️ Links are not allowed here!")
                await self._log(message.guild, message, "Anti-Link")
                return True

        # ── Mass mention ───────────────────────────────────────────────────────
        if len(message.mentions) > gs.max_mentions:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            await self._warn_user(message, f"⚠️ Too many mentions! Maximum is {gs.max_mentions}.")
            await self._log(message.guild, message, "Mass Mention")
            return True

        return False

    async def _warn_user(self, message: discord.Message, text: str) -> None:
        try:
            await message.channel.send(
                f"{message.author.mention} {text}",
                delete_after=6,
            )
        except discord.HTTPException:
            pass

    async def _log(self, guild: discord.Guild, message: discord.Message, reason: str) -> None:
        gs = await GuildSettings.get(guild.id)
        if not gs.logging_enabled or not gs.log_channel:
            return
        channel = guild.get_channel(gs.log_channel)
        if not channel:
            return
        embed = emb.build(
            title=f"🛡️ AutoMod — {reason}",
            color=discord.Color.orange(),
            fields=[
                ("User",    f"{message.author.mention} ({message.author.id})", True),
                ("Channel", message.channel.mention,                            True),
                ("Content", (message.content[:500] or "N/A"),                  False),
            ],
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))
    log.info("AutoMod cog loaded")
