# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Economy Service
#
# Centralised economy business logic used by cogs/economy.py and
# cogs/marketplace.py. Keeps all money-mutation in one place so
# it's easy to audit and extend.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

from core.database import db
from core.logger import get_logger

log = get_logger("economy_service")


async def ensure_user(user_id: int, guild_id: int) -> dict:
    """
    Return the user's economy row, creating it if it doesn't exist.
    Never returns None.
    """
    row = await db.fetchone(
        "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    if row is None:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?,?)",
            (user_id, guild_id),
        )
        row = await db.fetchone(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
    return row


async def get_balance(user_id: int, guild_id: int) -> tuple[int, int]:
    """Return (wallet_balance, bank_balance) for a user."""
    row = await ensure_user(user_id, guild_id)
    return row["balance"], row["bank"]


async def add_wallet(
    user_id: int,
    guild_id: int,
    amount: int,
    *,
    txn_type: str = "misc",
    meta: dict | None = None,
) -> int:
    """
    Add `amount` to the user's wallet (can be negative to subtract).
    Balance is clamped at 0 — will never go negative.
    Returns the new wallet balance.
    Records an audit transaction.
    """
    await db.execute(
        "UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ? AND guild_id = ?",
        (amount, user_id, guild_id),
    )
    row = await db.fetchone(
        "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    new_bal = row["balance"] if row else 0
    await db.record_transaction(guild_id, user_id, txn_type, amount, new_bal, meta)
    return new_bal


async def transfer(
    sender_id: int,
    receiver_id: int,
    guild_id: int,
    amount: int,
) -> tuple[int, int]:
    """
    Atomically transfer `amount` from sender's wallet to receiver's wallet.
    Raises ValueError if sender has insufficient funds.
    Returns (sender_new_balance, receiver_new_balance).
    """
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")

    async with db.transaction() as conn:
        row = await (
            await conn.execute(
                "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
                (sender_id, guild_id),
            )
        ).fetchone()

        if not row or row["balance"] < amount:
            available = row["balance"] if row else 0
            raise ValueError(
                f"Insufficient funds: need {amount:,}, have {available:,}"
            )

        await conn.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
            (amount, sender_id, guild_id),
        )
        await conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
            (amount, receiver_id, guild_id),
        )

    # Read back new balances
    sender_row   = await db.fetchone(
        "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
        (sender_id, guild_id),
    )
    receiver_row = await db.fetchone(
        "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
        (receiver_id, guild_id),
    )

    sender_bal   = sender_row["balance"]   if sender_row   else 0
    receiver_bal = receiver_row["balance"] if receiver_row else 0

    await db.record_transaction(guild_id, sender_id,   "transfer_out", -amount, sender_bal)
    await db.record_transaction(guild_id, receiver_id, "transfer_in",   amount, receiver_bal)

    log.info(
        "Transfer: %d→%d in guild %d, amount=%d",
        sender_id, receiver_id, guild_id, amount,
    )
    return sender_bal, receiver_bal


async def deposit(user_id: int, guild_id: int, amount: int) -> tuple[int, int]:
    """
    Move `amount` from wallet to bank.
    Raises ValueError if wallet has insufficient funds.
    Returns (new_wallet, new_bank).
    """
    row = await ensure_user(user_id, guild_id)
    if amount <= 0 or amount > row["balance"]:
        raise ValueError(f"Cannot deposit {amount:,} — wallet has {row['balance']:,}")

    await db.execute(
        "UPDATE users SET balance = balance - ?, bank = bank + ? WHERE user_id = ? AND guild_id = ?",
        (amount, amount, user_id, guild_id),
    )
    row = await db.fetchone(
        "SELECT balance, bank FROM users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    return row["balance"], row["bank"]


async def withdraw(user_id: int, guild_id: int, amount: int) -> tuple[int, int]:
    """
    Move `amount` from bank to wallet.
    Raises ValueError if bank has insufficient funds.
    Returns (new_wallet, new_bank).
    """
    row = await ensure_user(user_id, guild_id)
    if amount <= 0 or amount > row["bank"]:
        raise ValueError(f"Cannot withdraw {amount:,} — bank has {row['bank']:,}")

    await db.execute(
        "UPDATE users SET balance = balance + ?, bank = bank - ? WHERE user_id = ? AND guild_id = ?",
        (amount, amount, user_id, guild_id),
    )
    row = await db.fetchone(
        "SELECT balance, bank FROM users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    return row["balance"], row["bank"]


async def get_leaderboard(guild_id: int, limit: int = 10) -> list[dict]:
    """Return top members by total wealth (wallet + bank)."""
    return await db.fetchall(
        "SELECT user_id, balance, bank, balance + bank AS total "
        "FROM users WHERE guild_id = ? ORDER BY total DESC LIMIT ?",
        (guild_id, limit),
    )


async def reset_user(user_id: int, guild_id: int) -> None:
    """Reset a user's economy data to zero."""
    await db.execute(
        "UPDATE users SET balance = 0, bank = 0, daily_at = NULL, work_at = NULL "
        "WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    log.info("Economy reset for user %d in guild %d", user_id, guild_id)


async def add_item(user_id: int, guild_id: int, item_id: int, quantity: int = 1) -> None:
    """Add items to a user's inventory (upsert)."""
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    await db.execute(
        "INSERT INTO user_items (user_id, guild_id, item_id, quantity) VALUES (?,?,?,?) "
        "ON CONFLICT(user_id, guild_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity",
        (user_id, guild_id, item_id, quantity),
    )


async def remove_item(user_id: int, guild_id: int, item_id: int, quantity: int = 1) -> bool:
    """
    Remove items from a user's inventory.
    Returns True on success, False if they don't have enough.
    """
    row = await db.fetchone(
        "SELECT quantity FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
        (user_id, guild_id, item_id),
    )
    if not row or row["quantity"] < quantity:
        return False

    new_qty = row["quantity"] - quantity
    if new_qty <= 0:
        await db.execute(
            "DELETE FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (user_id, guild_id, item_id),
        )
    else:
        await db.execute(
            "UPDATE user_items SET quantity = ? WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (new_qty, user_id, guild_id, item_id),
        )
    return True


async def get_inventory(user_id: int, guild_id: int) -> list[dict]:
    """Return a user's full inventory with item details."""
    return await db.fetchall(
        "SELECT mi.item_id, mi.name, mi.emoji, mi.rarity, mi.category, "
        "mi.base_price, mi.current_price, ui.quantity "
        "FROM user_items ui "
        "JOIN market_items mi ON ui.item_id = mi.item_id "
        "WHERE ui.user_id = ? AND ui.guild_id = ? "
        "ORDER BY mi.rarity DESC, mi.name ASC",
        (user_id, guild_id),
    )
