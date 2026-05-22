# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Giveaway Cog (Fixed)
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import json
import random
import re

import discord
from discord import app_commands
from discord.ext import commands

from core.database import db
from core.permissions import require_mod
import core.embeds as emb
from core.logger import get_logger
from core.scheduler import scheduler

log = get_logger("giveaway")


def _parse_time(s: str) -> int | None:
    """Parse a duration string like 10m, 2h, 1d. Returns total seconds or None."""
    pattern = re.compile(r"(\d+)([smhdw])")
    matches = pattern.findall(s.lower())
    if not matches:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return sum(int(v) * units[u] for v, u in matches)


def _parse_stored_dt(iso_str: str) -> datetime.datetime:
    """Safely parse an ISO datetime string stored in SQLite."""
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.datetime.now(datetime.timezone.utc)


# Module-level bot reference — set when cog is loaded, never None after that
_bot: commands.Bot | None = None


async def _end_giveaway(row: dict) -> None:
    """End a giveaway, pick winners, update database, edit the message."""
    if _bot is None:
        return

    # Mark as ended first to prevent double-ending from race conditions
    updated = await db.execute(
        "UPDATE giveaways SET ended = 1 WHERE id = ? AND ended = 0",
        (row["id"],),
    )

    channel = _bot.get_channel(row["channel_id"])
    participants = json.loads(row["participants"])

    if not channel:
        return

    if not participants:
        embed = emb.build(
            title="🎉 Giveaway Ended",
            description=f"**{row['prize']}**\n\nNo one entered — no winner.",
            color=discord.Color.red(),
        )
    else:
        count      = min(row["winners"], len(participants))
        winner_ids = random.sample(participants, count)
        mentions   = " ".join(f"<@{uid}>" for uid in winner_ids)
        embed = emb.build(
            title="🎉 Giveaway Ended!",
            description=f"**Prize:** {row['prize']}\n**Winner(s):** {mentions}",
            color=discord.Color.gold(),
            fields=[
                ("Host",         f"<@{row['host_id']}>",      True),
                ("Participants", str(len(participants)),        True),
                ("Winners",      str(count),                   True),
            ],
        )

    try:
        msg = await channel.fetch_message(row["message_id"])
        await msg.edit(embed=embed, view=None)
    except discord.NotFound:
        log.warning("Giveaway message %s not found", row["message_id"])
    except discord.HTTPException as e:
        log.warning("Could not edit giveaway message: %s", e)

    if participants and winner_ids:
        try:
            await channel.send(
                f"🎉 Congratulations {mentions}! You won **{row['prize']}**!"
            )
        except discord.HTTPException:
            pass


@scheduler.every(30)
async def check_giveaways() -> None:
    """Background task — end any giveaways that have reached their end_time."""
    if _bot is None:
        return
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = await db.fetchall(
        "SELECT * FROM giveaways WHERE ended = 0 AND end_time <= ?",
        (now,),
    )
    for row in rows:
        try:
            await _end_giveaway(row)
        except Exception as e:
            log.exception("Error ending giveaway %s: %s", row["id"], e)


class GiveawayEnterView(discord.ui.View):
    """Button shown on the giveaway message. Persistent via custom_id."""

    def __init__(self, giveaway_id: int) -> None:
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(
        label="🎉 Enter Giveaway",
        style=discord.ButtonStyle.success,
        custom_id="giveaway:enter",
    )
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        row = await db.fetchone(
            "SELECT participants, ended FROM giveaways WHERE id = ?",
            (self.giveaway_id,),
        )
        if not row or row["ended"]:
            return await interaction.response.send_message(
                "❌ This giveaway has already ended.", ephemeral=True
            )

        participants = json.loads(row["participants"])
        if interaction.user.id in participants:
            return await interaction.response.send_message(
                "✅ You are already entered in this giveaway!", ephemeral=True
            )

        participants.append(interaction.user.id)
        await db.execute(
            "UPDATE giveaways SET participants = ? WHERE id = ?",
            (json.dumps(participants), self.giveaway_id),
        )
        await interaction.response.send_message(
            embed=emb.success(f"You entered the giveaway! ({len(participants)} participants so far)"),
            ephemeral=True,
        )


class Giveaways(commands.Cog, name="Giveaways"):
    """Create and manage giveaways."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        global _bot
        _bot = bot

    def cog_unload(self) -> None:
        global _bot
        _bot = None

    @commands.hybrid_command(name="gstart", description="Start a giveaway")
    @app_commands.describe(
        duration="Duration (e.g. 10m, 1h, 2d)",
        winners="Number of winners (1–20)",
        channel="Channel to post in (defaults to current)",
        prize="What to give away",
    )
    @require_mod()
    @commands.guild_only()
    async def gstart(
        self,
        ctx: commands.Context,
        duration: str,
        winners: int = 1,
        channel: discord.TextChannel | None = None,
        *,
        prize: str,
    ) -> None:
        seconds = _parse_time(duration)
        if not seconds or seconds < 10:
            return await ctx.send(embed=emb.error("Invalid duration. Use format like `10m`, `1h`, `2d`."))
        if not 1 <= winners <= 20:
            return await ctx.send(embed=emb.error("Winner count must be between 1 and 20."))

        target   = channel or ctx.channel
        end_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
        end_ts   = int(end_time.timestamp())

        embed = emb.build(
            title="🎉 GIVEAWAY!",
            description=f"**{prize}**\n\nClick the button below to enter!",
            color=discord.Color.gold(),
            fields=[
                ("Winners",   str(winners),            True),
                ("Ends",      f"<t:{end_ts}:R>",       True),
                ("Hosted by", ctx.author.mention,       True),
            ],
        )

        # Insert placeholder row, update message_id after send
        cursor = await db.execute(
            "INSERT INTO giveaways (message_id, channel_id, guild_id, prize, winners, host_id, end_time) "
            "VALUES (0, ?, ?, ?, ?, ?, ?)",
            (target.id, ctx.guild.id, prize, winners, ctx.author.id, end_time.isoformat()),
        )
        giveaway_id = cursor.lastrowid

        view = GiveawayEnterView(giveaway_id)
        msg  = await target.send(embed=embed, view=view)

        await db.execute(
            "UPDATE giveaways SET message_id = ? WHERE id = ?",
            (msg.id, giveaway_id),
        )
        if ctx.channel != target:
            await ctx.send(embed=emb.success(f"Giveaway started in {target.mention}!"), ephemeral=True)

    @commands.hybrid_command(name="gend", description="End a giveaway early")
    @app_commands.describe(message_id="Message ID of the giveaway to end")
    @require_mod()
    @commands.guild_only()
    async def gend(self, ctx: commands.Context, message_id: str) -> None:
        try:
            mid = int(message_id)
        except ValueError:
            return await ctx.send(embed=emb.error("Invalid message ID."))

        row = await db.fetchone(
            "SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND ended = 0",
            (mid, ctx.guild.id),
        )
        if not row:
            return await ctx.send(embed=emb.error("Giveaway not found or already ended."))

        await _end_giveaway(row)
        await ctx.send(embed=emb.success("Giveaway ended!"))

    @commands.hybrid_command(name="greroll", description="Reroll a giveaway winner")
    @app_commands.describe(message_id="Message ID of the ended giveaway")
    @require_mod()
    @commands.guild_only()
    async def greroll(self, ctx: commands.Context, message_id: str) -> None:
        try:
            mid = int(message_id)
        except ValueError:
            return await ctx.send(embed=emb.error("Invalid message ID."))

        row = await db.fetchone(
            "SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND ended = 1",
            (mid, ctx.guild.id),
        )
        if not row:
            return await ctx.send(embed=emb.error("Ended giveaway not found."))

        participants = json.loads(row["participants"])
        if not participants:
            return await ctx.send(embed=emb.error("No participants to reroll from."))

        winner_id = random.choice(participants)
        await ctx.send(
            embed=emb.build(
                title="🎲 Reroll!",
                description=f"New winner: <@{winner_id}>\nCongratulations on winning **{row['prize']}**!",
                color=discord.Color.gold(),
            )
        )

    @commands.hybrid_command(name="glist", description="List active giveaways in this server")
    @require_mod()
    @commands.guild_only()
    async def glist(self, ctx: commands.Context) -> None:
        rows = await db.fetchall(
            "SELECT * FROM giveaways WHERE guild_id = ? AND ended = 0 ORDER BY end_time ASC",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No active giveaways."))

        lines = []
        for r in rows:
            end_dt = _parse_stored_dt(r["end_time"])
            ts     = int(end_dt.timestamp())
            parts  = json.loads(r["participants"])
            lines.append(
                f"**{r['prize']}** — {len(parts)} entries — ends <t:{ts}:R> "
                f"— [Jump](https://discord.com/channels/{ctx.guild.id}/{r['channel_id']}/{r['message_id']})"
            )

        await ctx.send(
            embed=emb.build(
                title=f"🎉 Active Giveaways ({len(rows)})",
                description="\n".join(lines),
                color=discord.Color.gold(),
            )
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaways(bot))
    log.info("Giveaways cog loaded")
ENDOFFILE
echo "Done"
