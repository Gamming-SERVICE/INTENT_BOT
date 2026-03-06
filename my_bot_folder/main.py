import discord
import os
import asyncio
from discord.ext import commands
from collections import defaultdict
from database import init_database

# Configuration
CONFIG = {
    "TOKEN": "YOUR_ACTUAL_TOKEN",
    "PREFIX": "!",
}

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=CONFIG["PREFIX"], intents=intents, help_command=None)
        
        # Shared Caches moved here (accessible via bot.afk_users)
        self.spam_tracker = defaultdict(list)
        self.xp_cooldowns = {}
        self.active_giveaways = {}
        self.afk_users = {}
        self.custom_commands = {}

    async def setup_hook(self):
        # 1. Init Database
        await init_database()
        
        # 2. Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'✅ Loaded: {filename}')
                except Exception as e:
                    print(f'❌ Failed to load {filename}: {e}')

bot = MyBot()

if __name__ == "__main__":
    bot.run(CONFIG["TOKEN"])
