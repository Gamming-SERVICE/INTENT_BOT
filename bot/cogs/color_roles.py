# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Color Roles Cog
#                   PREFIX-ONLY | No slash commands
#
# Allows members to self-assign cosmetic color roles via commands.
# Admins configure the available roles; members pick one at a time.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import discord
from discord.ext import commands

from core.database import db
from core.permissions import require_admin
import core.embeds as emb
from core.logger import get_logger

log = get_logger("color_roles")


async def _get_color_roles(guild_id: int) -> list[dict]:
    """Return all configured color roles for a guild."""
    return await db.fetchall(
        "SELECT role_id, label, emoji FROM color_roles WHERE guild_id = ? ORDER BY label ASC",
        (guild_id,),
    )


async def _remove_all_color_roles(member: discord.Member, guild_id: int) -> None:
    """Remove all color roles currently held by a member."""
    rows     = await _get_color_roles(guild_id)
    role_ids = {r["role_id"] for r in rows}
    to_remove = [r for r in member.roles if r.id in role_ids]
    if to_remove:
        try:
            await member.remove_roles(*to_remove, reason="Color role swap")
        except discord.HTTPException as e:
            log.warning("Failed to remove color roles from %s: %s", member, e)


class ColorRoles(commands.Cog, name="ColorRoles"):
    """
    Self-assignable cosmetic color roles.

    Admin commands: !croleadd, !croleremove, !crolelist (admin), !crolereset
    Member commands: !color, !colors, !nocolor
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Admin: configure color roles ──────────────────────────────────────────

    @commands.command(name="croleadd", aliases=["addcolorrole"])
    @require_admin()
    @commands.guild_only()
    async def croleadd(
        self,
        ctx: commands.Context,
        role: discord.Role,
        emoji: str = "🎨",
        *,
        label: str = None,
    ) -> None:
        """Add a color role to the available list. Usage: !croleadd @Role [emoji] [label]
        Example: !croleadd @Red 🔴 Red
        Example: !croleadd @Blue"""
        label = (label or role.name)[:50]

        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=emb.error(
                "I cannot manage that role — it's above my highest role.\n"
                "Move my role above the color roles."
            ))

        await db.execute(
            "INSERT OR REPLACE INTO color_roles (guild_id, role_id, label, emoji) VALUES (?,?,?,?)",
            (ctx.guild.id, role.id, label, emoji),
        )
        log.info("Color role added: %s (%s) in guild %s", role.name, emoji, ctx.guild.id)
        await ctx.send(embed=emb.success(
            f"Color role added: {emoji} **{label}** → {role.mention}"
        ))

    @commands.command(name="croleremove", aliases=["removecolorrole"])
    @require_admin()
    @commands.guild_only()
    async def croleremove(self, ctx: commands.Context, role: discord.Role) -> None:
        """Remove a color role from the list. Usage: !croleremove @Role"""
        existing = await db.fetchone(
            "SELECT label FROM color_roles WHERE guild_id = ? AND role_id = ?",
            (ctx.guild.id, role.id),
        )
        if not existing:
            return await ctx.send(embed=emb.error(f"{role.mention} is not a configured color role."))

        await db.execute(
            "DELETE FROM color_roles WHERE guild_id = ? AND role_id = ?",
            (ctx.guild.id, role.id),
        )
        await ctx.send(embed=emb.success(f"Color role **{existing['label']}** removed."))

    @commands.command(name="crolereset")
    @require_admin()
    @commands.guild_only()
    async def crolereset(self, ctx: commands.Context) -> None:
        """Remove ALL configured color roles for this server. Usage: !crolereset"""
        count = await db.fetchone(
            "SELECT COUNT(*) AS c FROM color_roles WHERE guild_id = ?",
            (ctx.guild.id,),
        )
        if not count or count["c"] == 0:
            return await ctx.send(embed=emb.info("No color roles configured."))
        await db.execute("DELETE FROM color_roles WHERE guild_id = ?", (ctx.guild.id,))
        await ctx.send(embed=emb.success(f"Removed all {count['c']} color role(s) from this server."))

    # ── Member: self-assign color roles ───────────────────────────────────────

    @commands.command(name="colors", aliases=["colorroles", "colourlist"])
    @commands.guild_only()
    async def colors(self, ctx: commands.Context) -> None:
        """Show all available color roles. Usage: !colors"""
        rows = await _get_color_roles(ctx.guild.id)
        if not rows:
            return await ctx.send(embed=emb.info(
                "No color roles have been configured.\n"
                "Admins can add them with `!croleadd @Role`."
            ))

        lines = []
        for r in rows:
            role = ctx.guild.get_role(r["role_id"])
            if role:
                # Show a dot with the role's actual color
                color_hex = str(role.color) if role.color.value else "No color"
                lines.append(f"{r['emoji']} **{r['label']}** — {role.mention} `{color_hex}`")

        gs_prefix = "!"
        try:
            from core.settings import GuildSettings
            gs = await GuildSettings.fetch(ctx.guild.id)
            gs_prefix = gs.prefix
        except Exception:
            pass

        await ctx.send(embed=emb.build(
            title=f"🎨 Available Color Roles ({len(lines)})",
            description="\n".join(lines) if lines else "All configured roles seem to be deleted.",
            color=discord.Color.blurple(),
            fields=[(
                "How to use",
                f"`{gs_prefix}color <name or emoji>` to get a color\n"
                f"`{gs_prefix}nocolor` to remove your color role",
                False,
            )],
        ))

    @commands.command(name="color", aliases=["setcolor", "colour"])
    @commands.guild_only()
    async def color(self, ctx: commands.Context, *, name: str) -> None:
        """Assign yourself a color role. Usage: !color <name or emoji>
        Examples: !color Red | !color 🔴"""
        rows = await _get_color_roles(ctx.guild.id)
        if not rows:
            return await ctx.send(embed=emb.error(
                "No color roles configured. Ask an admin to add some with `!croleadd`."
            ))

        name_lower = name.lower().strip()
        match = None
        for r in rows:
            if (
                r["label"].lower() == name_lower
                or r["emoji"].strip() == name.strip()
                or str(r["role_id"]) == name_lower
            ):
                match = r
                break

        # Partial match fallback
        if not match:
            for r in rows:
                if name_lower in r["label"].lower():
                    match = r
                    break

        if not match:
            role_list = ", ".join(f"`{r['label']}`" for r in rows[:10])
            return await ctx.send(embed=emb.error(
                f"Color role `{name}` not found.\nAvailable: {role_list}"
            ))

        target_role = ctx.guild.get_role(match["role_id"])
        if not target_role:
            return await ctx.send(embed=emb.error(
                "That color role no longer exists. An admin needs to re-add it."
            ))

        # Check if already wearing this role
        if target_role in ctx.author.roles:
            return await ctx.send(embed=emb.info(
                f"You already have the **{match['label']}** color role. "
                f"Use `!nocolor` to remove it."
            ))

        # Remove all existing color roles, then add the new one
        await _remove_all_color_roles(ctx.author, ctx.guild.id)

        try:
            await ctx.author.add_roles(target_role, reason=f"Color role selected: {match['label']}")
        except discord.Forbidden:
            return await ctx.send(embed=emb.error(
                "I don't have permission to assign that role.\n"
                "Make sure my role is above the color roles."
            ))
        except discord.HTTPException as e:
            return await ctx.send(embed=emb.error(f"Failed to assign role: {e}"))

        await ctx.send(embed=emb.success(
            f"{match['emoji']} Color role **{match['label']}** applied!"
        ))

    @commands.command(name="nocolor", aliases=["removecolor", "nocolour"])
    @commands.guild_only()
    async def nocolor(self, ctx: commands.Context) -> None:
        """Remove your current color role. Usage: !nocolor"""
        rows    = await _get_color_roles(ctx.guild.id)
        role_ids = {r["role_id"] for r in rows}
        current = [r for r in ctx.author.roles if r.id in role_ids]

        if not current:
            return await ctx.send(embed=emb.info("You don't have any color role to remove."))

        await _remove_all_color_roles(ctx.author, ctx.guild.id)
        names = ", ".join(f"**{r.name}**" for r in current)
        await ctx.send(embed=emb.success(f"Color role(s) {names} removed."))

    @commands.command(name="mycolor", aliases=["mycolour"])
    @commands.guild_only()
    async def mycolor(self, ctx: commands.Context) -> None:
        """Check your current color role. Usage: !mycolor"""
        rows     = await _get_color_roles(ctx.guild.id)
        role_ids = {r["role_id"]: r for r in rows}
        current  = [r for r in ctx.author.roles if r.id in role_ids]

        if not current:
            return await ctx.send(embed=emb.info(
                "You don't have a color role. Use `!color <name>` to pick one!"
            ))

        role_data = role_ids[current[0].id]
        await ctx.send(embed=emb.build(
            title="🎨 Your Color Role",
            description=f"{role_data['emoji']} **{role_data['label']}** — {current[0].mention}",
            color=current[0].color,
        ))

    @commands.command(name="colorstats")
    @require_admin()
    @commands.guild_only()
    async def colorstats(self, ctx: commands.Context) -> None:
        """Show color role usage statistics. Usage: !colorstats"""
        rows = await _get_color_roles(ctx.guild.id)
        if not rows:
            return await ctx.send(embed=emb.info("No color roles configured."))

        lines = []
        total_users = 0
        for r in rows:
            role = ctx.guild.get_role(r["role_id"])
            if role:
                count = len(role.members)
                total_users += count
                lines.append(f"{r['emoji']} **{r['label']}** — {count} member(s)")

        await ctx.send(embed=emb.build(
            title=f"📊 Color Role Statistics",
            description="\n".join(lines) if lines else "No data available.",
            color=discord.Color.blurple(),
            fields=[("Total Users With Color", str(total_users), True)],
        ))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ColorRoles(bot))
    log.info("ColorRoles cog loaded")
