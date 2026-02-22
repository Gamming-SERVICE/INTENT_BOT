from discord.ext import commands
import discord
import datetime
from utils.embeds import create_embed

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ========================
    # KICK
    # ========================
    @commands.hybrid_command()
    @commands.has_permissions(kick_members=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role:
            return await ctx.reply("❌ You cannot kick this user.")

        await member.kick(reason=reason)

        embed = create_embed(
            "👢 Member Kicked",
            color=discord.Color.orange()
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.reply(embed=embed)

    # ========================
    # BAN
    # ========================
    @commands.hybrid_command()
    @commands.has_permissions(ban_members=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):

        if member.top_role >= ctx.author.top_role:
            return await ctx.reply("❌ You cannot ban this user.")

        await member.ban(reason=reason, delete_message_days=1)

        embed = create_embed(
            "🔨 Member Banned",
            color=discord.Color.red()
        )
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.reply(embed=embed)

    # ========================
    # UNBAN
    # ========================
    @commands.hybrid_command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int):
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user)
            await ctx.reply(f"✅ Unbanned **{user.name}**")
        except discord.NotFound:
            await ctx.reply("❌ User not found in ban list.")

    # ========================
    # TIMEOUT (MUTE)
    # ========================
    @commands.hybrid_command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    async def timeout_member(self, ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):

        if member.top_role >= ctx.author.top_role:
            return await ctx.reply("❌ You cannot timeout this user.")

        until = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)

        await member.timeout(until, reason=reason)

        embed = create_embed("🔇 Member Timed Out")
        embed.add_field(name="User", value=member.mention)
        embed.add_field(name="Duration", value=f"{minutes} minutes")
        embed.add_field(name="Moderator", value=ctx.author.mention)
        embed.add_field(name="Reason", value=reason, inline=False)

        await ctx.reply(embed=embed)

    # ========================
    # CLEAR
    # ========================
    @commands.hybrid_command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        if amount > 100:
            return await ctx.reply("❌ Max 100 messages at once.")

        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"✅ Deleted {len(deleted)-1} messages.", delete_after=5)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
