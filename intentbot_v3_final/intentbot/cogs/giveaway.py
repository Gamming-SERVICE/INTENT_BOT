# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Giveaway Cog
#                   PREFIX-ONLY | No slash commands
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import json
import random
import re

import discord
from discord.ext import commands

from core.database import db
from core.permissions import require_mod
import core.embeds as emb
from core.logger import get_logger
from core.scheduler import scheduler

log = get_logger("giveaway")


def _parse_time(s: str) -> int | None:
    matches = re.findall(r"(\d+)([smhdw])", s.lower())
    if not matches:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return sum(int(v) * units[u] for v, u in matches)


def _parse_dt(iso: str) -> datetime.datetime:
    try:
        dt = datetime.datetime.fromisoformat(iso)
        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


_bot: commands.Bot | None = None


async def _end_giveaway(row: dict) -> None:
    if _bot is None:
        return
    await db.execute("UPDATE giveaways SET ended = 1 WHERE id = ? AND ended = 0", (row["id"],))
    channel      = _bot.get_channel(row["channel_id"])
    participants = json.loads(row["participants"])
    if not channel:
        return
    if not participants:
        embed = emb.build(
            title="🎉 Giveaway Ended",
            description=f"**{row['prize']}**\n\nNo participants — no winner.",
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
                ("Host",         f"<@{row['host_id']}>",   True),
                ("Participants", str(len(participants)),    True),
                ("Winners",      str(count),                True),
            ],
        )
    try:
        msg = await channel.fetch_message(row["message_id"])
        await msg.edit(content=None, embed=embed)
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
    if _bot is None:
        return
    now  = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = await db.fetchall(
        "SELECT * FROM giveaways WHERE ended = 0 AND end_time <= ?", (now,)
    )
    for row in rows:
        try:
            await _end_giveaway(row)
        except Exception as e:
            log.exception("Error ending giveaway %s: %s", row["id"], e)


class Giveaways(commands.Cog, name="Giveaways"):
    """Create and manage giveaways."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        global _bot
        _bot = bot

    def cog_unload(self) -> None:
        global _bot
        _bot = None

    @commands.command(name="gstart")
    @require_mod()
    @commands.guild_only()
    async def gstart(self, ctx: commands.Context, duration: str, winners: int, *, prize: str) -> None:
        """Start a giveaway. Usage: !gstart <duration> <winners> <prize>
        Example: !gstart 1h 1 Discord Nitro"""
        seconds = _parse_time(duration)
        if not seconds or seconds < 10:
            return await ctx.send(embed=emb.error("Invalid duration. Use `10m`, `1h`, `2d`, etc."))
        if not 1 <= winners <= 20:
            return await ctx.send(embed=emb.error("Winner count must be 1–20."))

        end_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
        end_ts   = int(end_time.timestamp())

        embed = emb.build(
            title="🎉 GIVEAWAY!",
            description=f"**{prize}**\n\nReact with 🎉 to enter!",
            color=discord.Color.gold(),
            fields=[
                ("Winners",   str(winners),             True),
                ("Ends",      f"<t:{end_ts}:R>",        True),
                ("Hosted by", ctx.author.mention,       True),
            ],
        )

        giveaway_id = await db.execute_returning_id(
            "INSERT INTO giveaways (message_id, channel_id, guild_id, prize, winners, host_id, end_time) "
            "VALUES (0, ?, ?, ?, ?, ?, ?)",
            (ctx.channel.id, ctx.guild.id, prize, winners, ctx.author.id, end_time.isoformat()),
        )

        msg = await ctx.send(embed=embed)
        await msg.add_reaction("🎉")

        await db.execute(
            "UPDATE giveaways SET message_id = ? WHERE id = ?",
            (msg.id, giveaway_id),
        )

    @commands.command(name="gend")
    @require_mod()
    @commands.guild_only()
    async def gend(self, ctx: commands.Context, message_id: str) -> None:
        """End a giveaway early. Usage: !gend <message_id>"""
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

    @commands.command(name="greroll")
    @require_mod()
    @commands.guild_only()
    async def greroll(self, ctx: commands.Context, message_id: str) -> None:
        """Reroll a giveaway winner. Usage: !greroll <message_id>"""
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
        await ctx.send(embed=emb.build(
            title="🎲 Reroll!",
            description=f"New winner: <@{winner_id}>\nCongratulations on **{row['prize']}**!",
            color=discord.Color.gold(),
        ))

    @commands.command(name="glist")
    @require_mod()
    @commands.guild_only()
    async def glist(self, ctx: commands.Context) -> None:
        """List active giveaways. Usage: !glist"""
        rows = await db.fetchall(
            "SELECT * FROM giveaways WHERE guild_id = ? AND ended = 0 ORDER BY end_time ASC",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No active giveaways."))
        lines = []
        for r in rows:
            end_dt = _parse_dt(r["end_time"])
            ts     = int(end_dt.timestamp())
            parts  = json.loads(r["participants"])
            lines.append(
                f"**{r['prize']}** — {len(parts)} entries — ends <t:{ts}:R>"
            )
        await ctx.send(embed=emb.build(
            title=f"🎉 Active Giveaways ({len(rows)})",
            description="\n".join(lines),
            color=discord.Color.gold(),
        ))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) != "🎉" or not payload.guild_id:
            return
        if payload.user_id == self.bot.user.id:
            return
        row = await db.fetchone(
            "SELECT id, participants, ended FROM giveaways WHERE message_id = ? AND ended = 0",
            (payload.message_id,),
        )
        if not row:
            return
        participants = json.loads(row["participants"])
        if payload.user_id not in participants:
            participants.append(payload.user_id)
            await db.execute(
                "UPDATE giveaways SET participants = ? WHERE id = ?",
                (json.dumps(participants), row["id"]),
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaways(bot))
    log.info("Giveaways cog loaded")
