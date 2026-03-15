import random

from discord.ext import commands


class Waifu(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def waifu(self, ctx: commands.Context) -> None:
        options = ["Rem", "Asuna", "Mikasa", "Hinata", "Zero Two"]
        await ctx.send(f"💖 Your random waifu pick: **{random.choice(options)}**")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Waifu(bot))
