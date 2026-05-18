# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Fun Cog
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import random

import aiohttp
import discord
from discord import app_commands
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

    @commands.hybrid_command(name="8ball", aliases=["eightball"], description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question")
    async def eightball(self, ctx: commands.Context, *, question: str) -> None:
        answer = random.choice(EIGHTBALL_RESPONSES)
        color  = (
            discord.Color.green()  if any(w in answer.lower() for w in ("yes", "certain", "definitely", "good")) else
            discord.Color.red()    if any(w in answer.lower() for w in ("no", "doubtful", "not")) else
            discord.Color.yellow()
        )
        await ctx.send(
            embed=emb.build(
                title="🎱 Magic 8-Ball",
                description=f"**Question:** {question}\n\n**Answer:** {answer}",
                color=color,
                author=ctx.author,
            )
        )

    # ── Coinflip ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="coinflip", aliases=["flip", "coin"], description="Flip a coin")
    async def coinflip(self, ctx: commands.Context) -> None:
        result = random.choice(["🪙 Heads", "🪙 Tails"])
        await ctx.send(embed=emb.build(title="🪙 Coin Flip", description=f"**{result}**!", color=discord.Color.gold(), timestamp=False))

    # ── Dice ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="roll", aliases=["dice", "d"], description="Roll dice (e.g. 2d6, d20)")
    @app_commands.describe(dice="Dice notation like 2d6 or d20 (default 1d6)")
    async def roll(self, ctx: commands.Context, dice: str = "1d6") -> None:
        try:
            parts = dice.lower().replace(" ", "").split("d")
            count = int(parts[0]) if parts[0] else 1
            sides = int(parts[1])
            if not (1 <= count <= 100 and 2 <= sides <= 1000):
                raise ValueError
        except (ValueError, IndexError):
            return await ctx.send(embed=emb.error("Invalid dice format. Use something like `2d6` or `d20`."))
        rolls  = [random.randint(1, sides) for _ in range(count)]
        total  = sum(rolls)
        detail = ", ".join(str(r) for r in rolls) if count > 1 else ""
        desc   = f"**Total: {total}**" + (f"\nRolls: {detail}" if detail else "")
        await ctx.send(embed=emb.build(title=f"🎲 {dice.upper()}", description=desc, color=discord.Color.blurple(), timestamp=False))

    # ── Rock Paper Scissors ────────────────────────────────────────────────────

    @commands.hybrid_command(name="rps", description="Play Rock, Paper, Scissors")
    @app_commands.describe(choice="Your choice")
    @app_commands.choices(choice=[
        app_commands.Choice(name="🪨 Rock",     value="rock"),
        app_commands.Choice(name="📄 Paper",    value="paper"),
        app_commands.Choice(name="✂️ Scissors", value="scissors"),
    ])
    async def rps(self, ctx: commands.Context, choice: str) -> None:
        bot_choice = random.choice(["rock", "paper", "scissors"])
        player_e   = _RPS_EMOJI[choice]
        bot_e      = _RPS_EMOJI[bot_choice]
        if choice == bot_choice:
            result, color = "🟡 It's a tie!", discord.Color.yellow()
        elif _RPS_BEATS[choice] == bot_choice:
            result, color = "✅ You win!", discord.Color.green()
        else:
            result, color = "❌ You lose!", discord.Color.red()
        await ctx.send(
            embed=emb.build(
                title="✊ Rock Paper Scissors",
                description=f"{player_e} You vs {bot_e} Me\n\n**{result}**",
                color=color,
                timestamp=False,
            )
        )

    # ── Fun fact ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="fact", description="Get a random fun fact")
    async def fact(self, ctx: commands.Context) -> None:
        await ctx.send(embed=emb.build(title="💡 Fun Fact", description=random.choice(FUN_FACTS), color=discord.Color.teal(), timestamp=False))

    # ── Random joke ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="joke", description="Get a random joke")
    async def joke(self, ctx: commands.Context) -> None:
        async with ctx.typing():
            try:
                async with self._session.get(
                    "https://official-joke-api.appspot.com/random_joke",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        await ctx.send(
                            embed=emb.build(
                                title="😂 Joke",
                                description=f"**{data['setup']}**\n\n||{data['punchline']}||",
                                color=discord.Color.yellow(),
                                timestamp=False,
                            )
                        )
                        return
            except Exception:
                pass
        # Fallback local jokes
        jokes = [
            ("Why don't scientists trust atoms?", "Because they make up everything!"),
            ("I told my wife she was drawing her eyebrows too high.", "She looked surprised."),
            ("What do you call a fake noodle?", "An impasta!"),
            ("Why can't you give Elsa a balloon?", "Because she'll let it go!"),
            ("I'm reading a book about anti-gravity.", "It's impossible to put down."),
        ]
        setup, punchline = random.choice(jokes)
        await ctx.send(
            embed=emb.build(
                title="😂 Joke",
                description=f"**{setup}**\n\n||{punchline}||",
                color=discord.Color.yellow(),
                timestamp=False,
            )
        )

    # ── Cat / Dog images ───────────────────────────────────────────────────────

    @commands.hybrid_command(name="cat", description="Get a random cat image 🐱")
    async def cat(self, ctx: commands.Context) -> None:
        await self._animal_image(ctx, "https://api.thecatapi.com/v1/images/search", "url", "🐱 Meow!")

    @commands.hybrid_command(name="dog", description="Get a random dog image 🐶")
    async def dog(self, ctx: commands.Context) -> None:
        await self._animal_image(ctx, "https://dog.ceo/api/breeds/image/random", "message", "🐶 Woof!")

    async def _animal_image(self, ctx: commands.Context, url: str, key: str, title: str) -> None:
        async with ctx.typing():
            try:
                async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    img  = data[0][key] if isinstance(data, list) else data[key]
                    await ctx.send(embed=emb.build(title=title, color=discord.Color.blurple(), image=img, timestamp=False))
                    return
            except Exception:
                pass
        await ctx.send(embed=emb.error("Could not fetch an image right now. Try again!"))

    # ── Choose ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="choose", description="Choose between multiple options")
    @app_commands.describe(options="Comma-separated options (e.g. pizza, burger, sushi)")
    async def choose(self, ctx: commands.Context, *, options: str) -> None:
        choices = [o.strip() for o in options.split(",") if o.strip()]
        if len(choices) < 2:
            return await ctx.send(embed=emb.error("Please provide at least 2 comma-separated options."))
        picked = random.choice(choices)
        await ctx.send(
            embed=emb.build(
                title="🎲 I Choose…",
                description=f"**{picked}**",
                color=discord.Color.blurple(),
                timestamp=False,
                fields=[("Options", ", ".join(choices), False)],
            )
        )

    # ── Meme ───────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="meme", description="Get a random meme from Reddit")
    async def meme(self, ctx: commands.Context) -> None:
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
                        await ctx.send(embed=embed)
                        return
            except Exception:
                pass
        await ctx.send(embed=emb.error("Could not fetch a meme right now."))

    # ── Waifu ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="waifu", description="Get a random waifu image")
    async def waifu(self, ctx: commands.Context) -> None:
        async with ctx.typing():
            try:
                async with self._session.get(
                    "https://api.waifu.pics/sfw/waifu",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        await ctx.send(
                            embed=emb.build(
                                title="🌸 Waifu",
                                color=discord.Color.pink(),
                                image=data["url"],
                                timestamp=False,
                            )
                        )
                        return
            except Exception:
                pass
        await ctx.send(embed=emb.error("Could not fetch a waifu image right now."))

    # ── Hug / Pat ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="hug", description="Hug someone 🤗")
    @app_commands.describe(member="Who to hug")
    @commands.guild_only()
    async def hug(self, ctx: commands.Context, member: discord.Member) -> None:
        async with ctx.typing():
            try:
                async with self._session.get("https://api.waifu.pics/sfw/hug", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        url = (await resp.json())["url"]
                        await ctx.send(embed=emb.build(
                            title="🤗 Hug!",
                            description=f"{ctx.author.mention} hugged {member.mention}!",
                            color=discord.Color.pink(), image=url, timestamp=False))
                        return
            except Exception:
                pass
        await ctx.send(f"🤗 {ctx.author.mention} hugged {member.mention}!")

    @commands.hybrid_command(name="pat", description="Pat someone 🥺")
    @app_commands.describe(member="Who to pat")
    @commands.guild_only()
    async def pat(self, ctx: commands.Context, member: discord.Member) -> None:
        async with ctx.typing():
            try:
                async with self._session.get("https://api.waifu.pics/sfw/pat", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        url = (await resp.json())["url"]
                        await ctx.send(embed=emb.build(
                            title="🥺 Pat!",
                            description=f"{ctx.author.mention} patted {member.mention}!",
                            color=discord.Color.pink(), image=url, timestamp=False))
                        return
            except Exception:
                pass
        await ctx.send(f"🥺 {ctx.author.mention} patted {member.mention}!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
    log.info("Fun cog loaded")
