import discord
import os
import asyncio
from discord.ext import commands
from config import CONFIG

class UltimateBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=CONFIG["PREFIX"], intents=intents, help_command=None)

    async def setup_hook(self):
        # This loads every .py file in the /cogs folder
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'✅ Loaded Cog: {filename}')

bot = UltimateBot()

@bot.command()
@commands.is_owner()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Synced slash commands!")

if __name__ == "__main__":
    bot.run(CONFIG["TOKEN"])
