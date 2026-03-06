import discord
import os
import asyncio
from discord.ext import commands
from collections import defaultdict
from utils import CONFIG, init_database

class UltimateBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=CONFIG["PREFIX"], intents=intents, help_command=None)
        
        # Global Caches (Shared across files)
        self.spam_tracker = defaultdict(list)
        self.xp_cooldowns = {}
        self.afk_users = {}

    async def setup_hook(self):
        # Initializing database
        await init_database()
        
        # Loading all files from /cogs folder
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'🚀 Loaded Module: {filename}')

bot = UltimateBot()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} | ID: {bot.user.id}")

if __name__ == "__main__":
    bot.run(CONFIG["TOKEN"])
