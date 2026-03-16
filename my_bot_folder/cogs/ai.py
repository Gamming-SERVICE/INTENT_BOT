import aiohttp
from discord.ext import commands

POLLINATIONS_URL = "https://text.pollinations.ai/openai"
SYSTEM_PROMPT = (
    "You are bot in discord server of Intent FreeDomain, we provide free subdomains "
    "like .int.yt,.nc.to,.rh.to,.gw.to,.yn.to , intent is a nonprofit providing free "
    "subdomains to everyone, your name is Intent AI Bot"
)


class AI(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="intentai", aliases=["pollinate", "askai"])
    async def intent_ai(self, ctx: commands.Context, *, prompt: str) -> None:
        payload = {
            "model": "openai",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"@{ctx.author.display_name} {prompt}"},
            ],
            "temperature": 0.7,
            "max_tokens": 500,
            "stream": False,
            "reasoning_effort": "medium",
        }

        async with ctx.typing():
            try:
                timeout = aiohttp.ClientTimeout(total=45)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(POLLINATIONS_URL, json=payload) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            await ctx.send(f"❌ Pollinations API error ({resp.status}): {error_text[:500]}")
                            return

                        data = await resp.json()
            except aiohttp.ClientError:
                await ctx.send("❌ Could not reach Pollinations API. Please try again.")
                return

        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            await ctx.send("❌ No response from Pollinations API.")
            return

        for chunk_start in range(0, len(content), 1900):
            await ctx.send(content[chunk_start : chunk_start + 1900])

    @commands.command()
    async def gemini(self, ctx: commands.Context, *, prompt: str) -> None:
        key = self.bot.config.get("AI_KEYS", {}).get("gemini", "")
        if not key:
            await ctx.send("❌ Gemini API key is not configured in config.py")
            return

        async with ctx.typing():
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}

            try:
                timeout = aiohttp.ClientTimeout(total=45)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            await ctx.send(f"❌ Gemini API error ({resp.status}): {error_text[:500]}")
                            return
                        data = await resp.json()
            except aiohttp.ClientError:
                await ctx.send("❌ Could not reach Gemini API. Please try again.")
                return

        try:
            response = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            await ctx.send("❌ Gemini returned an unexpected response format.")
            return

        for chunk_start in range(0, len(response), 1900):
            await ctx.send(response[chunk_start : chunk_start + 1900])


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AI(bot))
