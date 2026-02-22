import discord
from discord.ext import commands
import asyncio
import logging

import config
from logger import setup_logger
from restart import graceful_crash
from database import get_prefix

setup_logger()

intents = discord.Intents.all()

async def prefix_callable(bot, message):
    if not message.guild:
        return config.DEFAULT_PREFIX
    return await get_prefix(message.guild.id)

bot = commands.Bot(
    command_prefix=prefix_callable,
    intents=intents
)

@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} ({bot.user.id})")
    await bot.tree.sync()

async def load_cogs():
    await bot.load_extension("cogs.prefix")
    await bot.load_extension("cogs.broadcast")
    await bot.load_extension("cogs.admin")
    await bot.load_extension("cogs.music")
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.market")
    await bot.load_extension("cogs.events")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(config.TOKEN)

try:
    asyncio.run(main())
except Exception:
    asyncio.run(graceful_crash())
