from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="reload")
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx: commands.Context, cog_name: str) -> None:
        ext = f"cogs.{cog_name.lower()}"
        try:
            await self.bot.reload_extension(ext)
            await ctx.send(f"✅ Reloaded `{ext}`")
        except commands.ExtensionError as exc:
            await ctx.send(f"❌ Failed to reload `{ext}`: {exc}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
