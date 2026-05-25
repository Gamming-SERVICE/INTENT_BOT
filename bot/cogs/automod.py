# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Advanced AutoMod Cog
#                   PREFIX-ONLY | No slash commands
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import time
from collections import defaultdict, deque

import discord
from discord.ext import commands

from core.settings import GuildSettings
from core.database import db
from core.permissions import require_admin
import core.embeds as emb
from core.logger import get_logger

log = get_logger("automod")

# Per-guild spam tracker: guild_id → user_id → deque of timestamps
_spam_tracker: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(deque))

# Raid detection: guild_id → deque of join timestamps
_join_tracker: dict[int, deque] = defaultdict(deque)

URL_RE    = re.compile(r"https?://[^\s]+", re.IGNORECASE)
INVITE_RE = re.compile(r"discord(?:\.gg|(?:app)?\.com/invite)/\S+", re.IGNORECASE)
ZALGO_RE  = re.compile(r"[\u0300-\u036f\u0489]{4,}")
REPEAT_RE = re.compile(r"(.)\1{9,}")

CAPS_THRESHOLD = 0.70
CAPS_MIN_LEN   = 15


class AutoMod(commands.Cog, name="AutoMod"):
    """Advanced per-guild automatic moderation."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Main entry point ───────────────────────────────────────────────────────

    async def process(self, message: discord.Message) -> bool:
        """
        Run all automod checks. Returns True if message was deleted/actioned.
        Called from on_message in main.py.
        """
        if not message.guild:
            return False
        if message.author.bot:
            return False
        member = message.author
        if member.guild_permissions.administrator or member.guild_permissions.manage_messages:
            return False

        gs = await GuildSettings.fetch(message.guild.id)
        if not gs.automod_enabled:
            return False

        content_lower = message.content.lower()

        # ── 1. Banned words ────────────────────────────────────────────────────
        for word in gs.banned_words:
            if word and word in content_lower:
                await self._delete_and_warn(message, "⚠️ That word is not allowed here.")
                await self._log(message.guild, message, "Banned Word", f"Matched: `{word}`")
                return True

        # ── 2. Anti-spam ───────────────────────────────────────────────────────
        if gs.anti_spam_enabled:
            now    = time.monotonic()
            bucket = _spam_tracker[message.guild.id][member.id]
            bucket.append(now)
            while bucket and now - bucket[0] > gs.spam_interval:
                bucket.popleft()
            if len(bucket) >= gs.spam_threshold:
                bucket.clear()
                try:
                    await message.channel.purge(
                        limit=gs.spam_threshold + 3,
                        check=lambda m: m.author == member,
                    )
                except discord.HTTPException:
                    pass
                await self._warn_channel(
                    message,
                    f"⚠️ {member.mention} slow down! You're sending messages too fast.",
                )
                await self._log(
                    message.guild, message, "Anti-Spam",
                    f"Threshold: {gs.spam_threshold}/{gs.spam_interval}s",
                )
                return True

        # ── 3. Link / invite filter ────────────────────────────────────────────
        if gs.anti_link_enabled:
            has_link   = URL_RE.search(message.content)
            has_invite = INVITE_RE.search(message.content)
            if has_link or has_invite:
                await self._delete_and_warn(message, "⚠️ Links and invites are not allowed here.")
                await self._log(
                    message.guild, message, "Anti-Link",
                    "Invite" if has_invite else "URL",
                )
                return True

        # ── 4. Mass mentions ───────────────────────────────────────────────────
        actual_mentions = len([m for m in message.mentions if not m.bot])
        if actual_mentions > gs.max_mentions:
            await self._delete_and_warn(
                message,
                f"⚠️ Too many mentions! Maximum is {gs.max_mentions}.",
            )
            await self._log(
                message.guild, message, "Mass Mention",
                f"{actual_mentions} mentions",
            )
            return True

        # ── 5. Zalgo text ──────────────────────────────────────────────────────
        if ZALGO_RE.search(message.content):
            await self._delete_and_warn(message, "⚠️ Zalgo/corrupted text is not allowed.")
            await self._log(message.guild, message, "Zalgo Text", "")
            return True

        # ── 6. Repeated characters ─────────────────────────────────────────────
        if REPEAT_RE.search(message.content):
            await self._delete_and_warn(message, "⚠️ Please don't spam repeated characters.")
            await self._log(message.guild, message, "Repeat Spam", "")
            return True

        # ── 7. Excessive caps ──────────────────────────────────────────────────
        text = message.content
        if len(text) >= CAPS_MIN_LEN:
            alpha = [c for c in text if c.isalpha()]
            if alpha and sum(1 for c in alpha if c.isupper()) / len(alpha) >= CAPS_THRESHOLD:
                await self._delete_and_warn(message, "⚠️ Please don't type in all caps.")
                await self._log(message.guild, message, "Excessive Caps", "")
                return True

        return False

    # ── Raid detection ─────────────────────────────────────────────────────────

    async def check_raid(self, member: discord.Member) -> None:
        """Call from on_member_join to detect mass-join raids."""
        guild_id = member.guild.id
        now      = time.monotonic()
        bucket   = _join_tracker[guild_id]
        bucket.append(now)
        while bucket and now - bucket[0] > 10:
            bucket.popleft()
        if len(bucket) >= 10:
            bucket.clear()
            gs = await GuildSettings.fetch(guild_id)
            if gs.log_channel:
                ch = member.guild.get_channel(gs.log_channel)
                if ch:
                    embed = emb.build(
                        title="🚨 RAID DETECTED",
                        description=(
                            "10+ accounts joined in the last 10 seconds!\n"
                            "Consider enabling membership screening or raid mode."
                        ),
                        color=discord.Color.red(),
                        fields=[("Latest Member", member.mention, True)],
                    )
                    try:
                        await ch.send(embed=embed)
                    except discord.HTTPException:
                        pass
            log.warning("Raid detected in guild %d — 10+ joins in 10s", guild_id)

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _delete_and_warn(self, message: discord.Message, text: str) -> None:
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await self._warn_channel(message, text)

    async def _warn_channel(self, message: discord.Message, text: str) -> None:
        try:
            await message.channel.send(text, delete_after=6)
        except discord.HTTPException:
            pass

    async def _log(
        self,
        guild: discord.Guild,
        message: discord.Message,
        reason: str,
        detail: str,
    ) -> None:
        gs = await GuildSettings.fetch(guild.id)
        if not gs.logging_enabled or not gs.log_channel:
            return
        channel = guild.get_channel(gs.log_channel)
        if not channel:
            return
        embed = emb.build(
            title=f"🛡️ AutoMod — {reason}",
            color=discord.Color.orange(),
            fields=[
                ("User",    f"{message.author.mention} (`{message.author}`)", True),
                ("Channel", message.channel.mention,                           True),
                ("Detail",  detail or "N/A",                                  True),
                ("Content", (message.content[:500] or "*empty*"),             False),
            ],
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    # ── Admin commands ─────────────────────────────────────────────────────────

    @commands.command(name="automodstats")
    @require_admin()
    @commands.guild_only()
    async def automodstats(self, ctx: commands.Context) -> None:
        """Show automod settings. Usage: !automodstats"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await ctx.send(embed=emb.build(
            title="🛡️ AutoMod Settings",
            color=discord.Color.orange(),
            fields=[
                ("Enabled",        "✅" if gs.automod_enabled   else "❌", True),
                ("Anti-Spam",      "✅" if gs.anti_spam_enabled  else "❌", True),
                ("Anti-Link",      "✅" if gs.anti_link_enabled  else "❌", True),
                ("Max Mentions",   str(gs.max_mentions),                    True),
                ("Spam Threshold", f"{gs.spam_threshold}/{gs.spam_interval}s", True),
                ("Banned Words",   str(len(gs.banned_words)),               True),
                ("Zalgo Filter",   "✅ Always On",                          True),
                ("Caps Filter",    "✅ Always On",                          True),
                ("Raid Detect",    "✅ Always On",                          True),
            ],
        ))

    @commands.command(name="setspam")
    @require_admin()
    @commands.guild_only()
    async def setspam(self, ctx: commands.Context, threshold: int, interval: int) -> None:
        """Configure anti-spam. Usage: !setspam <threshold> <interval_seconds>
        Example: !setspam 5 5  (5 messages in 5 seconds)"""
        if not 3 <= threshold <= 20:
            return await ctx.send(embed=emb.error("Threshold must be between 3 and 20."))
        if not 3 <= interval <= 30:
            return await ctx.send(embed=emb.error("Interval must be between 3 and 30 seconds."))
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set_many(spam_threshold=threshold, spam_interval=interval)
        await ctx.send(embed=emb.success(
            f"Spam threshold: **{threshold} messages** in **{interval} seconds**."
        ))

    @commands.command(name="setmaxmentions")
    @require_admin()
    @commands.guild_only()
    async def setmaxmentions(self, ctx: commands.Context, max_mentions: int) -> None:
        """Set maximum mentions per message. Usage: !setmaxmentions <1-20>"""
        if not 1 <= max_mentions <= 20:
            return await ctx.send(embed=emb.error("Max mentions must be between 1 and 20."))
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("max_mentions", max_mentions)
        await ctx.send(embed=emb.success(f"Max mentions per message set to **{max_mentions}**."))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))
    log.info("AutoMod cog loaded")
