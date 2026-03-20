import datetime
import re

import discord


def create_embed(title: str, description: str | None = None, color: discord.Color = discord.Color.blurple()) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.datetime.utcnow()
    return embed


def parse_time(time_str: str) -> int | None:
    time_regex = re.compile(r"(\d+)([smhdw])")
    matches = time_regex.findall(time_str.lower())
    if not matches:
        return None

    total_seconds = 0
    for value, unit in matches:
        amount = int(value)
        if unit == "s":
            total_seconds += amount
        elif unit == "m":
            total_seconds += amount * 60
        elif unit == "h":
            total_seconds += amount * 3600
        elif unit == "d":
            total_seconds += amount * 86400
        elif unit == "w":
            total_seconds += amount * 604800
    return total_seconds
