import aiosqlite
import discord
from discord.ext import commands

from database import DB_PATH


class InviteTracker(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _fetch_invites(self, guild: discord.Guild) -> dict[str, int]:
        try:
            invites = await guild.invites()
        except discord.Forbidden:
            return {}
        return {invite.code: invite.uses for invite in invites}

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            self.bot.invite_cache[guild.id] = await self._fetch_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        guild_cache = self.bot.invite_cache.setdefault(invite.guild.id, {})
        guild_cache[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        before = self.bot.invite_cache.get(member.guild.id, {})
        after = await self._fetch_invites(member.guild)
        self.bot.invite_cache[member.guild.id] = after

        inviter_id = None
        for code, uses in after.items():
            if uses > before.get(code, 0):
                invite = discord.utils.get(await member.guild.invites(), code=code)
                inviter_id = invite.inviter.id if invite and invite.inviter else None
                break

        if inviter_id is None:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO invite_stats (guild_id, inviter_id, total_invites)
                VALUES (?, ?, 1)
                ON CONFLICT(guild_id, inviter_id)
                DO UPDATE SET total_invites = total_invites + 1
                """,
                (member.guild.id, inviter_id),
            )
            await db.execute(
                """
                INSERT OR REPLACE INTO invite_joins (guild_id, joined_user_id, inviter_id)
                VALUES (?, ?, ?)
                """,
                (member.guild.id, member.id, inviter_id),
            )
            await db.commit()

    @commands.command(name="invites")
    async def invites(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        member = member or ctx.author
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT total_invites FROM invite_stats WHERE guild_id = ? AND inviter_id = ?",
                (ctx.guild.id, member.id),
            )
            row = await cursor.fetchone()

        total = row[0] if row else 0
        await ctx.send(f"📨 {member.mention} has **{total}** lifetime invites.")

    @commands.command(name="invitetop")
    async def invite_top(self, ctx: commands.Context) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT inviter_id, total_invites
                FROM invite_stats
                WHERE guild_id = ?
                ORDER BY total_invites DESC
                LIMIT 10
                """,
                (ctx.guild.id,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send("No invite data yet.")
            return

        lines = []
        for index, (inviter_id, total_invites) in enumerate(rows, start=1):
            member = ctx.guild.get_member(inviter_id)
            name = member.mention if member else f"User `{inviter_id}`"
            lines.append(f"{index}. {name} — **{total_invites}**")

        embed = discord.Embed(title="🏆 Invite Leaderboard", description="\n".join(lines), color=discord.Color.gold())
        await ctx.send(embed=embed)

    @commands.command(name="resetinvites")
    @commands.has_permissions(administrator=True)
    async def reset_invites(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            if member:
                await db.execute(
                    "DELETE FROM invite_stats WHERE guild_id = ? AND inviter_id = ?",
                    (ctx.guild.id, member.id),
                )
                await ctx.send(f"✅ Reset invite stats for {member.mention}.")
            else:
                await db.execute(
                    "DELETE FROM invite_stats WHERE guild_id = ?",
                    (ctx.guild.id,),
                )
                await ctx.send("✅ Reset invite stats for the entire server.")
            await db.commit()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InviteTracker(bot))
