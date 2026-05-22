# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Tickets Cog
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import datetime

import discord
from discord import app_commands
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.permissions import require_mod, require_admin
import core.embeds as emb
from core.logger import get_logger
from views.ticket_views import TicketPanelView, TicketControlView

log = get_logger("tickets")


def _parse_dt(iso_str: str) -> datetime.datetime:
    """Safely parse an ISO datetime string from SQLite."""
    try:
        return datetime.datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return datetime.datetime.utcnow()


class Tickets(commands.Cog, name="Tickets"):
    """Ticket system — panel, listing, and forced close."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="ticketpanel", description="Post the ticket opening panel in a channel")
    @app_commands.describe(channel="Channel to post the panel in")
    @require_admin()
    @commands.guild_only()
    async def ticketpanel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        target = channel or ctx.channel
        embed = emb.build(
            title="🎫 Support Tickets",
            description=(
                "Need help? Click the button below to open a support ticket.\n"
                "Our staff will assist you shortly."
            ),
            color=discord.Color.blurple(),
        )
        await target.send(embed=embed, view=TicketPanelView())
        await ctx.send(embed=emb.success(f"Ticket panel posted in {target.mention}"), ephemeral=True)

    @commands.hybrid_command(name="tickets", description="List open tickets in this server")
    @require_mod()
    @commands.guild_only()
    async def list_tickets(self, ctx: commands.Context) -> None:
        rows = await db.fetchall(
            "SELECT channel_id, user_id, created_at FROM tickets "
            "WHERE guild_id = ? AND status = 'open' ORDER BY created_at DESC",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No open tickets."))

        lines = []
        for r in rows[:20]:
            ch = ctx.guild.get_channel(r["channel_id"])
            ch_str = ch.mention if ch else f"*(deleted #{r['channel_id']})*"
            dt = _parse_dt(r["created_at"])
            ts = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
            lines.append(f"{ch_str} — <@{r['user_id']}> — <t:{ts}:R>")

        embed = emb.build(
            title=f"🎫 Open Tickets ({len(rows)})",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="closeticket", description="Force-close a ticket channel")
    @app_commands.describe(channel="Ticket channel to close (defaults to current channel)")
    @require_mod()
    @commands.guild_only()
    async def closeticket(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        target = channel or ctx.channel
        row = await db.fetchone(
            "SELECT id FROM tickets WHERE channel_id = ? AND status = 'open'",
            (target.id,),
        )
        if not row:
            return await ctx.send(embed=emb.error("That channel is not an active open ticket."))

        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (row["id"],),
        )
        await ctx.send(embed=emb.success(f"Ticket **{target.name}** closed. Deleting in 5 seconds..."))
        await asyncio.sleep(5)
        try:
            await target.delete(reason=f"Force-closed by {ctx.author}")
        except discord.HTTPException as e:
            log.warning("Failed to delete ticket channel %s: %s", target.id, e)

    @commands.hybrid_command(name="addtosupport", description="Add a member to this ticket channel")
    @app_commands.describe(member="Member to add")
    @require_mod()
    @commands.guild_only()
    async def addtosupport(self, ctx: commands.Context, member: discord.Member) -> None:
        row = await db.fetchone(
            "SELECT id FROM tickets WHERE channel_id = ? AND status = 'open'",
            (ctx.channel.id,),
        )
        if not row:
            return await ctx.send(embed=emb.error("This command must be used inside a ticket channel."))
        await ctx.channel.set_permissions(
            member, read_messages=True, send_messages=True,
            reason=f"Added to ticket by {ctx.author}",
        )
        await ctx.send(embed=emb.success(f"{member.mention} has been added to this ticket."))

    @commands.hybrid_command(name="removefromsupport", description="Remove a member from this ticket")
    @app_commands.describe(member="Member to remove")
    @require_mod()
    @commands.guild_only()
    async def removefromsupport(self, ctx: commands.Context, member: discord.Member) -> None:
        row = await db.fetchone(
            "SELECT id FROM tickets WHERE channel_id = ? AND status = 'open'",
            (ctx.channel.id,),
        )
        if not row:
            return await ctx.send(embed=emb.error("This command must be used inside a ticket channel."))
        await ctx.channel.set_permissions(
            member, overwrite=None,
            reason=f"Removed from ticket by {ctx.author}",
        )
        await ctx.send(embed=emb.success(f"{member.mention} has been removed from this ticket."))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
    log.info("Tickets cog loaded")
ENDOFFILE
echo "Done"
