import random

from discord.ext import commands


class Giveaway(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def groll(self, ctx: commands.Context, *members: str) -> None:
        if not members:
            await ctx.send("Provide participants for giveaway roll.")
            return
        winner = random.choice(members)
        await ctx.send(f"🎉 Giveaway winner: **{winner}**")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaway(bot))
