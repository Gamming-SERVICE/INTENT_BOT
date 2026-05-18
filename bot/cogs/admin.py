# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Admin / Setup Cog
# Commands: setwelcome, setleave, setlog, setlevelchannel, setmuterole,
#           setautorole, setticketcategory, toggle, setprefix,
#           addword, removeword, addmodrole, addcolorrole, removecolorrole,
#           colorpanel, addcmd, delcmd, listcmds, reactionrole, rmreactionrole,
#           settings, resetguild
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

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
from views.role_views import ColorRolePanelView

log = get_logger("admin")


class Admin(commands.Cog, name="Admin"):
    """Server configuration and administration commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Channel setup commands ─────────────────────────────────────────────────

    @commands.hybrid_command(name="setwelcome", description="Set the welcome channel")
    @app_commands.describe(channel="Channel to send welcome messages in")
    @require_admin()
    @commands.guild_only()
    async def setwelcome(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("welcome_channel", channel.id)
        await ctx.send(embed=emb.success(f"Welcome channel set to {channel.mention}"))

    @commands.hybrid_command(name="setleave", description="Set the leave channel")
    @app_commands.describe(channel="Channel to send leave messages in")
    @require_admin()
    @commands.guild_only()
    async def setleave(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("leave_channel", channel.id)
        await ctx.send(embed=emb.success(f"Leave channel set to {channel.mention}"))

    @commands.hybrid_command(name="setlog", description="Set the moderation/action log channel")
    @app_commands.describe(channel="Channel for log messages")
    @require_admin()
    @commands.guild_only()
    async def setlog(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("log_channel", channel.id)
        await ctx.send(embed=emb.success(f"Log channel set to {channel.mention}"))

    @commands.hybrid_command(name="setlevelchannel", description="Set the level-up announcement channel")
    @app_commands.describe(channel="Channel for level-up messages (leave blank to use current channel)")
    @require_admin()
    @commands.guild_only()
    async def setlevelchannel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        if channel:
            await gs.set("level_up_channel", channel.id)
            await ctx.send(embed=emb.success(f"Level-up channel set to {channel.mention}"))
        else:
            await gs.set("level_up_channel", None)
            await ctx.send(embed=emb.success("Level-up messages will appear in the channel where the member chatted"))

    @commands.hybrid_command(name="setticketcategory", description="Set the ticket category")
    @app_commands.describe(category="Category under which ticket channels are created")
    @require_admin()
    @commands.guild_only()
    async def setticketcategory(self, ctx: commands.Context, category: discord.CategoryChannel) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("ticket_category", category.id)
        await ctx.send(embed=emb.success(f"Ticket category set to **{category.name}**"))

    # ── Role setup commands ────────────────────────────────────────────────────

    @commands.hybrid_command(name="setmuterole", description="Set the mute role")
    @app_commands.describe(role="Role applied to muted members")
    @require_admin()
    @commands.guild_only()
    async def setmuterole(self, ctx: commands.Context, role: discord.Role) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("mute_role", role.id)
        await ctx.send(embed=emb.success(f"Mute role set to {role.mention}"))

    @commands.hybrid_command(name="setautorole", description="Set the auto role (given to new members)")
    @app_commands.describe(role="Role automatically assigned to new members")
    @require_admin()
    @commands.guild_only()
    async def setautorole(self, ctx: commands.Context, role: discord.Role) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("auto_role", role.id)
        await ctx.send(embed=emb.success(f"Auto role set to {role.mention}"))

    # ── Feature toggles ────────────────────────────────────────────────────────

    @commands.hybrid_command(name="toggle", description="Toggle a bot feature on or off")
    @app_commands.describe(feature="Feature to toggle")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Welcome",   value="welcome_enabled"),
        app_commands.Choice(name="Leave",     value="leave_enabled"),
        app_commands.Choice(name="Leveling",  value="leveling_enabled"),
        app_commands.Choice(name="Economy",   value="economy_enabled"),
        app_commands.Choice(name="AutoMod",   value="automod_enabled"),
        app_commands.Choice(name="Logging",   value="logging_enabled"),
        app_commands.Choice(name="AntiSpam",  value="anti_spam_enabled"),
        app_commands.Choice(name="AntiLink",  value="anti_link_enabled"),
    ])
    @require_admin()
    @commands.guild_only()
    async def toggle(self, ctx: commands.Context, feature: str) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        current = gs.get(feature, False)
        await gs.set(feature, not current)
        status = "✅ enabled" if not current else "❌ disabled"
        label  = feature.replace("_", " ").title()
        await ctx.send(embed=emb.success(f"**{label}** is now **{status}**"))

    # ── Prefix ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="setprefix", description="Change the bot's command prefix for this server")
    @app_commands.describe(prefix="New command prefix (e.g. !, ?, $)")
    @require_admin()
    @commands.guild_only()
    async def setprefix(self, ctx: commands.Context, prefix: str) -> None:
        if len(prefix) > 5:
            return await ctx.send(embed=emb.error("Prefix must be 5 characters or fewer"))
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("prefix", prefix)
        await ctx.send(embed=emb.success(f"Prefix set to `{prefix}`"))

    # ── Automod words ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name="addword", description="Add a word to the automod banned words list")
    @app_commands.describe(word="Word to ban")
    @require_admin()
    @commands.guild_only()
    async def addword(self, ctx: commands.Context, *, word: str) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        words: list[str] = gs.banned_words
        word_lower = word.lower()
        if word_lower in words:
            return await ctx.send(embed=emb.warning("That word is already in the list"))
        words.append(word_lower)
        await gs.set("banned_words", words)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(embed=emb.success("Word added to the banned list"), delete_after=5)

    @commands.hybrid_command(name="removeword", description="Remove a word from the automod banned words list")
    @app_commands.describe(word="Word to remove")
    @require_admin()
    @commands.guild_only()
    async def removeword(self, ctx: commands.Context, *, word: str) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        words: list[str] = gs.banned_words
        word_lower = word.lower()
        if word_lower not in words:
            return await ctx.send(embed=emb.error("That word is not in the list"))
        words.remove(word_lower)
        await gs.set("banned_words", words)
        await ctx.send(embed=emb.success("Word removed from the banned list"))

    @commands.hybrid_command(name="bannedwords", description="List all banned words")
    @require_mod()
    @commands.guild_only()
    async def bannedwords(self, ctx: commands.Context) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        words = gs.banned_words
        if not words:
            return await ctx.send(embed=emb.info("No banned words configured"))
        embed = emb.build(
            title="🚫 Banned Words",
            description="`" + "`, `".join(words) + "`",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed, ephemeral=True)

    # ── Color roles ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="addcolorrole", description="Add a color role to the color panel")
    @app_commands.describe(
        role="The role to add",
        label="Button label (defaults to role name)",
        emoji="Button emoji",
    )
    @require_admin()
    @commands.guild_only()
    async def addcolorrole(
        self,
        ctx: commands.Context,
        role: discord.Role,
        label: str | None = None,
        emoji: str = "🎨",
    ) -> None:
        label = label or role.name
        await db.execute(
            "INSERT OR REPLACE INTO color_roles (guild_id, role_id, label, emoji) VALUES (?,?,?,?)",
            (ctx.guild.id, role.id, label, emoji),
        )
        await ctx.send(embed=emb.success(f"Color role {role.mention} added with label **{label}**"))

    @commands.hybrid_command(name="removecolorrole", description="Remove a color role from the panel")
    @app_commands.describe(role="The role to remove")
    @require_admin()
    @commands.guild_only()
    async def removecolorrole(self, ctx: commands.Context, role: discord.Role) -> None:
        await db.execute(
            "DELETE FROM color_roles WHERE guild_id = ? AND role_id = ?",
            (ctx.guild.id, role.id),
        )
        await ctx.send(embed=emb.success(f"Color role {role.mention} removed"))

    @commands.hybrid_command(name="colorpanel", description="Post the color role selection panel")
    @app_commands.describe(channel="Channel to post the panel in")
    @require_admin()
    @commands.guild_only()
    async def colorpanel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        target = channel or ctx.channel
        rows = await db.fetchall(
            "SELECT role_id, label, emoji, style FROM color_roles WHERE guild_id = ?",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.error("No color roles configured. Use `/addcolorrole` first."))
        if len(rows) > 25:
            return await ctx.send(embed=emb.error("Maximum 25 color roles per panel."))
        roles_data = [(r["role_id"], r["label"], r["emoji"], r["style"]) for r in rows]
        embed = emb.build(
            title="🎨 Color Roles",
            description="Click a button to get a color role.\nClick again to remove it.\nPicking a new color removes your old one.",
            color=discord.Color.from_rgb(255, 255, 255),
        )
        view = ColorRolePanelView(roles_data)
        await target.send(embed=embed, view=view)
        await ctx.send(embed=emb.success(f"Color panel posted in {target.mention}"), ephemeral=True)

    # ── Custom commands ────────────────────────────────────────────────────────

    @commands.hybrid_command(name="addcmd", description="Create a custom text command")
    @app_commands.describe(name="Command name (no prefix)", response="Bot's response text")
    @require_admin()
    @commands.guild_only()
    async def addcmd(self, ctx: commands.Context, name: str, *, response: str) -> None:
        name = name.lower().strip()
        if not name.isidentifier():
            return await ctx.send(embed=emb.error("Command name must be alphanumeric (no spaces)"))
        await db.execute(
            """INSERT INTO custom_commands (name, guild_id, response, created_by)
               VALUES (?,?,?,?)
               ON CONFLICT(name, guild_id) DO UPDATE SET response = excluded.response""",
            (name, ctx.guild.id, response, ctx.author.id),
        )
        gs = await GuildSettings.get(ctx.guild.id)
        custom_commands_cache[(ctx.guild.id, name)] = response
        prefix = gs.prefix
        await ctx.send(embed=emb.success(f"Custom command `{prefix}{name}` created!"))

    @commands.hybrid_command(name="delcmd", description="Delete a custom text command")
    @app_commands.describe(name="Command name to delete")
    @require_admin()
    @commands.guild_only()
    async def delcmd(self, ctx: commands.Context, name: str) -> None:
        name = name.lower().strip()
        await db.execute(
            "DELETE FROM custom_commands WHERE name = ? AND guild_id = ?",
            (name, ctx.guild.id),
        )
        custom_commands_cache.pop((ctx.guild.id, name), None)
        await ctx.send(embed=emb.success(f"Custom command `{name}` deleted"))

    @commands.hybrid_command(name="listcmds", description="List all custom commands for this server")
    @commands.guild_only()
    async def listcmds(self, ctx: commands.Context) -> None:
        rows = await db.fetchall(
            "SELECT name, uses FROM custom_commands WHERE guild_id = ? ORDER BY uses DESC",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No custom commands configured"))
        gs   = await GuildSettings.get(ctx.guild.id)
        lines = [f"`{gs.prefix}{r['name']}` — {r['uses']} uses" for r in rows]
        embed = emb.build(title="📋 Custom Commands", description="\n".join(lines), color=discord.Color.blurple())
        await ctx.send(embed=embed)

    # ── Reaction roles ─────────────────────────────────────────────────────────

    @commands.hybrid_command(name="reactionrole", description="Link a reaction emoji to a role on a message")
    @app_commands.describe(
        message_id="ID of the message",
        emoji="Emoji to react with",
        role="Role to assign",
    )
    @require_admin()
    @commands.guild_only()
    async def reactionrole(self, ctx: commands.Context, message_id: str, emoji: str, role: discord.Role) -> None:
        try:
            mid = int(message_id)
            msg = await ctx.channel.fetch_message(mid)
            await msg.add_reaction(emoji)
        except Exception:
            return await ctx.send(embed=emb.error("Could not find message or add reaction in this channel."))
        await db.execute(
            "INSERT OR REPLACE INTO reaction_roles (message_id, emoji, role_id, guild_id) VALUES (?,?,?,?)",
            (mid, emoji, role.id, ctx.guild.id),
        )
        reaction_roles_cache[(mid, emoji)] = role.id
        await ctx.send(embed=emb.success(f"Reaction role set: {emoji} → {role.mention}"))

    @commands.hybrid_command(name="rmreactionrole", description="Remove a reaction role")
    @app_commands.describe(message_id="Message ID", emoji="Emoji to remove")
    @require_admin()
    @commands.guild_only()
    async def rmreactionrole(self, ctx: commands.Context, message_id: str, emoji: str) -> None:
        mid = int(message_id)
        await db.execute(
            "DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (mid, emoji),
        )
        reaction_roles_cache.pop((mid, emoji), None)
        await ctx.send(embed=emb.success(f"Reaction role {emoji} removed from message `{mid}`"))

    # ── Settings overview ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="settings", description="Show current server settings")
    @require_mod()
    @commands.guild_only()
    async def settings_cmd(self, ctx: commands.Context) -> None:
        gs = await GuildSettings.get(ctx.guild.id)

        def ch(cid: int | None) -> str:
            if cid is None:
                return "Not set"
            c = ctx.guild.get_channel(cid)
            return c.mention if c else f"Unknown ({cid})"

        def role(rid: int | None) -> str:
            if rid is None:
                return "Not set"
            r = ctx.guild.get_role(rid)
            return r.mention if r else f"Unknown ({rid})"

        def tog(val: bool) -> str:
            return "✅ On" if val else "❌ Off"

        embed = emb.build(
            title=f"⚙️ Settings — {ctx.guild.name}",
            color=discord.Color.blurple(),
            fields=[
                ("Prefix",            f"`{gs.prefix}`",              True),
                ("Welcome Channel",   ch(gs.welcome_channel),        True),
                ("Leave Channel",     ch(gs.leave_channel),          True),
                ("Log Channel",       ch(gs.log_channel),            True),
                ("Level-Up Channel",  ch(gs.level_up_channel),       True),
                ("Ticket Category",   ch(gs.ticket_category),        True),
                ("Mute Role",         role(gs.mute_role),            True),
                ("Auto Role",         role(gs.auto_role),            True),
                ("Welcome",           tog(gs.welcome_enabled),       True),
                ("Leave",             tog(gs.leave_enabled),         True),
                ("Leveling",          tog(gs.leveling_enabled),      True),
                ("Economy",           tog(gs.economy_enabled),       True),
                ("AutoMod",           tog(gs.automod_enabled),       True),
                ("Logging",           tog(gs.logging_enabled),       True),
                ("Anti-Spam",         tog(gs.anti_spam_enabled),     True),
                ("Anti-Link",         tog(gs.anti_link_enabled),     True),
                ("Currency",          f"{gs.currency_symbol} {gs.currency_name}", True),
                ("Banned Words",      str(len(gs.banned_words)),     True),
            ],
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="resetguild", description="Reset ALL server settings to defaults (IRREVERSIBLE)")
    @require_admin()
    @commands.guild_only()
    async def resetguild(self, ctx: commands.Context) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.reset_all()
        await ctx.send(embed=emb.success("All server settings have been reset to defaults."))

    # ── Welcome / Leave message customization ─────────────────────────────────

    @commands.hybrid_command(name="setwelcomemsg", description="Customize the welcome message")
    @app_commands.describe(message="Use {user}, {server}, {count} as placeholders")
    @require_admin()
    @commands.guild_only()
    async def setwelcomemsg(self, ctx: commands.Context, *, message: str) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("welcome_message", message)
        preview = message.format(user=ctx.author.mention, server=ctx.guild.name, count=ctx.guild.member_count)
        await ctx.send(embed=emb.success(f"Welcome message updated!\n\n**Preview:** {preview}"))

    @commands.hybrid_command(name="setleavemsg", description="Customize the leave message")
    @app_commands.describe(message="Use {username}, {server}, {count} as placeholders")
    @require_admin()
    @commands.guild_only()
    async def setleavemsg(self, ctx: commands.Context, *, message: str) -> None:
        gs = await GuildSettings.get(ctx.guild.id)
        await gs.set("leave_message", message)
        preview = message.format(username=ctx.author.name, server=ctx.guild.name, count=ctx.guild.member_count)
        await ctx.send(embed=emb.success(f"Leave message updated!\n\n**Preview:** {preview}"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
    log.info("Admin cog loaded")
