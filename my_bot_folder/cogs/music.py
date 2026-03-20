from discord.ext import commands


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def join(self, ctx: commands.Context) -> None:
        if not ctx.author.voice:
            await ctx.send("❌ Join a voice channel first.")
            return
        await ctx.author.voice.channel.connect()
        await ctx.send(f"✅ Joined {ctx.author.voice.channel.name}")

    @commands.command()
    async def stop(self, ctx: commands.Context) -> None:
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ Disconnected from voice.")
        else:
            await ctx.send("I'm not in a voice channel.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
