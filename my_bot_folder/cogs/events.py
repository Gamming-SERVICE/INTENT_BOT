import discord
import time
from discord.ext import commands
from database import get_user_data, update_user_data

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        # Leveling System
        user_id, guild_id = message.author.id, message.guild.id
        now = time.time()
        if user_id not in self.bot.xp_cooldowns or now - self.bot.xp_cooldowns[user_id] > 60:
            self.bot.xp_cooldowns[user_id] = now
            data = await get_user_data(user_id, guild_id)
            xp_gain = random.randint(15, 25)
            await update_user_data(user_id, guild_id, xp=data['xp'] + xp_gain)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if self.bot.config["WELCOME_ENABLED"]:
            print(f"👋 {member.name} joined {member.guild.name}")

async def setup(bot):
    await bot.add_cog(Events(bot))
