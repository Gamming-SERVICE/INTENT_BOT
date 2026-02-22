import discord
from discord.ext import commands
import config
import database
import os
import asyncio

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

async def get_dynamic_prefix(bot, message):
    if not message.guild:
        return config.DEFAULT_PREFIX
    return await database.get_prefix(message.guild.id)

bot = commands.Bot(
    command_prefix=get_dynamic_prefix,
    intents=intents
)

async def load_cogs():
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            await bot.load_extension(f"cogs.{file[:-3]}")

@bot.event
async def on_ready():
    await database.init_db()
    await load_cogs()
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.hybrid_command()
async def ping(ctx):
    await ctx.reply(f"Pong! {round(bot.latency * 1000)}ms")

bot.run(config.TOKEN)
