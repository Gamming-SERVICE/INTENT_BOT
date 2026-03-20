import random
import time

from discord.ext import commands

from config import CONFIG
from database import get_user_data, update_user_data


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message) -> None:
        if message.author.bot or not message.guild:
            return

        if CONFIG["LEVELING_ENABLED"]:
            user_id = message.author.id
            now = time.time()
            cooldown = CONFIG["XP_COOLDOWN"]
            if user_id not in self.bot.xp_cooldowns or now - self.bot.xp_cooldowns[user_id] > cooldown:
                self.bot.xp_cooldowns[user_id] = now
                data = await get_user_data(user_id, message.guild.id)
                xp_min, xp_max = CONFIG["XP_PER_MESSAGE"]
                xp_gain = random.randint(xp_min, xp_max)
                await update_user_data(user_id, message.guild.id, xp=data["xp"] + xp_gain, messages=data["messages"] + 1)

        await self.bot.process_commands(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))
