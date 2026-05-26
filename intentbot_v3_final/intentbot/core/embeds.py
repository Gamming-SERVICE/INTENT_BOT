# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — Embed Factory
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
from typing import Any

import discord

from core.constants import RARITY_COLORS, BOT_NAME, BOT_VERSION


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def build(
    title: str,
    description: str | None = None,
    color: discord.Color | None = None,
    *,
    author: discord.Member | discord.User | None = None,
    footer: str | None = None,
    thumbnail: str | None = None,
    image: str | None = None,
    fields: list[tuple[str, str, bool]] | None = None,
    url: str | None = None,
    timestamp: bool = True,
) -> discord.Embed:
    """
    Build a Discord embed with consistent styling.

    Parameters
    ----------
    fields : list of (name, value, inline)
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.blurple(),
        url=url,
    )
    if timestamp:
        embed.timestamp = _now()
    if author:
        embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    if footer:
        embed.set_footer(text=footer)
    else:
        embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}")
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=str(value)[:1024] or "\u200b", inline=inline)
    return embed


def success(description: str, *, title: str = "✅ Success") -> discord.Embed:
    return build(title, description, color=discord.Color.green(), timestamp=False)


def error(description: str, *, title: str = "❌ Error") -> discord.Embed:
    return build(title, description, color=discord.Color.red(), timestamp=False)


def warning(description: str, *, title: str = "⚠️ Warning") -> discord.Embed:
    return build(title, description, color=discord.Color.yellow(), timestamp=False)


def info(description: str, *, title: str = "ℹ️ Info") -> discord.Embed:
    return build(title, description, color=discord.Color.blurple(), timestamp=False)


def rarity(rarity_name: str, **kwargs: Any) -> discord.Embed:
    """Build an embed colored by item rarity."""
    color = RARITY_COLORS.get(rarity_name, discord.Color.blurple())
    return build(color=color, **kwargs)


def paginate(items: list[str], per_page: int = 10, *, title: str, color: discord.Color | None = None) -> list[discord.Embed]:
    """Split a list of strings into paginated embeds."""
    pages: list[discord.Embed] = []
    chunks = [items[i:i + per_page] for i in range(0, max(len(items), 1), per_page)]
    total = len(chunks)
    for i, chunk in enumerate(chunks, 1):
        embed = build(
            title=title,
            description="\n".join(chunk),
            color=color or discord.Color.blurple(),
        )
        embed.set_footer(text=f"Page {i}/{total} • {BOT_NAME} v{BOT_VERSION}")
        pages.append(embed)
    return pages
