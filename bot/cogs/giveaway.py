# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Giveaway Cog
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

_bot_ref: commands.Bot | None = None


def _parse_time(s: str) -> int | None:
    pattern = re.compile(r"(\d+)([smhdw])")
    matches = pattern.findall(s.lower())
    if not matches:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return sum(int(v) * units[u] for v, u in matches)


@scheduler.every(30)
async def check_giveaways() -> None:
    global _bot_ref
    if not _bot_ref:
        return
    now = datetime.datetime.utcnow()
    rows = await db.fetchall(
        "SELECT * FROM giveaways WHERE ended = 0 AND end_time <= ?",
        (now.isoformat(),),
    )
    for row in rows:
        await _end_giveaway(row)


async def _end_giveaway(row: dict) -> None:
    global _bot_ref
    await db.execute("UPDATE giveaways SET ended = 1 WHERE id = ?", (row["id"],))
    participants = json.loads(row["participants"])
    channel = _bot_ref.get_channel(row["channel_id"])
    if not channel:
        return

    if not participants:
        try:
            msg = await channel.fetch_message(row["message_id"])
            await msg.edit(
                embed=emb.build(
                    title="🎉 Giveaway Ended",
                    description=f"**{row['prize']}**\n\nNo participants — no winner.",
                    color=discord.Color.red(),
                )
            )
        except discord.HTTPException:
            pass
        return

    count    = min(row["winners"], len(participants))
    winner_ids = random.sample(participants, count)
    mentions  = " ".join(f"<@{uid}>" for uid in winner_ids)

    embed = emb.build(
        title="🎉 Giveaway Ended!",
        description=f"**Prize:** {row['prize']}\n**Winner(s):** {mentions}",
        color=discord.Color.gold(),
        fields=[("Host", f"<@{row['host_id']}>", True), ("Participants", str(len(participants)), True)],
    )
    try:
        msg = await channel.fetch_message(row["message_id"])
        await msg.edit(embed=embed)
    except discord.HTTPException:
        pass
    await channel.send(f"🎉 Congratulations {mentions}! You won **{row['prize']}**!")


class GiveawayEnterView(discord.ui.View):
    def __init__(self, giveaway_id: int) -> None:
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="giveaway:enter")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        row = await db.fetchone(
            "SELECT participants, ended FROM giveaways WHERE id = ?",
            (self.giveaway_id,),
        )
        if not row or row["ended"]:
            return await interaction.response.send_message("❌ This giveaway has ended.", ephemeral=True)
        participants = json.loads(row["participants"])
        if interaction.user.id in participants:
            return await interaction.response.send_message("❌ You are already entered!", ephemeral=True)
        participants.append(interaction.user.id)
        await db.execute(
            "UPDATE giveaways SET participants = ? WHERE id = ?",
            (json.dumps(participants), self.giveaway_id),
        )
        await interaction.response.send_message(
            embed=emb.success(f"You entered the giveaway! ({len(participants)} participants)"),
            ephemeral=True,
        )


class Giveaways(commands.Cog, name="Giveaways"):
    """Create and manage giveaways."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        global _bot_ref
        _bot_ref = bot

    @commands.hybrid_command(name="gstart", description="Start a giveaway")
    @app_commands.describe(
        duration="Duration (e.g. 1h, 30m, 2d)",
        winners="Number of winners",
        prize="What to give away",
        channel="Channel to post in",
    )
    @require_mod()
    @commands.guild_only()
    async def gstart(
        self,
        ctx: commands.Context,
        duration: str,
        winners: int = 1,
        *,
        prize: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
        seconds = _parse_time(duration)
        if not seconds or seconds < 10:
            return await ctx.send(embed=emb.error("Invalid duration. Example: `10m`, `1h`, `2d`"))
        if winners < 1 or winners > 20:
            return await ctx.send(embed=emb.error("Winner count must be between 1 and 20."))

        target   = channel or ctx.channel
        end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)

        embed = emb.build(
            title="🎉 GIVEAWAY!",
            description=f"**{prize}**\n\nClick the button to enter!",
            color=discord.Color.gold(),
            fields=[
                ("Winners",  str(winners),                               True),
                ("Ends",     f"<t:{int(end_time.timestamp())}:R>",       True),
                ("Hosted by", ctx.author.mention,                        True),
            ],
        )

        # Insert with placeholder message_id, update after send
        cursor = await db.execute(
            """INSERT INTO giveaways (message_id, channel_id, guild_id, prize, winners, host_id, end_time)
               VALUES (0,?,?,?,?,?,?)""",
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

    @commands.hybrid_command(name="gend", description="End a giveaway early by message ID")
    @app_commands.describe(message_id="Message ID of the giveaway")
    @require_mod()
    @commands.guild_only()
    async def gend(self, ctx: commands.Context, message_id: str) -> None:
        mid = int(message_id)
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
        mid = int(message_id)
        row = await db.fetchone(
            "SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND ended = 1",
            (mid, ctx.guild.id),
        )
        if not row:
            return await ctx.send(embed=emb.error("Ended giveaway not found."))
        participants = json.loads(row["participants"])
        if not participants:
            return await ctx.send(embed=emb.error("No participants to reroll."))
        winner_id = random.choice(participants)
        await ctx.send(
            embed=emb.build(
                title="🎲 Reroll!",
                description=f"New winner: <@{winner_id}> — Congratulations for **{row['prize']}**!",
                color=discord.Color.gold(),
            )
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaways(bot))
    log.info("Giveaways cog loaded")
