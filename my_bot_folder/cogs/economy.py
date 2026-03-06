import discord
import datetime
import random
from discord.ext import commands
from utils import CONFIG, get_user_data, update_user_data

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["bal"])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = await get_user_data(member.id, ctx.guild.id)
        embed = discord.Embed(title=f"💰 {member.name}'s Balance", color=discord.Color.green())
        embed.add_field(name="Wallet", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['balance']:,}")
        embed.add_field(name="Bank", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['bank']:,}")
        await ctx.send(embed=embed)

    @commands.command()
    async def work(self, ctx):
        data = await get_user_data(ctx.author.id, ctx.guild.id)
        now = datetime.datetime.utcnow()
        
        # Check cooldown
        if data.get("work_claimed"):
            last = datetime.datetime.fromisoformat(data["work_claimed"])
            if (now - last).total_seconds() < CONFIG["WORK_COOLDOWN"]:
                return await ctx.send("⌛ You're tired! Take a break.")

        earned = random.randint(CONFIG["WORK_MIN"], CONFIG["WORK_MAX"])
        await update_user_data(ctx.author.id, ctx.guild.id, 
                               balance=data["balance"] + earned, 
                               work_claimed=now.isoformat())
        await ctx.send(f"💼 You worked and earned {CONFIG['CURRENCY_SYMBOL']} **{earned}**!")

async def setup(bot):
    await bot.add_cog(Economy(bot))
