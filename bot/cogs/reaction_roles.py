# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Reaction Roles Cog
#                   PREFIX-ONLY | No slash commands
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import discord
from discord.ext import commands

from core.database import db
from core.cache import reaction_roles_cache
from core.permissions import require_admin
import core.embeds as emb
from core.logger import get_logger

log = get_logger("reaction_roles")


class ReactionRoles(commands.Cog, name="ReactionRoles"):
    """Reaction role management — assign roles via emoji reactions."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.command(name="rradd", aliases=["addreactionrole"])
    @require_admin()
    @commands.guild_only()
    async def rradd(self, ctx: commands.Context, message_id: str, emoji: str, role: discord.Role) -> None:
        """Add a reaction role to a message. Usage: !rradd <message_id> <emoji> @Role
        The bot will add the reaction to the message automatically."""
        try:
            mid = int(message_id)
        except ValueError:
            return await ctx.send(embed=emb.error("Invalid message ID. Must be a number."))

        # Try to fetch the message in the current channel
        try:
            msg = await ctx.channel.fetch_message(mid)
        except discord.NotFound:
            return await ctx.send(embed=emb.error(
                f"Message `{mid}` not found in {ctx.channel.mention}.\n"
                "Run this command in the same channel as the message."
            ))
        except discord.HTTPException as e:
            return await ctx.send(embed=emb.error(f"Failed to fetch message: {e}"))

        # Validate the bot can manage this role
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=emb.error("I cannot manage that role — it's above my highest role."))

        # Add the reaction to the message
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException as e:
            return await ctx.send(embed=emb.error(f"Could not add reaction `{emoji}`: {e}"))

        # Save to database
        await db.execute(
            "INSERT OR REPLACE INTO reaction_roles (message_id, emoji, role_id, guild_id) VALUES (?,?,?,?)",
            (mid, emoji, role.id, ctx.guild.id),
        )

        # Update in-memory cache
        reaction_roles_cache[(mid, emoji)] = role.id

        log.info("Reaction role added: msg=%s emoji=%s role=%s guild=%s", mid, emoji, role.id, ctx.guild.id)
        await ctx.send(embed=emb.success(
            f"Reaction role added!\n"
            f"Emoji: {emoji}\n"
            f"Role: {role.mention}\n"
            f"Message: [Jump]({msg.jump_url})"
        ))

    @commands.command(name="rrremove", aliases=["removereactionrole"])
    @require_admin()
    @commands.guild_only()
    async def rrremove(self, ctx: commands.Context, message_id: str, emoji: str) -> None:
        """Remove a reaction role. Usage: !rrremove <message_id> <emoji>"""
        try:
            mid = int(message_id)
        except ValueError:
            return await ctx.send(embed=emb.error("Invalid message ID."))

        existing = await db.fetchone(
            "SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ? AND guild_id = ?",
            (mid, emoji, ctx.guild.id),
        )
        if not existing:
            return await ctx.send(embed=emb.error("No reaction role found for that message/emoji combination."))

        await db.execute(
            "DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ? AND guild_id = ?",
            (mid, emoji, ctx.guild.id),
        )
        reaction_roles_cache.pop((mid, emoji), None)

        # Try to remove the bot's reaction from the message
        try:
            msg = await ctx.channel.fetch_message(mid)
            await msg.clear_reaction(emoji)
        except Exception:
            pass

        await ctx.send(embed=emb.success(f"Reaction role `{emoji}` removed from message `{mid}`."))

    @commands.command(name="rrlist", aliases=["listreactionroles"])
    @require_admin()
    @commands.guild_only()
    async def rrlist(self, ctx: commands.Context) -> None:
        """List all reaction roles in this server. Usage: !rrlist"""
        rows = await db.fetchall(
            "SELECT message_id, emoji, role_id FROM reaction_roles WHERE guild_id = ? ORDER BY message_id",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No reaction roles configured in this server."))

        lines = []
        for r in rows:
            role = ctx.guild.get_role(r["role_id"])
            role_str = role.mention if role else f"Deleted role ({r['role_id']})"
            lines.append(f"Message `{r['message_id']}` • {r['emoji']} → {role_str}")

        await ctx.send(embed=emb.build(
            title=f"🎭 Reaction Roles ({len(rows)})",
            description="\n".join(lines[:20]),
            color=discord.Color.blurple(),
        ))

    @commands.command(name="rrclear")
    @require_admin()
    @commands.guild_only()
    async def rrclear(self, ctx: commands.Context, message_id: str) -> None:
        """Remove all reaction roles from a message. Usage: !rrclear <message_id>"""
        try:
            mid = int(message_id)
        except ValueError:
            return await ctx.send(embed=emb.error("Invalid message ID."))

        rows = await db.fetchall(
            "SELECT emoji FROM reaction_roles WHERE message_id = ? AND guild_id = ?",
            (mid, ctx.guild.id),
        )
        if not rows:
            return await ctx.send(embed=emb.error("No reaction roles found for that message."))

        await db.execute(
            "DELETE FROM reaction_roles WHERE message_id = ? AND guild_id = ?",
            (mid, ctx.guild.id),
        )
        for row in rows:
            reaction_roles_cache.pop((mid, row["emoji"]), None)

        # Try to clear all reactions from the message
        try:
            msg = await ctx.channel.fetch_message(mid)
            await msg.clear_reactions()
        except Exception:
            pass

        await ctx.send(embed=emb.success(f"Cleared {len(rows)} reaction role(s) from message `{mid}`."))

    # ── Event listeners ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        role_id = reaction_roles_cache.get((payload.message_id, str(payload.emoji)))
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role = guild.get_role(role_id)
        if not role:
            log.warning("Reaction role: role %d not found in guild %d", role_id, payload.guild_id)
            return

        try:
            member = await guild.fetch_member(payload.user_id)
            await member.add_roles(role, reason="Reaction role")
            log.debug("Added role %s to %s via reaction", role.name, member)
        except discord.Forbidden:
            log.warning("Missing permissions to add role %s in guild %s", role.name, guild.name)
        except discord.HTTPException as e:
            log.warning("Failed to add reaction role: %s", e)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return

        role_id = reaction_roles_cache.get((payload.message_id, str(payload.emoji)))
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role = guild.get_role(role_id)
        if not role:
            return

        try:
            member = await guild.fetch_member(payload.user_id)
            await member.remove_roles(role, reason="Reaction role removed")
            log.debug("Removed role %s from %s via reaction", role.name, member)
        except discord.Forbidden:
            log.warning("Missing permissions to remove role %s in guild %s", role.name, guild.name)
        except discord.HTTPException as e:
            log.warning("Failed to remove reaction role: %s", e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRoles(bot))
    log.info("ReactionRoles cog loaded")
