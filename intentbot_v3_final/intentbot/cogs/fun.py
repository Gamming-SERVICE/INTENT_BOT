# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Fun Cog
#                   PREFIX-ONLY | No slash commands
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import random

import aiohttp
import discord
from discord.ext import commands

from core.constants import EIGHTBALL_RESPONSES, FUN_FACTS
import core.embeds as emb
from core.logger import get_logger

log = get_logger("fun")

_RPS_EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
_RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


class Fun(commands.Cog, name="Fun"):
    """Fun and entertainment commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot    = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()

    # ── 8-ball ─────────────────────────────────────────────────────────────────

    @commands.command(name="8ball", aliases=["eightball"])
    async def eightball(self, ctx: commands.Context, *, question: str) -> None:
        """Ask the magic 8-ball. Usage: !8ball <question>"""
        answer = random.choice(EIGHTBALL_RESPONSES)
        color  = (
            discord.Color.green()  if any(w in answer.lower() for w in ("yes", "certain", "definitely", "good")) else
            discord.Color.red()    if any(w in answer.lower() for w in ("no", "doubtful", "not")) else
            discord.Color.yellow()
        )
        await ctx.send(embed=emb.build(
            title="🎱 Magic 8-Ball",
            description=f"**Q:** {question}\n\n**A:** {answer}",
            color=color,
            author=ctx.author,
        ))

    # ── Coinflip ───────────────────────────────────────────────────────────────

    @commands.command(name="coinflip", aliases=["flip", "coin"])
    async def coinflip(self, ctx: commands.Context) -> None:
        """Flip a coin. Usage: !coinflip"""
        result = random.choice(["🪙 Heads", "🪙 Tails"])
        await ctx.send(embed=emb.build(
            title="🪙 Coin Flip",
            description=f"**{result}**!",
            color=discord.Color.gold(),
            timestamp=False,
        ))

    # ── Dice ───────────────────────────────────────────────────────────────────

    @commands.command(name="roll", aliases=["dice", "d"])
    async def roll(self, ctx: commands.Context, dice: str = "1d6") -> None:
        """Roll dice. Usage: !roll [2d6|d20] (default 1d6)"""
        try:
            parts = dice.lower().replace(" ", "").split("d")
            count = int(parts[0]) if parts[0] else 1
            sides = int(parts[1])
            if not (1 <= count <= 100 and 2 <= sides <= 1000):
                raise ValueError
        except (ValueError, IndexError):
            return await ctx.send(embed=emb.error("Invalid dice format. Use `2d6`, `d20`, etc."))
        rolls  = [random.randint(1, sides) for _ in range(count)]
        total  = sum(rolls)
        detail = ", ".join(str(r) for r in rolls) if count > 1 else ""
        desc   = f"**Total: {total}**" + (f"\nRolls: {detail}" if detail else "")
        await ctx.send(embed=emb.build(
            title=f"🎲 {dice.upper()}",
            description=desc,
            color=discord.Color.blurple(),
            timestamp=False,
        ))

    # ── Rock Paper Scissors ────────────────────────────────────────────────────

    @commands.command(name="rps")
    async def rps(self, ctx: commands.Context, choice: str) -> None:
        """Play Rock, Paper, Scissors. Usage: !rps <rock|paper|scissors>"""
        choice = choice.lower()
        if choice not in _RPS_EMOJI:
            return await ctx.send(embed=emb.error("Choose `rock`, `paper`, or `scissors`."))
        bot_choice = random.choice(["rock", "paper", "scissors"])
        if choice == bot_choice:
            result, color = "🟡 It's a tie!", discord.Color.yellow()
        elif _RPS_BEATS[choice] == bot_choice:
            result, color = "✅ You win!", discord.Color.green()
        else:
            result, color = "❌ You lose!", discord.Color.red()
        await ctx.send(embed=emb.build(
            title="✊ Rock Paper Scissors",
            description=f"{_RPS_EMOJI[choice]} You vs {_RPS_EMOJI[bot_choice]} Me\n\n**{result}**",
            color=color,
            timestamp=False,
        ))

    # ── Fact ───────────────────────────────────────────────────────────────────

    @commands.command(name="fact")
    async def fact(self, ctx: commands.Context) -> None:
        """Get a random fun fact. Usage: !fact"""
        await ctx.send(embed=emb.build(
            title="💡 Fun Fact",
            description=random.choice(FUN_FACTS),
            color=discord.Color.teal(),
            timestamp=False,
        ))

    # ── Joke ───────────────────────────────────────────────────────────────────

    @commands.command(name="joke")
    async def joke(self, ctx: commands.Context) -> None:
        """Get a random joke. Usage: !joke"""
        async with ctx.typing():
            try:
                async with self._session.get(
                    "https://official-joke-api.appspot.com/random_joke",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return await ctx.send(embed=emb.build(
                            title="😂 Joke",
                            description=f"**{data['setup']}**\n\n||{data['punchline']}||",
                            color=discord.Color.yellow(),
                            timestamp=False,
                        ))
            except Exception:
                pass
        jokes = [
            ("Why don't scientists trust atoms?", "Because they make up everything!"),
            ("I told my wife she was drawing her eyebrows too high.", "She looked surprised."),
            ("What do you call a fake noodle?", "An impasta!"),
            ("Why can't you give Elsa a balloon?", "Because she'll let it go!"),
            ("I'm reading a book about anti-gravity.", "It's impossible to put down."),
        ]
        setup, punchline = random.choice(jokes)
        await ctx.send(embed=emb.build(
            title="😂 Joke",
            description=f"**{setup}**\n\n||{punchline}||",
            color=discord.Color.yellow(),
            timestamp=False,
        ))

    # ── Cat / Dog ──────────────────────────────────────────────────────────────

    @commands.command(name="cat")
    async def cat(self, ctx: commands.Context) -> None:
        """Get a random cat image. Usage: !cat"""
        await self._animal(ctx, "https://api.thecatapi.com/v1/images/search", "list.0.url", "🐱 Meow!")

    @commands.command(name="dog")
    async def dog(self, ctx: commands.Context) -> None:
        """Get a random dog image. Usage: !dog"""
        await self._animal(ctx, "https://dog.ceo/api/breeds/image/random", "message", "🐶 Woof!")

    async def _animal(self, ctx: commands.Context, url: str, key_path: str, title: str) -> None:
        async with ctx.typing():
            try:
                async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    img  = data
                    for k in key_path.split("."):
                        img = img[int(k)] if k.isdigit() else img[k]
                    return await ctx.send(embed=emb.build(
                        title=title, color=discord.Color.blurple(), image=img, timestamp=False
                    ))
            except Exception:
                pass
        await ctx.send(embed=emb.error("Could not fetch image right now."))

    # ── Choose ─────────────────────────────────────────────────────────────────

    @commands.command(name="choose")
    async def choose(self, ctx: commands.Context, *, options: str) -> None:
        """Choose from comma-separated options. Usage: !choose pizza, sushi, tacos"""
        choices = [o.strip() for o in options.split(",") if o.strip()]
        if len(choices) < 2:
            return await ctx.send(embed=emb.error("Provide at least 2 comma-separated options."))
        picked = random.choice(choices)
        await ctx.send(embed=emb.build(
            title="🎲 I Choose…",
            description=f"**{picked}**",
            color=discord.Color.blurple(),
            timestamp=False,
            fields=[("Options", ", ".join(choices[:10]), False)],
        ))

    # ── Meme ───────────────────────────────────────────────────────────────────

    @commands.command(name="meme")
    async def meme(self, ctx: commands.Context) -> None:
        """Get a random meme. Usage: !meme"""
        async with ctx.typing():
            try:
                async with self._session.get(
                    "https://meme-api.com/gimme",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = emb.build(
                            title=data["title"],
                            color=discord.Color.orange(),
                            image=data["url"],
                            timestamp=False,
                        )
                        embed.set_footer(text=f"👍 {data.get('ups', 0):,} • r/{data.get('subreddit', 'memes')}")
                        return await ctx.send(embed=embed)
            except Exception:
                pass
        await ctx.send(embed=emb.error("Could not fetch a meme right now."))

    # ── Waifu ──────────────────────────────────────────────────────────────────

    @commands.command(name="waifu")
    async def waifu(self, ctx: commands.Context) -> None:
        """Get a random waifu image. Usage: !waifu"""
        async with ctx.typing():
            try:
                async with self._session.get(
                    "https://api.waifu.pics/sfw/waifu",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return await ctx.send(embed=emb.build(
                            title="🌸 Waifu",
                            color=discord.Color.pink(),
                            image=data["url"],
                            timestamp=False,
                        ))
            except Exception:
                pass
        await ctx.send(embed=emb.error("Could not fetch waifu image right now."))

    # ── Hug / Pat ──────────────────────────────────────────────────────────────

    @commands.command(name="hug")
    @commands.guild_only()
    async def hug(self, ctx: commands.Context, member: discord.Member) -> None:
        """Hug someone. Usage: !hug @user"""
        async with ctx.typing():
            try:
                async with self._session.get(
                    "https://api.waifu.pics/sfw/hug",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        url = (await resp.json())["url"]
                        return await ctx.send(embed=emb.build(
                            title="🤗 Hug!",
                            description=f"{ctx.author.mention} hugged {member.mention}!",
                            color=discord.Color.pink(),
                            image=url,
                            timestamp=False,
                        ))
            except Exception:
                pass
        await ctx.send(f"🤗 {ctx.author.mention} hugged {member.mention}!")

    @commands.command(name="pat")
    @commands.guild_only()
    async def pat(self, ctx: commands.Context, member: discord.Member) -> None:
        """Pat someone. Usage: !pat @user"""
        async with ctx.typing():
            try:
                async with self._session.get(
                    "https://api.waifu.pics/sfw/pat",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        url = (await resp.json())["url"]
                        return await ctx.send(embed=emb.build(
                            title="🥺 Pat!",
                            description=f"{ctx.author.mention} patted {member.mention}!",
                            color=discord.Color.pink(),
                            image=url,
                            timestamp=False,
                        ))
            except Exception:
                pass
        await ctx.send(f"🥺 {ctx.author.mention} patted {member.mention}!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
    log.info("Fun cog loaded")
