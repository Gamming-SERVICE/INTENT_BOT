# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Utility Cog
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import re

import discord
from discord import app_commands
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.cache import afk_users
from core.constants import BOT_VERSION, BOT_NAME
import core.embeds as emb
from core.logger import get_logger
from core.scheduler import scheduler

log = get_logger("utility")

_bot_ref: commands.Bot | None = None


def _parse_time(s: str) -> int | None:
    pattern = re.compile(r"(\d+)([smhdw])")
    matches = pattern.findall(s.lower())
    if not matches:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return sum(int(v) * units[u] for v, u in matches)


@scheduler.every(30)
async def check_reminders() -> None:
    global _bot_ref
    if not _bot_ref:
        return
    now = datetime.datetime.utcnow()
    rows = await db.fetchall(
        "SELECT * FROM reminders WHERE remind_at <= ?",
        (now.isoformat(),),
    )
    for row in rows:
        try:
            channel = _bot_ref.get_channel(row["channel_id"])
            if channel:
                user = await _bot_ref.fetch_user(row["user_id"])
                await channel.send(
                    embed=emb.build(
                        title="⏰ Reminder",
                        description=f"{user.mention} — {row['reminder']}",
                        color=discord.Color.blurple(),
                    )
                )
        except Exception:
            pass
        await db.execute("DELETE FROM reminders WHERE id = ?", (row["id"],))


class Utility(commands.Cog, name="Utility"):
    """General-purpose utility commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        global _bot_ref
        _bot_ref = bot

    # ── Ping ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="ping", description="Check bot latency")
    async def ping(self, ctx: commands.Context) -> None:
        latency = round(self.bot.latency * 1000)
        color   = discord.Color.green() if latency < 100 else discord.Color.yellow() if latency < 200 else discord.Color.red()
        await ctx.send(embed=emb.build(title="🏓 Pong!", description=f"Latency: **{latency}ms**", color=color, timestamp=False))

    # ── Bot info ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="botinfo", description="Show bot information")
    async def botinfo(self, ctx: commands.Context) -> None:
        total_users = sum(g.member_count for g in self.bot.guilds)
        embed = emb.build(
            title=f"🤖 {BOT_NAME} v{BOT_VERSION}",
            color=discord.Color.blurple(),
            thumbnail=self.bot.user.display_avatar.url,
            fields=[
                ("Servers",   str(len(self.bot.guilds)),          True),
                ("Users",     f"{total_users:,}",                 True),
                ("Latency",   f"{round(self.bot.latency*1000)}ms",True),
                ("Version",   BOT_VERSION,                        True),
                ("discord.py",discord.__version__,                True),
                ("Features",  "Mod • Economy • Market • AI\nTickets • Giveaways • Leveling\nAutoMod • Music & more", False),
            ],
        )
        await ctx.send(embed=embed)

    # ── User info ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="userinfo", aliases=["whois", "ui"], description="Show info about a member")
    @app_commands.describe(member="Member to look up")
    @commands.guild_only()
    async def userinfo(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        roles  = [r.mention for r in reversed(target.roles) if r != ctx.guild.default_role]
        embed  = emb.build(
            title=f"👤 {target}",
            color=target.color,
            thumbnail=target.display_avatar.url,
            fields=[
                ("Display Name",  target.display_name,                                   True),
                ("ID",            str(target.id),                                        True),
                ("Bot",           "✅ Yes" if target.bot else "❌ No",                    True),
                ("Joined Server", f"<t:{int(target.joined_at.timestamp())}:R>",          True),
                ("Joined Discord", f"<t:{int(target.created_at.timestamp())}:R>",        True),
                ("Roles",         (", ".join(roles[:10]) or "None") + (f" +{len(roles)-10} more" if len(roles)>10 else ""), False),
            ],
        )
        await ctx.send(embed=embed)

    # ── Server info ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="serverinfo", aliases=["si", "guildinfo"], description="Show server information")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        g      = ctx.guild
        bots   = sum(1 for m in g.members if m.bot)
        humans = g.member_count - bots
        embed  = emb.build(
            title=f"🏰 {g.name}",
            color=discord.Color.blurple(),
            thumbnail=g.icon.url if g.icon else None,
            fields=[
                ("Owner",       g.owner.mention if g.owner else "Unknown", True),
                ("ID",          str(g.id),                                 True),
                ("Created",     f"<t:{int(g.created_at.timestamp())}:R>",  True),
                ("Members",     f"{g.member_count} ({humans} humans, {bots} bots)", True),
                ("Channels",    f"💬 {len(g.text_channels)} | 🔊 {len(g.voice_channels)}", True),
                ("Roles",       str(len(g.roles)),                         True),
                ("Boost Level", str(g.premium_tier),                       True),
                ("Boosts",      str(g.premium_subscription_count),         True),
                ("Emojis",      f"{len(g.emojis)}/{g.emoji_limit}",        True),
            ],
        )
        await ctx.send(embed=embed)

    # ── Avatar ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="avatar", aliases=["av", "pfp"], description="Get a member's avatar")
    @app_commands.describe(member="Member")
    @commands.guild_only()
    async def avatar(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        embed  = emb.build(
            title=f"🖼️ {target.display_name}'s Avatar",
            color=target.color,
            image=target.display_avatar.url,
            fields=[
                ("PNG",  f"[Link]({target.display_avatar.with_format('png').url})",  True),
                ("WEBP", f"[Link]({target.display_avatar.with_format('webp').url})", True),
            ],
        )
        await ctx.send(embed=embed)

    # ── AFK ────────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="afk", description="Set your AFK status")
    @app_commands.describe(reason="Reason for being AFK")
    @commands.guild_only()
    async def afk(self, ctx: commands.Context, *, reason: str = "AFK") -> None:
        afk_users[ctx.author.id] = {
            "reason": reason,
            "since":  discord.utils.utcnow().timestamp(),
            "guild":  ctx.guild.id,
        }
        await ctx.send(embed=emb.info(f"{ctx.author.mention} is now AFK: **{reason}**"), delete_after=8)

    # ── Reminder ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="remind", aliases=["reminder"], description="Set a reminder")
    @app_commands.describe(duration="When to remind you (e.g. 10m, 2h, 1d)", reminder="What to remind you about")
    @commands.guild_only()
    async def remind(self, ctx: commands.Context, duration: str, *, reminder: str) -> None:
        seconds = _parse_time(duration)
        if not seconds or seconds < 10:
            return await ctx.send(embed=emb.error("Invalid duration. Use format like `10m`, `1h`, `2d`."))
        if seconds > 30 * 86400:
            return await ctx.send(embed=emb.error("Maximum reminder duration is 30 days."))
        remind_at = (datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)).isoformat()
        await db.execute(
            "INSERT INTO reminders (user_id, channel_id, guild_id, reminder, remind_at) VALUES (?,?,?,?,?)",
            (ctx.author.id, ctx.channel.id, ctx.guild.id, reminder, remind_at),
        )
        await ctx.send(
            embed=emb.success(f"⏰ I'll remind you about **{reminder}** <t:{int(discord.utils.utcnow().timestamp()) + seconds}:R>!")
        )

    # ── Poll ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="poll", description="Create a simple yes/no poll")
    @app_commands.describe(question="Poll question")
    @commands.guild_only()
    async def poll(self, ctx: commands.Context, *, question: str) -> None:
        embed = emb.build(
            title="📊 Poll",
            description=f"**{question}**",
            color=discord.Color.blurple(),
            author=ctx.author,
            fields=[("React to vote!", "✅ Yes   |   ❌ No", False)],
        )
        try:
            await ctx.message.delete()
        except Exception:
            pass
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    # ── Embed builder (admin utility) ─────────────────────────────────────────

    @commands.hybrid_command(name="embed", description="Send a custom embed to a channel")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(
        channel="Target channel",
        title="Embed title",
        description="Embed description",
        color="Hex color (e.g. ff0000)",
    )
    @commands.guild_only()
    async def embed_cmd(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        title: str,
        description: str,
        color: str = "5865f2",
    ) -> None:
        try:
            color_int = int(color.lstrip("#"), 16)
        except ValueError:
            color_int = 0x5865F2
        embed = discord.Embed(title=title, description=description, color=color_int)
        embed.set_footer(text=f"Sent by {ctx.author}")
        await channel.send(embed=embed)
        await ctx.send(embed=emb.success(f"Embed sent to {channel.mention}"), ephemeral=True)

    # ── on_message AFK handler ────────────────────────────────────────────────

    async def handle_afk(self, message: discord.Message) -> None:
        """Called from on_message in main.py."""
        if message.author.bot or not message.guild:
            return

        # User returned from AFK
        if message.author.id in afk_users:
            afk_data = afk_users.pop(message.author.id)
            since    = afk_data.get("since", 0)
            await message.channel.send(
                embed=emb.success(f"Welcome back {message.author.mention}! AFK removed (was away <t:{int(since)}:R>)"),
                delete_after=8,
            )

        # Mentioned user is AFK
        for user in message.mentions:
            if user.id in afk_users:
                data = afk_users[user.id]
                await message.channel.send(
                    embed=emb.info(f"💤 **{user.display_name}** is AFK: {data['reason']} — <t:{int(data['since'])}:R>"),
                    delete_after=10,
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
    log.info("Utility cog loaded")
