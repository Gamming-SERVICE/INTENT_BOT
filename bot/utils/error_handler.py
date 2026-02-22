from discord.ext import commands
import traceback
import discord

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):

        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("❌ You do not have permission to use this command.")

        if isinstance(error, commands.BotMissingPermissions):
            return await ctx.reply("❌ I do not have required permissions.")

        if isinstance(error, commands.CommandOnCooldown):
            return await ctx.reply(
                f"⏳ Command on cooldown. Try again in {round(error.retry_after, 1)}s."
            )

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply("❌ Missing required argument.")

        if isinstance(error, commands.BadArgument):
            return await ctx.reply("❌ Invalid argument provided.")

        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands silently

        # Unknown error (log but don't crash)
        print("Unexpected error:")
        traceback.print_exception(type(error), error, error.__traceback__)

        await ctx.reply("⚠️ An unexpected error occurred. The issue has been logged.")


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
