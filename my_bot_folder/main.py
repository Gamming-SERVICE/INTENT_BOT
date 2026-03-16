import asyncio
import os
from collections import defaultdict

import discord
from discord.ext import commands

from config import CONFIG
from database import init_database


def _resolve_token() -> str:
    raw_token = CONFIG.get("TOKEN", "")
    token = raw_token.strip().strip('"').strip("'") if isinstance(raw_token, str) else ""

    if not token or token == "DISCORD_TOKEN":
        raise RuntimeError(
            "Discord token is missing. Set DISCORD_TOKEN (or TOKEN) environment variable in your host panel."
        )

    return token


class IntentBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix=CONFIG["PREFIX"],
            intents=intents,
            help_command=commands.DefaultHelpCommand(no_category="General"),
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
    token = _resolve_token()
    bot = IntentBot()

    try:
        async with bot:
            await bot.start(token)
    except discord.LoginFailure as exc:
        raise RuntimeError(
            "Discord login failed. Your token is invalid or belongs to a different application. "
            "Regenerate token in Discord Developer Portal and update DISCORD_TOKEN in hosting panel."
        ) from exc


if __name__ == "__main__":
    asyncio.run(main())
