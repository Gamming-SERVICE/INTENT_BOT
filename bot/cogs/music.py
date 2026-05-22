# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — Music Cog
#
# Uses yt-dlp + FFmpeg (no Lavalink required).
# Requires:  pip install yt-dlp PyNaCl
# Requires:  ffmpeg installed on the system
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import functools
from collections import deque
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import core.embeds as emb
from core.database import db
from core.logger import get_logger
from core.settings import GuildSettings

log = get_logger("music")

# ── yt-dlp configuration ──────────────────────────────────────────────────────
YTDL_OPTIONS: dict[str, Any] = {
    "format":          "bestaudio/best",
    "outtmpl":         "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist":      True,
    "nocheckcertificate": True,
    "ignoreerrors":    False,
    "logtostderr":     False,
    "quiet":           True,
    "no_warnings":     True,
    "default_search":  "auto",
    "source_address":  "0.0.0.0",
    "extract_flat":    False,
}

FFMPEG_OPTIONS: dict[str, Any] = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        "-loglevel warning"
    ),
    "options": "-vn",
}


def _get_ytdl():
    try:
        import yt_dlp
        return yt_dlp.YoutubeDL(YTDL_OPTIONS)
    except ImportError:
        return None


# ── Per-guild music state ─────────────────────────────────────────────────────

class GuildMusicState:
    def __init__(self) -> None:
        self.queue:        deque[dict] = deque()
        self.current:      dict | None = None
        self.volume:       float       = 0.5
        self.loop:         bool        = False
        self.loop_queue:   bool        = False
        self.vc:           discord.VoiceClient | None = None
        self._skip_flag:   bool        = False

    @property
    def is_playing(self) -> bool:
        return self.vc is not None and self.vc.is_playing()

    def clear(self) -> None:
        self.queue.clear()
        self.current = None


# Global state per guild
_states: dict[int, GuildMusicState] = {}


def _get_state(guild_id: int) -> GuildMusicState:
    if guild_id not in _states:
        _states[guild_id] = GuildMusicState()
    return _states[guild_id]


# ── Track info fetcher ────────────────────────────────────────────────────────

async def _fetch_info(query: str, loop: asyncio.AbstractEventLoop) -> dict | None:
    ytdl = _get_ytdl()
    if ytdl is None:
        return None
    if not query.startswith(("http://", "https://")):
        query = f"ytsearch:{query}"
    try:
        partial = functools.partial(ytdl.extract_info, query, download=False)
        data    = await loop.run_in_executor(None, partial)
    except Exception as e:
        log.warning("yt-dlp error: %s", e)
        return None

    if data is None:
        return None

    if "entries" in data:
        # ytsearch result — take first hit
        entries = [e for e in data["entries"] if e]
        if not entries:
            return None
        data = entries[0]

    return {
        "url":       data.get("url"),
        "title":     data.get("title", "Unknown"),
        "duration":  data.get("duration", 0),
        "thumbnail": data.get("thumbnail"),
        "webpage_url": data.get("webpage_url", ""),
        "uploader":  data.get("uploader", "Unknown"),
    }


def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return "Live"
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── Cog ───────────────────────────────────────────────────────────────────────

class Music(commands.Cog, name="Music"):
    """
    Music playback via yt-dlp + FFmpeg.

    Requires yt-dlp and FFmpeg installed.
    No Lavalink needed.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def cog_unload(self) -> None:
        for guild_id, state in _states.items():
            if state.vc:
                asyncio.create_task(state.vc.disconnect())
        _states.clear()

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _ensure_voice(self, ctx: commands.Context) -> discord.VoiceClient | None:
        """Connect to the author's voice channel. Returns VoiceClient or None."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=emb.error("You must be in a voice channel."))
            return None

        vc_channel = ctx.author.voice.channel

        if ctx.voice_client:
            if ctx.voice_client.channel != vc_channel:
                await ctx.voice_client.move_to(vc_channel)
            return ctx.voice_client

        try:
            return await vc_channel.connect(timeout=10, reconnect=True)
        except asyncio.TimeoutError:
            await ctx.send(embed=emb.error("Timed out connecting to voice channel."))
            return None
        except discord.ClientException as e:
            await ctx.send(embed=emb.error(f"Voice connection error: {e}"))
            return None

    def _play_next(self, guild_id: int, error: Exception | None = None) -> None:
        """Called by discord.py after a track finishes."""
        if error:
            log.error("Playback error in guild %d: %s", guild_id, error)

        state = _get_state(guild_id)

        if state.loop and state.current and not state._skip_flag:
            # Re-queue current track at front
            state.queue.appendleft(state.current)

        elif state.loop_queue and state.current:
            state.queue.append(state.current)

        state._skip_flag = False
        state.current    = None

        if state.queue:
            asyncio.run_coroutine_threadsafe(
                self._play_track(guild_id), self.bot.loop
            )

    async def _play_track(self, guild_id: int) -> None:
        state = _get_state(guild_id)
        if not state.queue or not state.vc:
            return

        track = state.queue.popleft()
        state.current = track

        try:
            source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=state.volume)
            state.vc.play(source, after=lambda e: self._play_next(guild_id, e))
            log.info("Now playing in guild %d: %s", guild_id, track["title"])
        except Exception as e:
            log.error("Failed to play track in guild %d: %s", guild_id, e)
            state.current = None
            if state.queue:
                await self._play_track(guild_id)

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="play", aliases=["p"], description="Play a song or add it to the queue")
    @app_commands.describe(query="Song name or YouTube/Spotify URL")
    @commands.guild_only()
    @commands.cooldown(2, 5, commands.BucketType.guild)
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        if _get_ytdl() is None:
            return await ctx.send(embed=emb.error(
                "Music is not available. Install yt-dlp:\n`pip install yt-dlp`"
            ))

        vc = await self._ensure_voice(ctx)
        if vc is None:
            return

        state     = _get_state(ctx.guild.id)
        state.vc  = vc

        await ctx.defer()
        track = await _fetch_info(query, self.bot.loop)

        if not track:
            return await ctx.send(embed=emb.error(f"Could not find anything for: **{query}**"))

        state.queue.append(track)
        duration = _fmt_duration(track["duration"])

        if state.is_playing:
            embed = emb.build(
                title="📋 Added to Queue",
                description=f"[{track['title']}]({track['webpage_url']})",
                color=discord.Color.blurple(),
                thumbnail=track.get("thumbnail"),
                fields=[
                    ("Duration",  duration,                      True),
                    ("Uploader",  track["uploader"],             True),
                    ("Position",  str(len(state.queue)),         True),
                ],
            )
            await ctx.send(embed=embed)
        else:
            await self._play_track(ctx.guild.id)
            embed = emb.build(
                title="▶️ Now Playing",
                description=f"[{track['title']}]({track['webpage_url']})",
                color=discord.Color.green(),
                thumbnail=track.get("thumbnail"),
                fields=[
                    ("Duration", duration,          True),
                    ("Uploader", track["uploader"], True),
                    ("Volume",   f"{int(state.volume * 100)}%", True),
                ],
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="skip", aliases=["s"], description="Skip the current track")
    @commands.guild_only()
    async def skip(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        if not state.is_playing:
            return await ctx.send(embed=emb.error("Nothing is playing."))
        state._skip_flag = True
        state.vc.stop()
        await ctx.send(embed=emb.success("⏭️ Skipped!"))

    @commands.hybrid_command(name="stop", description="Stop music and clear the queue")
    @commands.guild_only()
    async def stop(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        state.clear()
        state.loop       = False
        state.loop_queue = False
        if state.vc and state.vc.is_playing():
            state.vc.stop()
        await ctx.send(embed=emb.success("⏹️ Stopped and queue cleared."))

    @commands.hybrid_command(name="pause", description="Pause the current track")
    @commands.guild_only()
    async def pause(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        if state.vc and state.vc.is_playing():
            state.vc.pause()
            await ctx.send(embed=emb.success("⏸️ Paused."))
        else:
            await ctx.send(embed=emb.error("Nothing is playing."))

    @commands.hybrid_command(name="resume", description="Resume a paused track")
    @commands.guild_only()
    async def resume(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        if state.vc and state.vc.is_paused():
            state.vc.resume()
            await ctx.send(embed=emb.success("▶️ Resumed."))
        else:
            await ctx.send(embed=emb.error("Nothing is paused."))

    @commands.hybrid_command(name="volume", aliases=["vol"], description="Set volume (0–200)")
    @app_commands.describe(level="Volume level 0–200")
    @commands.guild_only()
    async def volume(self, ctx: commands.Context, level: int) -> None:
        if not 0 <= level <= 200:
            return await ctx.send(embed=emb.error("Volume must be between 0 and 200."))
        state = _get_state(ctx.guild.id)
        state.volume = level / 100
        if state.vc and state.vc.source:
            state.vc.source.volume = state.volume
        await ctx.send(embed=emb.success(f"🔊 Volume set to **{level}%**"))

    @commands.hybrid_command(name="queue", aliases=["q"], description="Show the music queue")
    @commands.guild_only()
    async def queue_cmd(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        if not state.current and not state.queue:
            return await ctx.send(embed=emb.info("The queue is empty. Use `/play` to add songs!"))

        lines = []
        if state.current:
            dur = _fmt_duration(state.current["duration"])
            lines.append(f"**▶️ Now:** [{state.current['title']}]({state.current['webpage_url']}) `{dur}`")

        for i, track in enumerate(list(state.queue)[:10], 1):
            dur = _fmt_duration(track["duration"])
            lines.append(f"**{i}.** [{track['title']}]({track['webpage_url']}) `{dur}`")

        if len(state.queue) > 10:
            lines.append(f"\n*...and {len(state.queue) - 10} more tracks*")

        loop_status = "🔂 Track" if state.loop else ("🔁 Queue" if state.loop_queue else "Off")
        embed = emb.build(
            title=f"🎵 Music Queue — {len(state.queue)} tracks",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            fields=[
                ("Loop",   loop_status,                           True),
                ("Volume", f"{int(state.volume * 100)}%",         True),
            ],
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show the current track")
    @commands.guild_only()
    async def nowplaying(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        if not state.current:
            return await ctx.send(embed=emb.info("Nothing is playing."))
        t = state.current
        embed = emb.build(
            title="▶️ Now Playing",
            description=f"[{t['title']}]({t['webpage_url']})",
            color=discord.Color.green(),
            thumbnail=t.get("thumbnail"),
            fields=[
                ("Duration", _fmt_duration(t["duration"]), True),
                ("Uploader", t["uploader"],                True),
                ("Volume",   f"{int(state.volume * 100)}%", True),
                ("Loop",     "On" if state.loop else "Off",True),
            ],
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="loop", description="Toggle loop for the current track")
    @commands.guild_only()
    async def loop(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        state.loop       = not state.loop
        state.loop_queue = False
        status = "🔂 Loop enabled" if state.loop else "Loop disabled"
        await ctx.send(embed=emb.success(status))

    @commands.hybrid_command(name="loopqueue", aliases=["lq"], description="Toggle queue loop")
    @commands.guild_only()
    async def loopqueue(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        state.loop_queue = not state.loop_queue
        state.loop       = False
        status = "🔁 Queue loop enabled" if state.loop_queue else "Queue loop disabled"
        await ctx.send(embed=emb.success(status))

    @commands.hybrid_command(name="shuffle", description="Shuffle the queue")
    @commands.guild_only()
    async def shuffle(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        if len(state.queue) < 2:
            return await ctx.send(embed=emb.error("Not enough tracks to shuffle."))
        import random
        queue_list = list(state.queue)
        random.shuffle(queue_list)
        state.queue = deque(queue_list)
        await ctx.send(embed=emb.success(f"🔀 Shuffled **{len(state.queue)}** tracks."))

    @commands.hybrid_command(name="remove", description="Remove a track from the queue by position")
    @app_commands.describe(position="Position in the queue (1 = first)")
    @commands.guild_only()
    async def remove(self, ctx: commands.Context, position: int) -> None:
        state = _get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send(embed=emb.error("The queue is empty."))
        if not 1 <= position <= len(state.queue):
            return await ctx.send(embed=emb.error(f"Position must be between 1 and {len(state.queue)}."))
        queue_list = list(state.queue)
        removed    = queue_list.pop(position - 1)
        state.queue = deque(queue_list)
        await ctx.send(embed=emb.success(f"Removed **{removed['title']}** from the queue."))

    @commands.hybrid_command(name="leave", aliases=["dc", "disconnect"], description="Leave the voice channel")
    @commands.guild_only()
    async def leave(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        state.clear()
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send(embed=emb.success("👋 Left the voice channel."))
        else:
            await ctx.send(embed=emb.error("I'm not in a voice channel."))

    @commands.hybrid_command(name="clearqueue", aliases=["cq"], description="Clear the music queue")
    @commands.guild_only()
    async def clearqueue(self, ctx: commands.Context) -> None:
        state = _get_state(ctx.guild.id)
        count = len(state.queue)
        state.queue.clear()
        await ctx.send(embed=emb.success(f"Cleared **{count}** tracks from the queue."))

    # ── Auto-leave on empty VC ─────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return
        state = _get_state(member.guild.id)
        if not state.vc:
            return
        # If everyone left the bot's channel — disconnect after 30s
        if (before.channel and before.channel == state.vc.channel
                and len([m for m in before.channel.members if not m.bot]) == 0):
            await asyncio.sleep(30)
            if state.vc and len([m for m in state.vc.channel.members if not m.bot]) == 0:
                state.clear()
                await state.vc.disconnect()
                log.info("Auto-disconnected from empty VC in guild %d", member.guild.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
    log.info("Music cog loaded (yt-dlp backend)")
