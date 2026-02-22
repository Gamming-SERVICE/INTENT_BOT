import wavelink
from discord.ext import commands
import config

class Music(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.connect_nodes())

    async def connect_nodes(self):
        await self.bot.wait_until_ready()

        await wavelink.NodePool.create_node(
            bot=self.bot,
            host=config.LAVALINK_HOST,
            port=config.LAVALINK_PORT,
            password=config.LAVALINK_PASSWORD
        )

    @commands.command()
    async def play(self, ctx, *, query):
        if not ctx.author.voice:
            return await ctx.send("Join voice channel.")

        vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)

        tracks = await wavelink.YouTubeTrack.search(query)
        await vc.play(tracks[0])
        await ctx.send(f"Playing: {tracks[0].title}")

async def setup(bot):
    await bot.add_cog(Music(bot))
