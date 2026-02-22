from discord.ext import commands
from database import set_prefix

class Prefix(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setprefix(self, ctx, new_prefix):
        await set_prefix(ctx.guild.id, new_prefix)
        await ctx.send(f"Prefix changed to `{new_prefix}`")

async def setup(bot):
    await bot.add_cog(Prefix(bot))
