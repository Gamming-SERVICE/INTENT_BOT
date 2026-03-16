import datetime
import random

import discord
from discord.ext import commands

from config import CONFIG
from database import get_user_data, update_user_data


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(aliases=["bal"])
    async def balance(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        member = member or ctx.author
        data = await get_user_data(member.id, ctx.guild.id)
        embed = discord.Embed(title=f"💰 {member.display_name}'s Balance", color=discord.Color.green())
        embed.add_field(name="Wallet", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['balance']:,}")
        embed.add_field(name="Bank", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['bank']:,}")
        await ctx.send(embed=embed)

    @commands.command()
    async def work(self, ctx: commands.Context) -> None:
        data = await get_user_data(ctx.author.id, ctx.guild.id)
        now = datetime.datetime.utcnow()

        if data.get("work_claimed"):
            last_claim = datetime.datetime.fromisoformat(data["work_claimed"])
            if (now - last_claim).total_seconds() < CONFIG["WORK_COOLDOWN"]:
                await ctx.send("⌛ Work cooldown active. Try again later.")
                return

        earned = random.randint(CONFIG["WORK_MIN"], CONFIG["WORK_MAX"])
        await update_user_data(
            ctx.author.id,
            ctx.guild.id,
            balance=data["balance"] + earned,
            work_claimed=now.isoformat(),
        )
        await ctx.send(f"💼 You earned {CONFIG['CURRENCY_SYMBOL']} **{earned}**")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
