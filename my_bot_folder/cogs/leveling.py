import discord
from discord.ext import commands

from database import get_user_data


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def rank(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        member = member or ctx.author
        data = await get_user_data(member.id, ctx.guild.id)
        await ctx.send(f"📈 {member.mention} | XP: **{data['xp']}** | Level: **{data['level']}** | Messages: **{data['messages']}**")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leveling(bot))
