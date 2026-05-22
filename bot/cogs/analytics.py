# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Analytics & Diagnostics Cog
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import platform
import sys

import discord
from discord import app_commands
from discord.ext import commands

from core.database import db
from core.permissions import require_admin, require_mod
from core.constants import BOT_VERSION, BOT_NAME
import core.embeds as emb
from core.logger import get_logger

log = get_logger("analytics")


class Analytics(commands.Cog, name="Analytics"):
    """Server analytics, bot diagnostics, and health monitoring."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Health check ───────────────────────────────────────────────────────────

    @commands.hybrid_command(name="health", description="Show full bot health diagnostics")
    @require_admin()
    @commands.guild_only()
    async def health(self, ctx: commands.Context) -> None:
        """Comprehensive bot health report for administrators."""
        latency = round(self.bot.latency * 1000)

        # Database health check
        try:
            await db.fetchone("SELECT 1")
            db_status = "✅ Connected"
            row_count = await db.fetchone("SELECT COUNT(*) AS c FROM users")
            db_info   = f"Users: {row_count['c']:,}" if row_count else ""
        except Exception as e:
            db_status = f"❌ Error: {e}"
            db_info   = ""

        # Guild stats
        guilds      = len(self.bot.guilds)
        total_users = sum(g.member_count for g in self.bot.guilds)

        # Uptime
        uptime = "N/A"
        if hasattr(self.bot, "_start_time"):
            delta   = datetime.datetime.utcnow() - self.bot._start_time
            h, rem  = divmod(int(delta.total_seconds()), 3600)
            m, s    = divmod(rem, 60)
            uptime  = f"{h}h {m}m {s}s"

        # Cog health
        loaded_cogs  = list(self.bot.cogs.keys())
        cog_status   = f"✅ {len(loaded_cogs)} loaded"

        # Memory usage (approximate)
        try:
            import resource
            mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            mem_str = f"{mem_mb:.1f} MB"
        except Exception:
            try:
                import psutil, os
                proc   = psutil.Process(os.getpid())
                mem_mb = proc.memory_info().rss / 1024 / 1024
                mem_str = f"{mem_mb:.1f} MB"
            except Exception:
                mem_str = "N/A"

        color = (
            discord.Color.green()  if latency < 100 else
            discord.Color.yellow() if latency < 200 else
            discord.Color.red()
        )

        embed = emb.build(
            title=f"🏥 {BOT_NAME} Health Report",
            color=color,
            fields=[
                ("Latency",     f"{latency}ms",          True),
                ("Uptime",      uptime,                   True),
                ("Status",      "🟢 Online",              True),
                ("Database",    db_status,                True),
                ("DB Info",     db_info or "N/A",         True),
                ("Memory",      mem_str,                  True),
                ("Guilds",      str(guilds),              True),
                ("Total Users", f"{total_users:,}",       True),
                ("Cogs",        cog_status,               True),
                ("Python",      sys.version.split()[0],   True),
                ("discord.py",  discord.__version__,      True),
                ("Bot Version", f"v{BOT_VERSION}",        True),
                ("Platform",    platform.system(),        True),
                ("Loaded Cogs", ", ".join(loaded_cogs),  False),
            ],
        )
        await ctx.send(embed=embed, ephemeral=True)

    # ── Server statistics ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="stats", description="Show server activity statistics")
    @require_mod()
    @commands.guild_only()
    async def stats(self, ctx: commands.Context) -> None:
        guild_id = ctx.guild.id

        # User counts
        total = await db.fetchone(
            "SELECT COUNT(*) AS c FROM users WHERE guild_id = ?", (guild_id,)
        )
        top_xp = await db.fetchone(
            "SELECT user_id, xp FROM users WHERE guild_id = ? ORDER BY xp DESC LIMIT 1",
            (guild_id,),
        )
        top_bal = await db.fetchone(
            "SELECT user_id, balance+bank AS total FROM users WHERE guild_id = ? ORDER BY total DESC LIMIT 1",
            (guild_id,),
        )

        # Ticket stats
        tickets_open = await db.fetchone(
            "SELECT COUNT(*) AS c FROM tickets WHERE guild_id = ? AND status='open'",
            (guild_id,),
        )
        tickets_total = await db.fetchone(
            "SELECT COUNT(*) AS c FROM tickets WHERE guild_id = ?",
            (guild_id,),
        )

        # Economy totals
        econ = await db.fetchone(
            "SELECT SUM(balance+bank) AS total FROM users WHERE guild_id = ?",
            (guild_id,),
        )

        # Giveaways
        giveaways_active = await db.fetchone(
            "SELECT COUNT(*) AS c FROM giveaways WHERE guild_id = ? AND ended=0",
            (guild_id,),
        )

        # Mod actions this month
        month_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).isoformat()
        mod_actions = await db.fetchone(
            "SELECT COUNT(*) AS c FROM mod_logs WHERE guild_id = ? AND created_at >= ?",
            (guild_id, month_ago),
        )

        top_xp_member  = ctx.guild.get_member(top_xp["user_id"]) if top_xp and top_xp["user_id"] else None
        top_bal_member = ctx.guild.get_member(top_bal["user_id"]) if top_bal and top_bal["user_id"] else None

        embed = emb.build(
            title=f"📊 {ctx.guild.name} — Statistics",
            color=discord.Color.blurple(),
            thumbnail=ctx.guild.icon.url if ctx.guild.icon else None,
            fields=[
                ("Registered Users", f"{(total['c'] if total else 0):,}",                             True),
                ("Total Wealth",     f"🪙 {(econ['total'] if econ and econ['total'] else 0):,}",       True),
                ("Top XP User",      top_xp_member.mention if top_xp_member else "N/A",               True),
                ("Top Rich User",    top_bal_member.mention if top_bal_member else "N/A",              True),
                ("Open Tickets",     str(tickets_open["c"] if tickets_open else 0),                    True),
                ("Total Tickets",    str(tickets_total["c"] if tickets_total else 0),                  True),
                ("Active Giveaways", str(giveaways_active["c"] if giveaways_active else 0),            True),
                ("Mod Actions (30d)", str(mod_actions["c"] if mod_actions else 0),                     True),
                ("Members",          f"{ctx.guild.member_count:,}",                                    True),
            ],
        )
        await ctx.send(embed=embed)

    # ── Economy audit ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name="econaudit", description="[Admin] View recent economy transactions")
    @app_commands.describe(member="Member to audit (shows all if not specified)")
    @require_admin()
    @commands.guild_only()
    async def econaudit(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        if member:
            rows = await db.fetchall(
                "SELECT type, amount, balance_after, created_at FROM economy_transactions "
                "WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 15",
                (ctx.guild.id, member.id),
            )
            title = f"📒 Economy Audit — {member}"
        else:
            rows = await db.fetchall(
                "SELECT user_id, type, amount, balance_after, created_at FROM economy_transactions "
                "WHERE guild_id = ? ORDER BY created_at DESC LIMIT 15",
                (ctx.guild.id,),
            )
            title = "📒 Economy Audit — Recent Transactions"

        if not rows:
            return await ctx.send(embed=emb.info("No transactions recorded yet."))

        lines = []
        for r in rows:
            dt = datetime.datetime.fromisoformat(r["created_at"])
            ts = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
            amt_str = f"+{r['amount']:,}" if r["amount"] > 0 else f"{r['amount']:,}"
            user_str = f"<@{r['user_id']}> " if "user_id" in r else ""
            lines.append(f"<t:{ts}:R> {user_str}`{r['type']}` **{amt_str}** → bal: {r['balance_after']:,}")

        await ctx.send(
            embed=emb.build(title=title, description="\n".join(lines), color=discord.Color.blurple()),
            ephemeral=True,
        )

    # ── Backup management ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="backups", description="[Admin] List available database backups")
    @require_admin()
    @commands.guild_only()
    async def backups(self, ctx: commands.Context) -> None:
        import os
        backup_dir = "data/backups"
        try:
            files = sorted(
                [f for f in os.listdir(backup_dir) if f.endswith(".zip")],
                reverse=True,
            )
        except FileNotFoundError:
            return await ctx.send(embed=emb.error("No backup directory found."))

        if not files:
            return await ctx.send(embed=emb.info("No backups available yet."))

        lines = []
        for f in files[:10]:
            size = os.path.getsize(os.path.join(backup_dir, f)) / 1024
            lines.append(f"📦 `{f}` — {size:.1f} KB")

        embed = emb.build(
            title=f"💾 Database Backups ({len(files)} total)",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            fields=[("Location", f"`{backup_dir}/`", False)],
        )
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="createbackup", description="[Admin] Create a manual database backup now")
    @require_admin()
    @commands.guild_only()
    async def createbackup(self, ctx: commands.Context) -> None:
        import zipfile, time
        from pathlib import Path

        await ctx.defer(ephemeral=True)
        backup_dir = Path("data/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp       = time.strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"manual_backup_{stamp}.zip"

        try:
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                db_path = Path("data/database.db")
                if db_path.exists():
                    zf.write(db_path, "database.db")
            size = backup_path.stat().st_size / 1024
            await ctx.send(
                embed=emb.success(f"Backup created: `{backup_path.name}` ({size:.1f} KB)"),
                ephemeral=True,
            )
        except Exception as e:
            await ctx.send(embed=emb.error(f"Backup failed: {e}"), ephemeral=True)

    # ── Command usage analytics ────────────────────────────────────────────────

    @commands.hybrid_command(name="cmdstats", description="Most-used custom commands in this server")
    @commands.guild_only()
    async def cmdstats(self, ctx: commands.Context) -> None:
        rows = await db.fetchall(
            "SELECT name, uses FROM custom_commands WHERE guild_id = ? ORDER BY uses DESC LIMIT 10",
            (ctx.guild.id,),
        )
        if not rows:
            return await ctx.send(embed=emb.info("No custom commands configured."))

        from core.settings import GuildSettings
        gs = await GuildSettings.get(ctx.guild.id)
        lines = [
            f"**{i}.** `{gs.prefix}{r['name']}` — {r['uses']:,} uses"
            for i, r in enumerate(rows, 1)
        ]
        await ctx.send(
            embed=emb.build(
                title="📊 Command Usage Stats",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            )
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Analytics(bot))
    log.info("Analytics cog loaded")
