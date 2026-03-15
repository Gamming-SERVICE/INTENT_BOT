import discord
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send(f"🏓 Pong! `{round(self.bot.latency * 1000)}ms`")

    @commands.command()
    async def userinfo(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        member = member or ctx.author
        embed = discord.Embed(title=f"User Info - {member}", color=discord.Color.blurple())
        embed.add_field(name="ID", value=str(member.id), inline=False)
        embed.add_field(name="Joined", value=discord.utils.format_dt(member.joined_at, style='R'))
        embed.add_field(name="Created", value=discord.utils.format_dt(member.created_at, style='R'))
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
