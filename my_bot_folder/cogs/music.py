import discord
from discord.ext import commands
import wavelink
import asyncio

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_queues = {}

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"✅ Lavalink Node {payload.node.identifier} is ready!")

    @commands.command()
    async def join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first.")
        
        await ctx.author.voice.channel.connect(cls=wavelink.Player)
        await ctx.send(f"✅ Joined {ctx.author.voice.channel.name}")

    @commands.command()
    async def play(self, ctx, *, search: str):
        if not ctx.voice_client:
            await ctx.invoke(self.join)

        vc: wavelink.Player = ctx.voice_client
        tracks = await wavelink.Playable.search(search)
        if not tracks:
            return await ctx.send("❌ No results found.")

        track = tracks[0]
        await vc.queue.put_wait(track)
        
        if not vc.playing:
            await vc.play(vc.queue.get())
            await ctx.send(f"🎵 Now playing: **{track.title}**")
        else:
            await ctx.send(f"✅ Added to queue: **{track.title}**")

    @commands.command()
    async def skip(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if vc and vc.playing:
            await vc.skip()
            await ctx.send("⏭️ Skipped current song.")

    @commands.command()
    async def stop(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if vc:
            await vc.disconnect()
            await ctx.send("⏹️ Disconnected and cleared queue.")

async def setup(bot):
    await bot.add_cog(Music(bot))
