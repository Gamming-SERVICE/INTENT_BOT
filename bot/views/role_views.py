# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Role Views
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import discord
from core.logger import get_logger
import core.embeds as emb

log = get_logger("role_views")


class ColorRolePanelView(discord.ui.View):
    """
    Persistent color-role button panel.
    roles_data: list of (role_id, label, emoji, style)
    """

    def __init__(self, roles_data: list[tuple]) -> None:
        super().__init__(timeout=None)
        for role_id, label, emoji, style in roles_data:
            btn_style = {
                1: discord.ButtonStyle.primary,
                2: discord.ButtonStyle.secondary,
                3: discord.ButtonStyle.success,
                4: discord.ButtonStyle.danger,
            }.get(style, discord.ButtonStyle.secondary)

            btn = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=btn_style,
                custom_id=f"colorrole:{role_id}",
            )
            btn.callback = self._make_callback(role_id)
            self.add_item(btn)

    def _make_callback(self, role_id: int):
        async def callback(interaction: discord.Interaction) -> None:
            guild = interaction.guild
            if not guild:
                return
            role = guild.get_role(role_id)
            if not role:
                return await interaction.response.send_message("❌ Role not found.", ephemeral=True)

            # Fetch all color roles for this guild from DB to remove old ones
            from core.database import db
            rows = await db.fetchall(
                "SELECT role_id FROM color_roles WHERE guild_id = ?",
                (guild.id,),
            )
            all_color_role_ids = {r["role_id"] for r in rows}
            member = interaction.user

            # Remove any existing color roles
            roles_to_remove = [r for r in member.roles if r.id in all_color_role_ids and r.id != role_id]
            if roles_to_remove:
                try:
                    await member.remove_roles(*roles_to_remove, reason="Color role swap")
                except discord.HTTPException:
                    pass

            # Toggle the selected role
            if role in member.roles:
                await member.remove_roles(role, reason="Color role removed")
                await interaction.response.send_message(
                    embed=emb.success(f"Removed color role **{role.name}**"), ephemeral=True
                )
            else:
                await member.add_roles(role, reason="Color role selected")
                await interaction.response.send_message(
                    embed=emb.success(f"Applied color role **{role.name}**"), ephemeral=True
                )
        return callback


class PaginatorView(discord.ui.View):
    """Generic paginator for multi-page embeds."""

    def __init__(self, pages: list[discord.Embed], author_id: int) -> None:
        super().__init__(timeout=120)
        self.pages      = pages
        self.current    = 0
        self.author_id  = author_id
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
