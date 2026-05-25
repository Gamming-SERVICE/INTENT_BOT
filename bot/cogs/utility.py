# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Utility Cog
#                   PREFIX-ONLY | No slash commands
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import re

import discord
from discord.ext import commands

from core.database import db
from core.settings import GuildSettings
from core.cache import afk_users
from core.constants import BOT_VERSION, BOT_NAME
import core.embeds as emb
from core.logger import get_logger
from core.scheduler import scheduler

log = get_logger("utility")


def _parse_time(s: str) -> int | None:
    matches = re.findall(r"(\d+)([smhdw])", s.lower())
    if not matches:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return sum(int(v) * units[u] for v, u in matches)


_bot: commands.Bot | None = None


@scheduler.every(30)
async def check_reminders() -> None:
    if _bot is None:
        return
    now = datetime.datetime.utcnow().isoformat()
    rows = await db.fetchall(
        "SELECT * FROM reminders WHERE remind_at <= ?", (now,)
    )
    for row in rows:
        try:
            channel = _bot.get_channel(row["channel_id"])
            if channel:
                try:
                    user = await _bot.fetch_user(row["user_id"])
                    mention = user.mention
                except Exception:
                    mention = f"<@{row['user_id']}>"
                await channel.send(embed=emb.build(
                    title="⏰ Reminder",
                    description=f"{mention}\n\n{row['reminder']}",
                    color=discord.Color.blurple(),
                ))
        except discord.HTTPException as e:
            log.warning("Failed to send reminder %s: %s", row["id"], e)
        except Exception as e:
            log.exception("Error delivering reminder %s: %s", row["id"], e)
        finally:
            await db.execute("DELETE FROM reminders WHERE id = ?", (row["id"],))


class Utility(commands.Cog, name="Utility"):
    """General-purpose utility commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        global _bot
        _bot = bot

    def cog_unload(self) -> None:
        global _bot
        _bot = None

    # ── Help ───────────────────────────────────────────────────────────────────

    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context, *, command_name: str = None) -> None:
        """Show help. Usage: !help [command]"""
        gs = await GuildSettings.fetch(ctx.guild.id) if ctx.guild else None
        prefix = gs.prefix if gs else "!"

        if command_name:
            cmd = self.bot.get_command(command_name)
            if not cmd:
                return await ctx.send(embed=emb.error(f"Command `{command_name}` not found."))
            embed = emb.build(
                title=f"📖 Help — `{prefix}{cmd.name}`",
                description=cmd.help or "No description available.",
                color=discord.Color.blurple(),
            )
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(f"`{a}`" for a in cmd.aliases), inline=False)
            await ctx.send(embed=embed)
            return

        categories = {
            "⚙️ Admin":        ["setwelcome","setleave","setlog","setmuterole","setautorole","setprefix","toggle","settings","addcmd","delcmd","listcmds","reactionrole"],
            "🛡️ Moderation":   ["ban","unban","kick","timeout","mute","unmute","warn","warnings","clearwarns","purge","slowmode","lock","unlock","nick","role","modlogs"],
            "💰 Economy":       ["balance","daily","work","pay","rob","deposit","withdraw","richlist","addmoney","removemoney"],
            "🛒 Marketplace":   ["shop","buy","sell","inventory","trade","iteminfo"],
            "⭐ Leveling":      ["rank","leveltop","setxp","resetxp"],
            "🎫 Tickets":       ["ticketpanel","tickets","closeticket"],
            "🎉 Giveaways":     ["gstart","gend","greroll","glist"],
            "🤖 AI":            ["ai","aisetkey","aikeys","aiproviders"],
            "🎵 Music":         ["play","skip","stop","pause","resume","volume","queue","nowplaying","loop","shuffle","leave"],
            "🎮 Fun":           ["8ball","coinflip","roll","rps","fact","joke","cat","dog","meme","waifu","hug","pat","choose"],
            "🔧 Utility":       ["ping","botinfo","userinfo","serverinfo","avatar","afk","remind","poll","embed","invite","uptime"],
            "📊 Analytics":     ["health","stats","backups","createbackup","cmdstats"],
        }

        embed = discord.Embed(
            title=f"📖 {BOT_NAME} v{BOT_VERSION} — Help",
            description=f"Prefix: `{prefix}` | Use `{prefix}help <command>` for details",
            color=discord.Color.blurple(),
        )
        for category, cmds in categories.items():
            embed.add_field(
                name=category,
                value=" ".join(f"`{c}`" for c in cmds),
                inline=False,
            )
        embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}")
        await ctx.send(embed=embed)

    # ── Ping ───────────────────────────────────────────────────────────────────

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        """Check bot latency. Usage: !ping"""
        latency = round(self.bot.latency * 1000)
        color   = (
            discord.Color.green()  if latency < 100 else
            discord.Color.yellow() if latency < 200 else
            discord.Color.red()
        )
        await ctx.send(embed=emb.build(
            title="🏓 Pong!",
            description=f"Websocket latency: **{latency}ms**",
            color=color,
            timestamp=False,
        ))

    # ── Bot info ───────────────────────────────────────────────────────────────

    @commands.command(name="botinfo")
    async def botinfo(self, ctx: commands.Context) -> None:
        """Show bot information. Usage: !botinfo"""
        guilds  = len(self.bot.guilds)
        latency = round(self.bot.latency * 1000)
        await ctx.send(embed=emb.build(
            title=f"🤖 {BOT_NAME} v{BOT_VERSION}",
            color=discord.Color.blurple(),
            thumbnail=self.bot.user.display_avatar.url,
            fields=[
                ("Servers",  str(guilds),               True),
                ("Latency",  f"{latency}ms",             True),
                ("Version",  f"v{BOT_VERSION}",          True),
                ("Library",  f"discord.py {discord.__version__}", True),
                ("Features", "Mod • Economy • Market • AI\nTickets • Giveaways • Leveling\nAutoMod • Music • Fun", False),
            ],
        ))

    # ── User info ──────────────────────────────────────────────────────────────

    @commands.command(name="userinfo", aliases=["whois", "ui"])
    @commands.guild_only()
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None) -> None:
        """Show info about a member. Usage: !userinfo [@user]"""
        target = member or ctx.author
        roles  = [r.mention for r in reversed(target.roles) if r != ctx.guild.default_role]
        role_str = (
            (", ".join(roles[:10]) + (f" +{len(roles) - 10} more" if len(roles) > 10 else ""))
            if roles else "None"
        )
        joined_ts  = int(target.joined_at.timestamp()) if target.joined_at else 0
        created_ts = int(target.created_at.timestamp())
        await ctx.send(embed=emb.build(
            title=f"👤 {target}",
            color=target.color,
            thumbnail=target.display_avatar.url,
            fields=[
                ("Display Name",   target.display_name,                            True),
                ("ID",             str(target.id),                                 True),
                ("Bot",            "✅ Yes" if target.bot else "❌ No",              True),
                ("Joined Server",  f"<t:{joined_ts}:R>" if joined_ts else "N/A",   True),
                ("Joined Discord", f"<t:{created_ts}:R>",                           True),
                ("Top Role",       target.top_role.mention,                         True),
                ("Roles",          role_str,                                        False),
            ],
        ))

    # ── Server info ────────────────────────────────────────────────────────────

    @commands.command(name="serverinfo", aliases=["si", "guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context) -> None:
        """Show server information. Usage: !serverinfo"""
        g          = ctx.guild
        bots       = sum(1 for m in g.members if m.bot) if g.chunked else "?"
        created_ts = int(g.created_at.timestamp())
        await ctx.send(embed=emb.build(
            title=f"🏰 {g.name}",
            color=discord.Color.blurple(),
            thumbnail=g.icon.url if g.icon else None,
            fields=[
                ("Owner",       g.owner.mention if g.owner else "Unknown",              True),
                ("ID",          str(g.id),                                               True),
                ("Created",     f"<t:{created_ts}:R>",                                  True),
                ("Members",     f"{g.member_count:,}",                                  True),
                ("Channels",    f"💬 {len(g.text_channels)} | 🔊 {len(g.voice_channels)}", True),
                ("Roles",       str(len(g.roles)),                                       True),
                ("Boost Level", str(g.premium_tier),                                    True),
                ("Boosts",      str(g.premium_subscription_count),                      True),
                ("Emojis",      f"{len(g.emojis)}/{g.emoji_limit}",                     True),
                ("Verification",str(g.verification_level).title(),                      True),
            ],
        ))

    # ── Avatar ─────────────────────────────────────────────────────────────────

    @commands.command(name="avatar", aliases=["av", "pfp"])
    @commands.guild_only()
    async def avatar(self, ctx: commands.Context, member: discord.Member = None) -> None:
        """Get a member's avatar. Usage: !avatar [@user]"""
        target = member or ctx.author
        av     = target.display_avatar
        await ctx.send(embed=emb.build(
            title=f"🖼️ {target.display_name}'s Avatar",
            color=target.color,
            image=av.url,
            fields=[
                ("PNG",  f"[Link]({av.with_format('png').url})",  True),
                ("WEBP", f"[Link]({av.with_format('webp').url})", True),
            ],
        ))

    # ── AFK ────────────────────────────────────────────────────────────────────

    @commands.command(name="afk")
    @commands.guild_only()
    async def afk(self, ctx: commands.Context, *, reason: str = "AFK") -> None:
        """Set your AFK status. Usage: !afk [reason]"""
        if len(reason) > 200:
            return await ctx.send(embed=emb.error("AFK reason must be under 200 characters."))
        afk_users[ctx.author.id] = {
            "reason": reason,
            "since":  datetime.datetime.utcnow().timestamp(),
            "guild":  ctx.guild.id,
        }
        await ctx.send(
            embed=emb.info(f"💤 {ctx.author.mention} is now AFK: **{reason}**"),
            delete_after=8,
        )

    # ── Remind ─────────────────────────────────────────────────────────────────

    @commands.command(name="remind", aliases=["reminder"])
    @commands.guild_only()
    async def remind(self, ctx: commands.Context, duration: str, *, reminder: str) -> None:
        """Set a reminder. Usage: !remind <duration> <message>
        Examples: !remind 30m check oven | !remind 2h meeting"""
        if len(reminder) > 500:
            return await ctx.send(embed=emb.error("Reminder text must be under 500 characters."))
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
        fire_ts = int(datetime.datetime.utcnow().timestamp()) + seconds
        await ctx.send(embed=emb.success(
            f"⏰ Reminder set!\n**{reminder}**\nFiring <t:{fire_ts}:R>"
        ))

    # ── Poll ───────────────────────────────────────────────────────────────────

    @commands.command(name="poll")
    @commands.guild_only()
    async def poll(self, ctx: commands.Context, *, question: str) -> None:
        """Create a yes/no poll. Usage: !poll <question>"""
        if len(question) > 300:
            return await ctx.send(embed=emb.error("Question must be under 300 characters."))
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

    # ── Embed builder ──────────────────────────────────────────────────────────

    @commands.command(name="embed")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embed_cmd(self, ctx: commands.Context, channel: discord.TextChannel, title: str, *, description: str) -> None:
        """Send a custom embed. Usage: !embed #channel "Title" Description text here"""
        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
        embed.set_footer(text=f"Posted by {ctx.author}")
        await channel.send(embed=embed)
        await ctx.send(embed=emb.success(f"Embed sent to {channel.mention}."), delete_after=5)

    # ── Invite ─────────────────────────────────────────────────────────────────

    @commands.command(name="invite")
    async def invite(self, ctx: commands.Context) -> None:
        """Get the bot's invite link. Usage: !invite"""
        perms = discord.Permissions(
            manage_messages=True, manage_roles=True, manage_channels=True,
            kick_members=True, ban_members=True, moderate_members=True,
            send_messages=True, embed_links=True, attach_files=True,
            read_message_history=True, add_reactions=True,
            manage_nicknames=True,
        )
        url = discord.utils.oauth_url(self.bot.user.id, permissions=perms)
        await ctx.send(embed=emb.build(
            title="📨 Invite Intent BOT",
            description=f"[Click here to add me to your server!]({url})",
            color=discord.Color.blurple(),
            timestamp=False,
        ))

    # ── Uptime ─────────────────────────────────────────────────────────────────

    @commands.command(name="uptime")
    async def uptime(self, ctx: commands.Context) -> None:
        """Show how long the bot has been running. Usage: !uptime"""
        if not hasattr(self.bot, "_start_time"):
            return await ctx.send(embed=emb.error("Start time not recorded."))
        delta   = datetime.datetime.utcnow() - self.bot._start_time
        h, rem  = divmod(int(delta.total_seconds()), 3600)
        m, s    = divmod(rem, 60)
        await ctx.send(embed=emb.build(
            title="⏱️ Uptime",
            description=f"**{h}h {m}m {s}s**",
            color=discord.Color.green(),
            timestamp=False,
        ))

    # ── AFK handler (called from on_message in main.py) ────────────────────────

    async def handle_afk(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        if message.author.id in afk_users:
            afk_data = afk_users.pop(message.author.id)
            since_ts = int(afk_data.get("since", 0))
            try:
                await message.channel.send(
                    embed=emb.success(
                        f"Welcome back {message.author.mention}! "
                        f"AFK removed (away since <t:{since_ts}:R>)"
                    ),
                    delete_after=8,
                )
            except discord.HTTPException:
                pass
        for user in message.mentions:
            if user.bot:
                continue
            if user.id in afk_users:
                data    = afk_users[user.id]
                since_t = int(data.get("since", 0))
                try:
                    await message.channel.send(
                        embed=emb.info(
                            f"💤 **{user.display_name}** is AFK: {data['reason']}\n"
                            f"Away since <t:{since_t}:R>"
                        ),
                        delete_after=10,
                    )
                except discord.HTTPException:
                    pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
    log.info("Utility cog loaded")
