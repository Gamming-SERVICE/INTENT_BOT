# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — AI Chat Cog
# Supports: Gemini, OpenAI, Groq, Claude (Anthropic), Mistral
# Prefix-only version (NO slash commands)
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import aiohttp
import discord
from discord.ext import commands

from core.database import db
from core.permissions import require_admin
import core.embeds as emb
from core.logger import get_logger

log = get_logger("ai")

_PROVIDERS = ("gemini", "openai", "groq", "claude", "mistral")

_PROVIDER_MODELS = {
    "gemini": "gemini-1.5-flash-latest",
    "openai": "gpt-4o-mini",
    "groq": "llama3-8b-8192",
    "claude": "claude-3-haiku-20240307",
    "mistral": "mistral-small-latest",
}

_SYSTEM_PROMPT = (
    "You are Intent BOT, a helpful, friendly, and witty Discord bot assistant. "
    "Keep responses concise (under 1500 characters) and use Discord markdown where appropriate."
)


async def _get_token(guild_id: int, provider: str) -> str | None:
    row = await db.fetchone(
        "SELECT token FROM ai_tokens WHERE guild_id = ? AND provider = ?",
        (guild_id, provider),
    )
    return row["token"] if row else None


async def _query_gemini(token: str, prompt: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_PROVIDER_MODELS['gemini']}:generateContent?key={token}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{_SYSTEM_PROMPT}\n\nUser: {prompt}"
                    }
                ]
            }
        ]
    }

    async with aiohttp.ClientSession() as s:
        async with s.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as r:
            data = await r.json()

            return data["candidates"][0]["content"]["parts"][0]["text"]


async def _query_openai_compat(
    token: str,
    prompt: str,
    base_url: str,
    model: str,
) -> str:

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": _SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": 800,
    }

    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as r:
            data = await r.json()

            return data["choices"][0]["message"]["content"]


async def _query_claude(token: str, prompt: str) -> str:
    headers = {
        "x-api-key": token,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    payload = {
        "model": _PROVIDER_MODELS["claude"],
        "max_tokens": 800,
        "system": _SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    async with aiohttp.ClientSession() as s:
        async with s.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as r:
            data = await r.json()

            return data["content"][0]["text"]


async def _query_ai(
    guild_id: int,
    provider: str,
    prompt: str,
) -> str:

    token = await _get_token(guild_id, provider)

    if not token:
        raise ValueError(
            f"No API key configured for **{provider}**.\n"
            f"Use `!aisetkey {provider} YOUR_KEY`"
        )

    try:
        if provider == "gemini":
            return await _query_gemini(token, prompt)

        elif provider == "openai":
            return await _query_openai_compat(
                token,
                prompt,
                "https://api.openai.com/v1",
                _PROVIDER_MODELS["openai"],
            )

        elif provider == "groq":
            return await _query_openai_compat(
                token,
                prompt,
                "https://api.groq.com/openai/v1",
                _PROVIDER_MODELS["groq"],
            )

        elif provider == "claude":
            return await _query_claude(token, prompt)

        elif provider == "mistral":
            return await _query_openai_compat(
                token,
                prompt,
                "https://api.mistral.ai/v1",
                _PROVIDER_MODELS["mistral"],
            )

        else:
            raise ValueError("Unknown provider")

    except ValueError:
        raise

    except Exception as e:
        raise RuntimeError(
            f"AI API error ({provider}): {e}"
        ) from e


class AI(commands.Cog, name="AI"):
    """Multi-provider AI chat integration."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ─────────────────────────────────────────────────────────────
    # !ai
    # Usage:
    # !ai gemini hello
    # !ai openai write a poem
    # ─────────────────────────────────────────────────────────────

    @commands.command(name="ai")
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def ai_chat(
        self,
        ctx: commands.Context,
        provider: str = "gemini",
        *,
        prompt: str,
    ) -> None:

        provider = provider.lower()

        if provider not in _PROVIDERS:
            return await ctx.send(
                embed=emb.error(
                    f"Unknown provider.\n"
                    f"Available: {', '.join(_PROVIDERS)}"
                )
            )

        if len(prompt) > 1000:
            return await ctx.send(
                embed=emb.error(
                    "Prompt too long (max 1000 chars)."
                )
            )

        async with ctx.typing():

            try:
                response = await _query_ai(
                    ctx.guild.id,
                    provider,
                    prompt,
                )

            except ValueError as e:
                return await ctx.send(
                    embed=emb.error(str(e))
                )

            except RuntimeError as e:
                log.error("AI query failed: %s", e)

                return await ctx.send(
                    embed=emb.error(
                        f"AI API error:\n`{e}`"
                    )
                )

        if len(response) > 4000:
            response = response[:3990] + "…"

        embed = emb.build(
            title=f"🤖 AI Response — {provider.title()}",
            description=response,
            color=discord.Color.blurple(),
            author=ctx.author,
        )

        embed.add_field(
            name="Prompt",
            value=prompt[:200],
            inline=False,
        )

        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────────────────────
    # !aisetkey
    # ─────────────────────────────────────────────────────────────

    @commands.command(name="aisetkey")
    @require_admin()
    @commands.guild_only()
    async def ai_set_key(
        self,
        ctx: commands.Context,
        provider: str,
        *,
        key: str,
    ) -> None:

        provider = provider.lower()

        if provider not in _PROVIDERS:
            return await ctx.send(
                embed=emb.error(
                    f"Unknown provider.\n"
                    f"Available: {', '.join(_PROVIDERS)}"
                )
            )

        await db.execute(
            """
            INSERT INTO ai_tokens
            (guild_id, provider, token, added_by)

            VALUES (?,?,?,?)

            ON CONFLICT(guild_id, provider)
            DO UPDATE SET
                token = excluded.token,
                added_by = excluded.added_by
            """,
            (
                ctx.guild.id,
                provider,
                key,
                ctx.author.id,
            ),
        )

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await ctx.send(
            embed=emb.success(
                f"API key for **{provider}** saved."
            )
        )

    # ─────────────────────────────────────────────────────────────
    # !aikeys
    # ─────────────────────────────────────────────────────────────

    @commands.command(name="aikeys")
    @require_admin()
    @commands.guild_only()
    async def ai_list_keys(
        self,
        ctx: commands.Context,
    ) -> None:

        rows = await db.fetchall(
            """
            SELECT provider, added_by
            FROM ai_tokens
            WHERE guild_id = ?
            """,
            (ctx.guild.id,),
        )

        if not rows:
            return await ctx.send(
                embed=emb.info(
                    "No AI keys configured."
                )
            )

        lines = [
            f"✅ **{r['provider'].title()}** — added by <@{r['added_by']}>"
            for r in rows
        ]

        await ctx.send(
            embed=emb.build(
                title="🔑 Configured AI Providers",
                description="\n".join(lines),
                color=discord.Color.blurple(),
            )
        )

    # ─────────────────────────────────────────────────────────────
    # !airemovekey
    # ─────────────────────────────────────────────────────────────

    @commands.command(name="airemovekey")
    @require_admin()
    @commands.guild_only()
    async def ai_remove_key(
        self,
        ctx: commands.Context,
        provider: str,
    ) -> None:

        provider = provider.lower()

        await db.execute(
            """
            DELETE FROM ai_tokens
            WHERE guild_id = ?
            AND provider = ?
            """,
            (
                ctx.guild.id,
                provider,
            ),
        )

        await ctx.send(
            embed=emb.success(
                f"API key for **{provider}** removed."
            )
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AI(bot))
    log.info("AI cog loaded")
