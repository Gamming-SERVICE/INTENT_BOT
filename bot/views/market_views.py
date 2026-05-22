# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Market Views (Race-Condition-Safe)
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import json

import discord

from core.database import db
import core.embeds as emb
from core.logger import get_logger

log = get_logger("market_views")

# Per-trade lock to prevent double-acceptance race conditions
_trade_locks: dict[int, asyncio.Lock] = {}


def _get_trade_lock(trade_id: int) -> asyncio.Lock:
    if trade_id not in _trade_locks:
        _trade_locks[trade_id] = asyncio.Lock()
    return _trade_locks[trade_id]


class TradeConfirmView(discord.ui.View):
    """
    Trade offer confirmation panel shown to the receiver.

    Race-condition protected:
    - Uses per-trade asyncio.Lock to prevent concurrent accept calls
    - Uses DB IMMEDIATE transaction to atomically verify and apply
    - Cleans up the lock dict on resolution
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
            return await interaction.response.send_message(
                "❌ This trade offer is not for you.", ephemeral=True
            )

        lock = _get_trade_lock(self.trade_id)
        if lock.locked():
            return await interaction.response.send_message(
                "⏳ Trade is being processed, please wait.", ephemeral=True
            )

        async with lock:
            # Immediately defer so Discord doesn't time out
            await interaction.response.defer()

            try:
                async with db.transaction() as conn:
                    # Verify trade is still pending (prevents double-accept)
                    cursor = await conn.execute(
                        "SELECT * FROM trades WHERE id = ? AND status = 'pending'",
                        (self.trade_id,),
                    )
                    trade_row = await cursor.fetchone()
                    if not trade_row:
                        await interaction.followup.send(
                            embed=emb.error("This trade is no longer available."), ephemeral=True
                        )
                        return

                    trade_row = dict(trade_row)

                    # Verify receiver balance
                    cursor = await conn.execute(
                        "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
                        (self.receiver.id, interaction.guild.id),
                    )
                    recv_row = await cursor.fetchone()
                    if not recv_row or recv_row["balance"] < self.price:
                        await conn.execute(
                            "UPDATE trades SET status = 'cancelled' WHERE id = ?",
                            (self.trade_id,),
                        )
                        await interaction.followup.send(
                            embed=emb.error(
                                f"Insufficient funds. You need {self.currency_symbol} {self.price:,}."
                            ),
                            ephemeral=True,
                        )
                        return

                    # Verify sender still has enough of the item
                    cursor = await conn.execute(
                        "SELECT quantity FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                        (self.sender.id, interaction.guild.id, trade_row["item_id"]),
                    )
                    sender_inv = await cursor.fetchone()
                    if not sender_inv or sender_inv["quantity"] < self.quantity:
                        await conn.execute(
                            "UPDATE trades SET status = 'cancelled' WHERE id = ?",
                            (self.trade_id,),
                        )
                        await interaction.followup.send(
                            embed=emb.error("The seller no longer has enough of that item."),
                            ephemeral=True,
                        )
                        return

                    # ── Execute the trade atomically ───────────────────────
                    new_sender_qty = sender_inv["quantity"] - self.quantity

                    # Remove or reduce sender's item
                    if new_sender_qty <= 0:
                        await conn.execute(
                            "DELETE FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                            (self.sender.id, interaction.guild.id, trade_row["item_id"]),
                        )
                    else:
                        await conn.execute(
                            "UPDATE user_items SET quantity = ? "
                            "WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                            (new_sender_qty, self.sender.id, interaction.guild.id, trade_row["item_id"]),
                        )

                    # Add item to receiver
                    await conn.execute(
                        "INSERT INTO user_items (user_id, guild_id, item_id, quantity) VALUES (?,?,?,?) "
                        "ON CONFLICT(user_id, guild_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity",
                        (self.receiver.id, interaction.guild.id, trade_row["item_id"], self.quantity),
                    )

                    # Transfer coins: receiver → sender
                    await conn.execute(
                        "UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
                        (self.price, self.receiver.id, interaction.guild.id),
                    )
                    await conn.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
                        (self.price, self.sender.id, interaction.guild.id),
                    )

                    # Mark trade complete
                    await conn.execute(
                        "UPDATE trades SET status = 'completed', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (self.trade_id,),
                    )
                    # Transaction commits here automatically

            except Exception as e:
                log.error("Trade %s failed: %s", self.trade_id, e, exc_info=True)
                await interaction.followup.send(
                    embed=emb.error("Trade failed due to an internal error. Please try again."),
                    ephemeral=True,
                )
                return
            finally:
                _trade_locks.pop(self.trade_id, None)

            # Disable buttons
            for child in self.children:
                child.disabled = True

            embed = emb.build(
                title="✅ Trade Completed",
                color=discord.Color.green(),
                fields=[
                    ("Item",   f"{self.item_name} ×{self.quantity}",          True),
                    ("Price",  f"{self.currency_symbol} {self.price:,}",       True),
                    ("Seller", self.sender.mention,                            True),
                    ("Buyer",  self.receiver.mention,                          True),
                ],
            )
            try:
                await interaction.followup.edit_message(
                    interaction.message.id, embed=embed, view=self
                )
            except discord.HTTPException:
                await interaction.followup.send(embed=embed)

            log.info(
                "Trade %s completed: %s→%s, item=%s qty=%d price=%d",
                self.trade_id, self.sender.id, self.receiver.id,
                self.item_name, self.quantity, self.price,
            )

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id not in (self.receiver.id, self.sender.id):
            return await interaction.response.send_message(
                "❌ Not your trade.", ephemeral=True
            )
        await db.execute(
            "UPDATE trades SET status = 'declined', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (self.trade_id,),
        )
        _trade_locks.pop(self.trade_id, None)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=emb.error("Trade declined."), view=self)

    async def on_timeout(self) -> None:
        await db.execute(
            "UPDATE trades SET status = 'expired' WHERE id = ? AND status = 'pending'",
            (self.trade_id,),
        )
        _trade_locks.pop(self.trade_id, None)
        for child in self.children:
            child.disabled = True
