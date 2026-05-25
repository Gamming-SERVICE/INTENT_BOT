# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Admin Cog
#                   PREFIX-ONLY | No slash commands
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import discord
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.permissions import require_admin, require_mod
from core.cache import (
    custom_commands_cache,
    reaction_roles_cache,
    load_custom_commands_into_cache,
    load_reaction_roles_into_cache,
)
import core.embeds as emb
from core.logger import get_logger

log = get_logger("admin")


class Admin(commands.Cog, name="Admin"):
    """Server configuration and administration commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Channel setup ──────────────────────────────────────────────────────────

    @commands.command(name="setwelcome")
    @require_admin()
    @commands.guild_only()
    async def setwelcome(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Set the welcome message channel. Usage: !setwelcome #channel"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("welcome_channel", channel.id)
        await ctx.send(embed=emb.success(f"Welcome channel set to {channel.mention}"))

    @commands.command(name="setleave")
    @require_admin()
    @commands.guild_only()
    async def setleave(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Set the leave message channel. Usage: !setleave #channel"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("leave_channel", channel.id)
        await ctx.send(embed=emb.success(f"Leave channel set to {channel.mention}"))

    @commands.command(name="setlog")
    @require_admin()
    @commands.guild_only()
    async def setlog(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Set the moderation log channel. Usage: !setlog #channel"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("log_channel", channel.id)
        await ctx.send(embed=emb.success(f"Log channel set to {channel.mention}"))

    @commands.command(name="setlevelchannel")
    @require_admin()
    @commands.guild_only()
    async def setlevelchannel(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        """Set the level-up announcement channel. Usage: !setlevelchannel [#channel]"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        if channel:
            await gs.set("level_up_channel", channel.id)
            await ctx.send(embed=emb.success(f"Level-up channel set to {channel.mention}"))
        else:
            await gs.set("level_up_channel", None)
            await ctx.send(embed=emb.success("Level-up messages will appear where the member chatted."))

    @commands.command(name="setticketcategory")
    @require_admin()
    @commands.guild_only()
    async def setticketcategory(self, ctx: commands.Context, *, category_name: str) -> None:
        """Set the ticket channel category. Usage: !setticketcategory Support"""
        category = discord.utils.find(
            lambda c: c.name.lower() == category_name.lower() and isinstance(c, discord.CategoryChannel),
            ctx.guild.channels,
        )
        if not category:
            return await ctx.send(embed=emb.error(f"Category `{category_name}` not found."))
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("ticket_category", category.id)
        await ctx.send(embed=emb.success(f"Ticket category set to **{category.name}**"))

    # ── Role setup ─────────────────────────────────────────────────────────────

    @commands.command(name="setmuterole")
    @require_admin()
    @commands.guild_only()
    async def setmuterole(self, ctx: commands.Context, role: discord.Role) -> None:
        """Set the mute role. Usage: !setmuterole @Muted"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("mute_role", role.id)
        await ctx.send(embed=emb.success(f"Mute role set to {role.mention}"))

    @commands.command(name="setautorole")
    @require_admin()
    @commands.guild_only()
    async def setautorole(self, ctx: commands.Context, role: discord.Role) -> None:
        """Set auto-role for new members. Usage: !setautorole @Member"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("auto_role", role.id)
        await ctx.send(embed=emb.success(f"Auto role set to {role.mention}"))

    # ── Feature toggles ────────────────────────────────────────────────────────

    _TOGGLE_KEYS = {
        "welcome":   "welcome_enabled",
        "leave":     "leave_enabled",
        "leveling":  "leveling_enabled",
        "economy":   "economy_enabled",
        "automod":   "automod_enabled",
        "logging":   "logging_enabled",
        "antispam":  "anti_spam_enabled",
        "antilink":  "anti_link_enabled",
    }

    @commands.command(name="toggle")
    @require_admin()
    @commands.guild_only()
    async def toggle(self, ctx: commands.Context, feature: str) -> None:
        """Toggle a bot feature on or off. Usage: !toggle <feature>
        Features: welcome, leave, leveling, economy, automod, logging, antispam, antilink"""
        key = self._TOGGLE_KEYS.get(feature.lower())
        if not key:
            opts = ", ".join(f"`{k}`" for k in self._TOGGLE_KEYS)
            return await ctx.send(embed=emb.error(f"Unknown feature. Options: {opts}"))
        gs = await GuildSettings.fetch(ctx.guild.id)
        current = gs.get(key, False)
        await gs.set(key, not current)
        status = "✅ enabled" if not current else "❌ disabled"
        label = feature.replace("_", " ").title()
        await ctx.send(embed=emb.success(f"**{label}** is now **{status}**"))

    # ── Prefix ─────────────────────────────────────────────────────────────────

    @commands.command(name="setprefix")
    @require_admin()
    @commands.guild_only()
    async def setprefix(self, ctx: commands.Context, prefix: str) -> None:
        """Change the command prefix. Usage: !setprefix ?"""
        if len(prefix) > 5:
            return await ctx.send(embed=emb.error("Prefix must be 5 characters or fewer."))
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("prefix", prefix)
        await ctx.send(embed=emb.success(f"Prefix updated to `{prefix}`"))

    # ── Banned words ───────────────────────────────────────────────────────────

    @commands.command(name="addword")
    @require_admin()
    @commands.guild_only()
    async def addword(self, ctx: commands.Context, *, word: str) -> None:
        """Add a word to the automod banned list. Usage: !addword badword"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        words: list = gs.banned_words
        word_lower = word.lower().strip()
        if word_lower in words:
            return await ctx.send(embed=emb.warning("That word is already in the list."))
        words.append(word_lower)
        await gs.set("banned_words", words)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(embed=emb.success("Word added to the banned list."), delete_after=5)

    @commands.command(name="removeword")
    @require_admin()
    @commands.guild_only()
    async def removeword(self, ctx: commands.Context, *, word: str) -> None:
        """Remove a word from the automod banned list. Usage: !removeword badword"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        words: list = gs.banned_words
        word_lower = word.lower().strip()
        if word_lower not in words:
            return await ctx.send(embed=emb.error("That word is not in the list."))
        words.remove(word_lower)
        await gs.set("banned_words", words)
        await ctx.send(embed=emb.success("Word removed from the banned list."))

    @commands.command(name="bannedwords")
    @require_mod()
    @commands.guild_only()
    async def bannedwords(self, ctx: commands.Context) -> None:
        """List all automod banned words. Usage: !bannedwords"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        words = gs.banned_words
        if not words:
            return await ctx.send(embed=emb.info("No banned words configured."))
        embed = emb.build(
            title="🚫 Banned Words",
            description="`" + "`, `".join(words) + "`",
            color=discord.Color.red(),
        )
        try:
            await ctx.author.send(embed=embed)
            await ctx.send(embed=emb.success("Banned words list sent to your DMs."), delete_after=5)
        except discord.HTTPException:
            await ctx.send(embed=embed, delete_after=15)

    # ── Custom commands ────────────────────────────────────────────────────────

    @commands.command(name="addcmd")
    @require_admin()
    @commands.guild_only()
    async def addcmd(self, ctx: commands.Context, name: str, *, response: str) -> None:
        """Create a custom text command. Usage: !addcmd hello Hello there!"""
        name = name.lower().strip()
        if not name.replace("_", "").replace("-", "").isalnum():
            return await ctx.send(embed=emb.error("Command name must be alphanumeric (hyphens/underscores OK)."))
        if len(response) > 2000:
            return await ctx.send(embed=emb.error("Response must be under 2000 characters."))
        await db.execute(
            "INSERT INTO custom_commands (name, guild_id, response, created_by) VALUES (?,?,?,?) "
            "ON CONFLICT(name, guild_id) DO UPDATE SET response = excluded.response",
            (name, ctx.guild.id, response, ctx.author.id),
        )
        custom_commands_cache[(ctx.guild.id, name)] = response
        gs = await GuildSettings.fetch(ctx.guild.id)
        await ctx.send(embed=emb.success(f"Custom command `{gs.prefix}{name}` created!"))

    @commands.command(name="delcmd")
    @require_admin()
    @commands.guild_only()
    async def delcmd(self, ctx: commands.Context, name: str) -> None:
        """Delete a custom command. Usage: !delcmd hello"""
        name = name.lower().strip()
        await db.execute(
            "DELETE FROM custom_commands WHERE name = ? AND guild_id = ?",
            (name, ctx.guild.id),
        )
        custom_commands_cache.pop((ctx.guild.id, name), None)
        await ctx.send(embed=emb.success(f"Custom command `{name}` deleted."))

    @commands.command(name="listcmds")
    @commands.guild_only()
    async def listcmds(self, ctx: commands.Context) -> None:
        """List all custom commands. Usage: !listcmds"""
        rows = await db.fetchall(
            "SELECT name, uses FROM custom_commands WHERE guild_id = ? ORDER BY uses DESC",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No custom commands configured."))
        gs = await GuildSettings.fetch(ctx.guild.id)
        lines = [f"`{gs.prefix}{r['name']}` — {r['uses']} uses" for r in rows]
        await ctx.send(embed=emb.build(
            title="📋 Custom Commands",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        ))

    # ── Reaction roles ─────────────────────────────────────────────────────────

    @commands.command(name="reactionrole")
    @require_admin()
    @commands.guild_only()
    async def reactionrole(self, ctx: commands.Context, message_id: str, emoji: str, role: discord.Role) -> None:
        """Link a reaction emoji to a role. Usage: !reactionrole <message_id> <emoji> @Role"""
        try:
            mid = int(message_id)
            msg = await ctx.channel.fetch_message(mid)
            await msg.add_reaction(emoji)
        except (ValueError, discord.HTTPException) as e:
            return await ctx.send(embed=emb.error(f"Could not find message or add reaction: {e}"))
        await db.execute(
            "INSERT OR REPLACE INTO reaction_roles (message_id, emoji, role_id, guild_id) VALUES (?,?,?,?)",
            (mid, emoji, role.id, ctx.guild.id),
        )
        reaction_roles_cache[(mid, emoji)] = role.id
        await ctx.send(embed=emb.success(f"Reaction role set: {emoji} → {role.mention}"))

    @commands.command(name="rmreactionrole")
    @require_admin()
    @commands.guild_only()
    async def rmreactionrole(self, ctx: commands.Context, message_id: str, emoji: str) -> None:
        """Remove a reaction role. Usage: !rmreactionrole <message_id> <emoji>"""
        try:
            mid = int(message_id)
        except ValueError:
            return await ctx.send(embed=emb.error("Invalid message ID."))
        await db.execute(
            "DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (mid, emoji),
        )
        reaction_roles_cache.pop((mid, emoji), None)
        await ctx.send(embed=emb.success(f"Reaction role `{emoji}` removed from message `{mid}`."))

    # ── Welcome/leave message templates ───────────────────────────────────────

    @commands.command(name="setwelcomemsg")
    @require_admin()
    @commands.guild_only()
    async def setwelcomemsg(self, ctx: commands.Context, *, message: str) -> None:
        """Set welcome message template. Placeholders: {user} {server} {count}
        Usage: !setwelcomemsg Welcome {user} to {server}!"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("welcome_message", message)
        preview = message.format(
            user=ctx.author.mention,
            username=ctx.author.name,
            server=ctx.guild.name,
            count=ctx.guild.member_count or 0,
        )
        await ctx.send(embed=emb.success(f"Welcome message updated!\n\n**Preview:** {preview}"))

    @commands.command(name="setleavemsg")
    @require_admin()
    @commands.guild_only()
    async def setleavemsg(self, ctx: commands.Context, *, message: str) -> None:
        """Set leave message template. Placeholders: {username} {server} {count}
        Usage: !setleavemsg {username} left {server}."""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.set("leave_message", message)
        preview = message.format(
            user=ctx.author.mention,
            username=ctx.author.name,
            server=ctx.guild.name,
            count=ctx.guild.member_count or 0,
        )
        await ctx.send(embed=emb.success(f"Leave message updated!\n\n**Preview:** {preview}"))

    # ── Settings overview ──────────────────────────────────────────────────────

    @commands.command(name="settings")
    @require_mod()
    @commands.guild_only()
    async def settings_cmd(self, ctx: commands.Context) -> None:
        """Show all current server settings. Usage: !settings"""
        gs = await GuildSettings.fetch(ctx.guild.id)

        def ch(cid):
            if not cid:
                return "Not set"
            c = ctx.guild.get_channel(cid)
            return c.mention if c else f"Deleted ({cid})"

        def role(rid):
            if not rid:
                return "Not set"
            r = ctx.guild.get_role(rid)
            return r.mention if r else f"Deleted ({rid})"

        def tog(val):
            return "✅ On" if val else "❌ Off"

        embed = emb.build(
            title=f"⚙️ Settings — {ctx.guild.name}",
            color=discord.Color.blurple(),
            fields=[
                ("Prefix",           f"`{gs.prefix}`",              True),
                ("Welcome Channel",  ch(gs.welcome_channel),        True),
                ("Leave Channel",    ch(gs.leave_channel),          True),
                ("Log Channel",      ch(gs.log_channel),            True),
                ("Level-Up Channel", ch(gs.level_up_channel),       True),
                ("Ticket Category",  ch(gs.ticket_category),        True),
                ("Mute Role",        role(gs.mute_role),            True),
                ("Auto Role",        role(gs.auto_role),            True),
                ("Welcome",          tog(gs.welcome_enabled),       True),
                ("Leave",            tog(gs.leave_enabled),         True),
                ("Leveling",         tog(gs.leveling_enabled),      True),
                ("Economy",          tog(gs.economy_enabled),       True),
                ("AutoMod",          tog(gs.automod_enabled),       True),
                ("Logging",          tog(gs.logging_enabled),       True),
                ("Anti-Spam",        tog(gs.anti_spam_enabled),     True),
                ("Anti-Link",        tog(gs.anti_link_enabled),     True),
                ("Currency",         f"{gs.currency_symbol} {gs.currency_name}", True),
                ("Banned Words",     str(len(gs.banned_words)),     True),
            ],
        )
        await ctx.send(embed=embed)

    @commands.command(name="resetguild")
    @require_admin()
    @commands.guild_only()
    async def resetguild(self, ctx: commands.Context) -> None:
        """Reset ALL server settings to defaults. Usage: !resetguild"""
        gs = await GuildSettings.fetch(ctx.guild.id)
        await gs.reset_all()
        await ctx.send(embed=emb.success("All server settings have been reset to defaults."))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
    log.info("Admin cog loaded")
