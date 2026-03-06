import discord
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Example: Kick Command
    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason"):
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("❌ Top role error.")
        await member.kick(reason=reason)
        await ctx.send(f"✅ Kicked {member.mention}")

    # Example: Warn Command (Uses the bot's cache)
    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason):
        # You can access database helpers by importing them at the top
        from database import update_user_data
        # Logic here...
        await ctx.send(f"⚠️ Warned {member.name}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
