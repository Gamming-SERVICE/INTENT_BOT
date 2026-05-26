# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — AI Cog
#                   PREFIX-ONLY | discord.py 2.7.1
#
# Commands:
#   !ai <provider> <prompt>      — query AI
#   !aiproviders                 — list providers and which have keys set
#   !aisetkey <provider> <key>   — store per-guild key in DB (admin)
#   !aikeys                      — list per-guild configured keys (admin)
#   !airemovekey <provider>      — remove a per-guild DB key (admin)
#
# Key resolution order:
#   1. Guild DB key (stored via !aisetkey)
#   2. Environment variable (GEMINI_API_KEY etc.)
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os

import discord
from discord.ext import commands

from core.database import db
from core.permissions import require_admin
import core.embeds as emb
from core.logger import get_logger
from services.ai_service import ask_ai, MODELS, _ENV_KEYS, list_configured_providers

log = get_logger("ai_cog")

_PROVIDERS = tuple(MODELS.keys())   # ("gemini", "openai", "groq", "mistral")


async def _resolve_key(guild_id: int, provider: str) -> str | None:
    """
    Try to find an API key for a provider.
    Checks guild DB first, then falls back to environment variable.
    Returns the key string or None if not found.
    """
    # 1. Guild-specific key from DB
    row = await db.fetchone(
        "SELECT token FROM ai_tokens WHERE guild_id = ? AND provider = ?",
        (guild_id, provider),
    )
    if row and row["token"].strip():
        return row["token"].strip()

    # 2. Environment variable
    env_var = _ENV_KEYS.get(provider, "")
    env_key = os.getenv(env_var, "").strip() if env_var else ""
    return env_key or None


class AI(commands.Cog, name="AI"):
    """Multi-provider AI chat commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── !ai ───────────────────────────────────────────────────────────────────

    @commands.command(name="ai", aliases=["ask", "chat"])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def ai_chat(self, ctx: commands.Context, provider: str, *, prompt: str) -> None:
        """Query an AI provider.
        Usage: !ai <provider> <prompt>
        Examples:
          !ai openai What is Python?
          !ai gemini Tell me a joke
          !ai groq Explain async/await
          !ai mistral Write a haiku about coding
        Providers: openai, gemini, groq, mistral"""

        provider = provider.lower().strip()

        if provider not in _PROVIDERS:
            # First word wasn't a provider — treat everything as prompt with default
            prompt   = f"{provider} {prompt}"
            provider = "gemini"

        if len(prompt) > 1000:
            return await ctx.send(
                embed=emb.error("Prompt too long. Maximum 1000 characters.")
            )

        # Resolve the API key (DB first, then env)
        api_key = await _resolve_key(ctx.guild.id, provider)
        if not api_key:
            env_var = _ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
            return await ctx.send(
                embed=emb.error(
                    f"No API key configured for **{provider}**.\n\n"
                    f"**Option 1 — Environment variable:** "
                    f"Add `{env_var}=your_key` to your `.env` file.\n\n"
                    f"**Option 2 — Per-server key:** "
                    f"Run `!aisetkey {provider} your_key` (admin only)."
                )
            )

        # Temporarily set env var so ai_service.get_api_key() finds it
        # (handles both DB-sourced and env-sourced keys transparently)
        env_var       = _ENV_KEYS.get(provider, "")
        original_val  = os.environ.get(env_var)
        os.environ[env_var] = api_key

        async with ctx.typing():
            try:
                response = await ask_ai(provider, prompt)
            except RuntimeError as e:
                log.warning("AI request failed — provider=%s error=%s", provider, e)
                return await ctx.send(
                    embed=emb.error(
                        f"**{provider.title()} API error:**\n{e}"
                    )
                )
            finally:
                # Restore original env state
                if original_val is None:
                    os.environ.pop(env_var, None)
                else:
                    os.environ[env_var] = original_val

        # Truncate if over Discord embed limit
        if len(response) > 4000:
            response = response[:3990] + "\n…*(truncated)*"

        embed = emb.build(
            title=f"🤖 {provider.title()} Response",
            description=response,
            color=discord.Color.blurple(),
            author=ctx.author,
        )
        embed.add_field(name="Prompt", value=prompt[:200], inline=False)
        embed.set_footer(text=f"Model: {MODELS[provider]} • Intent BOT")
        await ctx.send(embed=embed)

    # ── !aiproviders ──────────────────────────────────────────────────────────

    @commands.command(name="aiproviders")
    async def ai_providers(self, ctx: commands.Context) -> None:
        """List all AI providers and their key status.
        Usage: !aiproviders"""
        lines = []
        for p, model in MODELS.items():
            env_var = _ENV_KEYS.get(p, "")
            has_env = bool(os.getenv(env_var, "").strip())

            has_db = False
            if ctx.guild:
                row = await db.fetchone(
                    "SELECT token FROM ai_tokens WHERE guild_id = ? AND provider = ?",
                    (ctx.guild.id, p),
                )
                has_db = bool(row and row["token"].strip())

            if has_db:
                status = "✅ Server key set"
            elif has_env:
                status = "✅ Env key set"
            else:
                status = f"❌ No key — set `{env_var}`"

            lines.append(f"**{p}** (`{model}`)\n  {status}")

        prefix = "!"
        if ctx.guild:
            try:
                from core.settings import GuildSettings
                gs     = await GuildSettings.fetch(ctx.guild.id)
                prefix = gs.prefix
            except Exception:
                pass

        await ctx.send(embed=emb.build(
            title="🤖 AI Providers",
            description="\n\n".join(lines),
            color=discord.Color.blurple(),
            fields=[(
                "Usage",
                f"`{prefix}ai <provider> <prompt>`\nExample: `{prefix}ai openai Hello!`",
                False,
            )],
        ))

    # ── !aisetkey ─────────────────────────────────────────────────────────────

    @commands.command(name="aisetkey")
    @require_admin()
    @commands.guild_only()
    async def ai_set_key(self, ctx: commands.Context, provider: str, *, key: str) -> None:
        """Store a per-server AI API key in the database.
        Usage: !aisetkey <provider> <your_api_key>
        Providers: openai, gemini, groq, mistral
        The key is stored encrypted to your server — not shared globally."""
        provider = provider.lower().strip()
        if provider not in _PROVIDERS:
            return await ctx.send(
                embed=emb.error(
                    f"Unknown provider `{provider}`.\n"
                    f"Choose: {', '.join(f'`{p}`' for p in _PROVIDERS)}"
                )
            )
        key = key.strip()
        if not key:
            return await ctx.send(embed=emb.error("API key cannot be empty."))

        await db.execute(
            "INSERT INTO ai_tokens (guild_id, provider, token, added_by) VALUES (?,?,?,?) "
            "ON CONFLICT(guild_id, provider) DO UPDATE SET "
            "token = excluded.token, added_by = excluded.added_by",
            (ctx.guild.id, provider, key, ctx.author.id),
        )

        # Delete the command message to hide the key from chat
        try:
            await ctx.message.delete()
        except Exception:
            pass

        await ctx.send(
            embed=emb.success(
                f"✅ API key for **{provider}** saved for this server.\n"
                "The message containing your key has been deleted."
            ),
            delete_after=15,
        )
        log.info("AI key set: guild=%d provider=%s by=%d", ctx.guild.id, provider, ctx.author.id)

    # ── !aikeys ───────────────────────────────────────────────────────────────

    @commands.command(name="aikeys")
    @require_admin()
    @commands.guild_only()
    async def ai_list_keys(self, ctx: commands.Context) -> None:
        """List which AI providers have per-server keys stored.
        Usage: !aikeys"""
        rows = await db.fetchall(
            "SELECT provider, added_by FROM ai_tokens WHERE guild_id = ?",
            (ctx.guild.id,),
        )
        if not rows:
            prefix = "!"
            try:
                from core.settings import GuildSettings
                gs     = await GuildSettings.fetch(ctx.guild.id)
                prefix = gs.prefix
            except Exception:
                pass
            return await ctx.send(embed=emb.info(
                f"No per-server AI keys configured.\n"
                f"Use `{prefix}aisetkey <provider> <key>` to add one,\n"
                f"or set environment variables in `.env`."
            ))

        lines = [
            f"✅ **{r['provider']}** — added by <@{r['added_by']}>"
            for r in rows
        ]
        try:
            await ctx.author.send(embed=emb.build(
                title="🔑 Per-Server AI Keys",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            ))
            await ctx.send(
                embed=emb.success("AI key list sent to your DMs."),
                delete_after=8,
            )
        except discord.HTTPException:
            await ctx.send(embed=emb.build(
                title="🔑 Per-Server AI Keys",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            ))

    # ── !airemovekey ──────────────────────────────────────────────────────────

    @commands.command(name="airemovekey")
    @require_admin()
    @commands.guild_only()
    async def ai_remove_key(self, ctx: commands.Context, provider: str) -> None:
        """Remove a per-server AI API key.
        Usage: !airemovekey <provider>"""
        provider = provider.lower().strip()
        if provider not in _PROVIDERS:
            return await ctx.send(
                embed=emb.error(
                    f"Unknown provider `{provider}`.\n"
                    f"Choose: {', '.join(f'`{p}`' for p in _PROVIDERS)}"
                )
            )
        existing = await db.fetchone(
            "SELECT provider FROM ai_tokens WHERE guild_id = ? AND provider = ?",
            (ctx.guild.id, provider),
        )
        if not existing:
            return await ctx.send(
                embed=emb.warning(f"No per-server key found for **{provider}**.")
            )
        await db.execute(
            "DELETE FROM ai_tokens WHERE guild_id = ? AND provider = ?",
            (ctx.guild.id, provider),
        )
        await ctx.send(embed=emb.success(f"API key for **{provider}** removed."))
        log.info("AI key removed: guild=%d provider=%s by=%d", ctx.guild.id, provider, ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AI(bot))
    log.info("AI cog loaded")
