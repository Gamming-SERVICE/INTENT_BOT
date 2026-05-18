# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Market Views
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import discord
from core.database import db
import core.embeds as emb
from core.logger import get_logger

log = get_logger("market_views")


class TradeConfirmView(discord.ui.View):
    """
    Shown to the trade recipient to accept or decline.
    trade_id: DB row id
    sender: Member who initiated
    receiver: Member who must confirm
    item_name, quantity, price: trade details
    currency_symbol: from guild settings
    """

    def __init__(
        self,
        trade_id: int,
        sender: discord.Member,
        receiver: discord.Member,
        item_name: str,
        quantity: int,
        price: int,
        currency_symbol: str,
    ) -> None:
        super().__init__(timeout=120)
        self.trade_id        = trade_id
        self.sender          = sender
        self.receiver        = receiver
        self.item_name       = item_name
        self.quantity        = quantity
        self.price           = price
        self.currency_symbol = currency_symbol

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.receiver.id:
            return await interaction.response.send_message("❌ This trade is not for you.", ephemeral=True)

        # Check receiver balance
        row = await db.fetchone(
            "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
            (self.receiver.id, interaction.guild.id),
        )
        if not row or row["balance"] < self.price:
            await db.execute(
                "UPDATE trades SET status = 'cancelled' WHERE id = ?", (self.trade_id,)
            )
            await interaction.response.edit_message(
                embed=emb.error("You don't have enough coins to accept this trade."), view=None
            )
            return

        # Check sender still has item
        trade_row = await db.fetchone(
            "SELECT item_id, quantity FROM trades WHERE id = ? AND status = 'pending'",
            (self.trade_id,),
        )
        if not trade_row:
            return await interaction.response.send_message("❌ This trade is no longer valid.", ephemeral=True)

        sender_item = await db.fetchone(
            "SELECT quantity FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (self.sender.id, interaction.guild.id, trade_row["item_id"]),
        )
        if not sender_item or sender_item["quantity"] < self.quantity:
            await db.execute("UPDATE trades SET status = 'cancelled' WHERE id = ?", (self.trade_id,))
            await interaction.response.edit_message(
                embed=emb.error("The sender no longer has that item."), view=None
            )
            return

        # Execute trade: deduct from sender item, add to receiver item, transfer money
        new_qty = sender_item["quantity"] - self.quantity
        if new_qty <= 0:
            await db.execute(
                "DELETE FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                (self.sender.id, interaction.guild.id, trade_row["item_id"]),
            )
        else:
            await db.execute(
                "UPDATE user_items SET quantity = ? WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                (new_qty, self.sender.id, interaction.guild.id, trade_row["item_id"]),
            )

        await db.execute(
            """INSERT INTO user_items (user_id, guild_id, item_id, quantity) VALUES (?,?,?,?)
               ON CONFLICT(user_id, guild_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity""",
            (self.receiver.id, interaction.guild.id, trade_row["item_id"], self.quantity),
        )

        # Transfer money
        await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
            (self.price, self.receiver.id, interaction.guild.id),
        )
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
            (self.price, self.sender.id, interaction.guild.id),
        )
        await db.execute(
            "UPDATE trades SET status = 'completed', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (self.trade_id,),
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            embed=emb.build(
                title="✅ Trade Completed",
                color=discord.Color.green(),
                fields=[
                    ("Item",     f"{self.item_name} ×{self.quantity}", True),
                    ("Price",    f"{self.currency_symbol} {self.price:,}", True),
                    ("From",     self.sender.mention,    True),
                    ("To",       self.receiver.mention,  True),
                ],
            ),
            view=self,
        )

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id not in (self.receiver.id, self.sender.id):
            return await interaction.response.send_message("❌ Not your trade.", ephemeral=True)
        await db.execute("UPDATE trades SET status = 'declined' WHERE id = ?", (self.trade_id,))
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=emb.error("Trade declined."), view=self
        )

    async def on_timeout(self) -> None:
        await db.execute("UPDATE trades SET status = 'expired' WHERE id = ?", (self.trade_id,))
