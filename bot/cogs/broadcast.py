from discord.ext import commands
import config

class Broadcast(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def broadcast(self, ctx, *, message):
        if ctx.author.id != config.OWNER_ID:
            return

        for guild in self.bot.guilds:
            if guild.system_channel:
                try:
                    await guild.system_channel.send(message)
                except:
                    pass

        await ctx.send("Broadcast sent.")

async def setup(bot):
    await bot.add_cog(Broadcast(bot))
