# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Ticket Views
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import discord
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
import core.embeds as emb
from core.logger import get_logger

log = get_logger("ticket_views")


class TicketPanelView(discord.ui.View):
    """Persistent view shown in the ticket panel embed."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Open Ticket", style=discord.ButtonStyle.primary, custom_id="ticket:open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("❌ This must be used in a server.", ephemeral=True)

        gs = await GuildSettings.get(guild.id)

        # Check for existing open ticket
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

        # Resolve category
        category = None
        if gs.ticket_category:
            category = guild.get_channel(gs.ticket_category)

        # Build overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user:   discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }

        # Add moderators
        for role in guild.roles:
            if role.permissions.manage_messages or role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{interaction.user.name.lower().replace(' ', '-')}",
                category=category,
                overwrites=overwrites,
                reason=f"Ticket opened by {interaction.user}",
            )
        except discord.HTTPException as e:
            log.error("Failed to create ticket channel: %s", e)
            return await interaction.response.send_message("❌ Failed to create ticket channel.", ephemeral=True)

        await db.execute(
            "INSERT INTO tickets (channel_id, user_id, guild_id) VALUES (?,?,?)",
            (channel.id, interaction.user.id, guild.id),
        )

        embed = emb.build(
            title="🎫 Support Ticket",
            description=(
                f"Hello {interaction.user.mention}! Staff will be with you shortly.\n"
                "Please describe your issue and be patient."
            ),
            color=discord.Color.blurple(),
            thumbnail=interaction.user.display_avatar.url,
        )
        await channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(
            f"✅ Your ticket has been created: {channel.mention}", ephemeral=True
        )
        log.info("Ticket opened by %s in guild %s", interaction.user, guild.name)


class TicketControlView(discord.ui.View):
    """Buttons inside the ticket channel."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        guild = interaction.guild
        if not guild:
            return

        row = await db.fetchone(
            "SELECT id, user_id FROM tickets WHERE channel_id = ? AND status = 'open'",
            (interaction.channel.id,),
        )
        if not row:
            return await interaction.response.send_message("❌ This is not an active ticket.", ephemeral=True)

        # Only ticket owner or mods can close
        is_owner = interaction.user.id == row["user_id"]
        is_mod   = interaction.user.guild_permissions.manage_messages
        if not (is_owner or is_mod):
            return await interaction.response.send_message("❌ Only the ticket owner or a moderator can close this.", ephemeral=True)

        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (row["id"],),
        )
        embed = emb.build(
            title="🔒 Ticket Closed",
            description=f"Closed by {interaction.user.mention}. This channel will be deleted in 5 seconds.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=5))
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.HTTPException:
            pass

    @discord.ui.button(label="📋 Claim", style=discord.ButtonStyle.success, custom_id="ticket:claim")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ Only moderators can claim tickets.", ephemeral=True)
        await interaction.response.send_message(
            embed=emb.success(f"Ticket claimed by {interaction.user.mention}!")
        )
        # Disable claim button after claiming
        button.disabled = True
        button.label = f"✅ Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)
