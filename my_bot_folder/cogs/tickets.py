from discord.ext import commands


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def ticket(self, ctx: commands.Context, *, issue: str) -> None:
        await ctx.send(f"🎟️ Ticket created for {ctx.author.mention}: {issue}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
