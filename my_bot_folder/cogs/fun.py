import random

from discord.ext import commands


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def eightball(self, ctx: commands.Context, *, question: str) -> None:
        responses = ["Yes", "No", "Maybe", "Definitely", "Ask again later"]
        await ctx.send(f"🎱 Q: {question}\nA: **{random.choice(responses)}**")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
