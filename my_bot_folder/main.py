import asyncio
import os
from collections import defaultdict

import discord
from discord.ext import commands

from config import CONFIG
from database import init_database


class IntentBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix=CONFIG["PREFIX"],
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

        self.config = CONFIG
        self.spam_tracker = defaultdict(list)
        self.xp_cooldowns = {}
        self.invite_cache: dict[int, dict[str, int]] = {}

    async def setup_hook(self) -> None:
        await init_database()

        cogs_path = os.path.join(os.path.dirname(__file__), "cogs")
        for filename in os.listdir(cogs_path):
            if filename.endswith(".py") and filename != "__init__.py":
                await self.load_extension(f"cogs.{filename[:-3]}")

    async def on_ready(self) -> None:
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")


async def main() -> None:
    bot = IntentBot()
    async with bot:
        await bot.start(CONFIG["TOKEN"])


if __name__ == "__main__":
    asyncio.run(main())
