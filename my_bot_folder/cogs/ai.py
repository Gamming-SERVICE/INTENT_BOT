import discord
import aiohttp
from discord.ext import commands

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def gemini(self, ctx, *, prompt):
        key = self.bot.config["AI_KEYS"]["gemini"]
        if not key: return await ctx.send("❌ Gemini API Key not set in config.")
        
        async with ctx.typing():
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()
                    response = data["candidates"][0]["content"]["parts"][0]["text"]
                    await ctx.send(response[:2000])

async def setup(bot):
    await bot.add_cog(AI(bot))
