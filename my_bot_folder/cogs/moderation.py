import aiosqlite
import discord
from discord.ext import commands

from database import DB_PATH
from utils import create_embed


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot kick a member with equal/higher role.")
            return
        await member.kick(reason=reason)
        await ctx.send(embed=create_embed("👢 User kicked", f"{member.mention}\nReason: {reason}", discord.Color.orange()))

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
                (member.id, ctx.guild.id, ctx.author.id, reason),
            )
            await db.commit()
        await ctx.send(f"⚠️ Warned {member.mention}: {reason}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
