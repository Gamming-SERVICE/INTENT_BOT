import discord
import datetime

def create_embed(title, description=None, color=discord.Color.blurple()):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    return embed
