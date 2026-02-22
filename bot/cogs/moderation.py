from discord.ext import commands
import database

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def setprefix(self, ctx, prefix: str):
        await database.set_prefix(ctx.guild.id, prefix)
        await ctx.reply(f"Prefix updated to `{prefix}`")

async def setup(bot):
    await bot.add_cog(Admin(bot))
