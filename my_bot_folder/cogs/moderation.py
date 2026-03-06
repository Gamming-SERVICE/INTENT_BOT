import discord
from discord.ext import commands
from utils import create_embed, parse_time, update_user_data
import aiosqlite

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason"):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ You cannot kick this user.")
        await member.kick(reason=reason)
        await ctx.send(embed=create_embed("👢 Kicked", f"{member.mention} was kicked.\nReason: {reason}", discord.Color.orange()))

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason):
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
                            (member.id, ctx.guild.id, ctx.author.id, reason))
            await db.commit()
        await ctx.send(f"⚠️ Warned {member.mention} for: {reason}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
