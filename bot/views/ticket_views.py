# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Ticket Views (Fixed)
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio

import discord

from core.database import db
from core.settings import GuildSettings
import core.embeds as emb
from core.logger import get_logger

log = get_logger("ticket_views")


class TicketPanelView(discord.ui.View):
    """Persistent view shown in the ticket panel embed. Survives restarts."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📩 Open Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:open",
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message(
                "❌ This must be used inside a server.", ephemeral=True
            )

        gs = await GuildSettings.fetch(guild.id)

        # Check for an existing open ticket owned by this user
        existing = await db.fetchone(
            "SELECT channel_id FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'",
            (interaction.user.id, guild.id),
        )
        if existing:
            ch = guild.get_channel(existing["channel_id"])
            if ch:
                return await interaction.response.send_message(
                    f"❌ You already have an open ticket: {ch.mention}", ephemeral=True
                )
            # Channel was deleted externally — mark the stale row closed
            await db.execute(
                "UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP "
                "WHERE user_id = ? AND guild_id = ? AND status = 'open'",
                (interaction.user.id, guild.id),
            )

        # Resolve category (may be None — channel will be created at guild root)
        category: discord.CategoryChannel | None = None
        if gs.ticket_category:
            category = guild.get_channel(gs.ticket_category)

        # Build permission overwrites
        overwrites: dict = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user:   discord.PermissionOverwrite(
                read_messages=True, send_messages=True, attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True
            ),
        }
        # Give all mod/admin roles read access
        for role in guild.roles:
            if role.permissions.manage_messages or role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )

        safe_name = interaction.user.name.lower().replace(" ", "-")[:20]
        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{safe_name}",
                category=category,
                overwrites=overwrites,
                reason=f"Ticket opened by {interaction.user} ({interaction.user.id})",
            )
        except discord.HTTPException as e:
            log.error("Failed to create ticket channel for %s: %s", interaction.user, e)
            return await interaction.response.send_message(
                "❌ Failed to create a ticket channel. Please contact an admin.", ephemeral=True
            )

        await db.execute(
            "INSERT INTO tickets (channel_id, user_id, guild_id) VALUES (?, ?, ?)",
            (channel.id, interaction.user.id, guild.id),
        )

        embed = emb.build(
            title="🎫 Support Ticket",
            description=(
                f"Hello {interaction.user.mention}! A staff member will be with you shortly.\n\n"
                "Please describe your issue in as much detail as possible.\n"
                "Click **Close Ticket** when your issue has been resolved."
            ),
            color=discord.Color.blurple(),
            thumbnail=interaction.user.display_avatar.url,
        )
        await channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(
            f"✅ Your ticket has been created: {channel.mention}", ephemeral=True
        )
        log.info("Ticket opened: channel=%s user=%s guild=%s", channel.id, interaction.user.id, guild.id)


class TicketControlView(discord.ui.View):
    """Buttons inside the ticket channel. Survives restarts via custom_id."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        guild = interaction.guild
        if not guild:
            return

        row = await db.fetchone(
            "SELECT id, user_id FROM tickets WHERE channel_id = ? AND status = 'open'",
            (interaction.channel.id,),
        )
        if not row:
            return await interaction.response.send_message(
                "❌ This is not an active ticket.", ephemeral=True
            )

        is_owner = interaction.user.id == row["user_id"]
        is_mod   = interaction.user.guild_permissions.manage_messages
        if not (is_owner or is_mod):
            return await interaction.response.send_message(
                "❌ Only the ticket owner or a moderator can close this ticket.", ephemeral=True
            )

        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (row["id"],),
        )

        embed = emb.build(
            title="🔒 Ticket Closing",
            description=f"Closed by {interaction.user.mention}. This channel will be deleted in 5 seconds.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.HTTPException as e:
            log.warning("Could not delete ticket channel %s: %s", interaction.channel.id, e)

    @discord.ui.button(
        label="📋 Claim",
        style=discord.ButtonStyle.success,
        custom_id="ticket:claim",
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message(
                "❌ Only moderators can claim tickets.", ephemeral=True
            )
        button.disabled = True
        button.label    = f"✅ Claimed by {interaction.user.display_name}"
        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            pass
        await interaction.response.send_message(
            embed=emb.success(f"Ticket claimed by {interaction.user.mention}!")
        )
