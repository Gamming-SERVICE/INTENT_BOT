# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — AI Service
#                   Multi-provider async AI query layer
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio

import os
from typing import Any

import aiohttp

from core.logger import get_logger

log = get_logger("ai")

# ── Model identifiers ─────────────────────────────────────────────────────────

MODELS: dict[str, str] = {
    "gemini":  "gemini-1.5-flash",
    "openai":  "gpt-4o-mini",
    "groq":    "llama3-70b-8192",
    "mistral": "mistral-small-latest",
}

# ── Base URLs ─────────────────────────────────────────────────────────────────

_OPENAI_BASE  = "https://api.openai.com/v1"
_GROQ_BASE    = "https://api.groq.com/openai/v1"
_MISTRAL_BASE = "https://api.mistral.ai/v1"

# ── Request timeout (seconds) ─────────────────────────────────────────────────

_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)

# ── Default system prompt ─────────────────────────────────────────────────────

_DEFAULT_SYSTEM = (
    "You are Intent BOT, a helpful and friendly Discord bot assistant. "
    "Keep responses concise and clear. Use Discord markdown where appropriate."
)


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get_env_key(provider: str) -> str:
    """
    Return the API key for a provider from environment variables.
    Raises RuntimeError with a helpful message if the key is not set.
    """
    env_map: dict[str, str] = {
        "gemini":  "GEMINI_API_KEY",
        "openai":  "OPENAI_API_KEY",
        "groq":    "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }
    env_var = env_map.get(provider.lower())
    if not env_var:
        raise RuntimeError(
            f"Unknown AI provider: '{provider}'. "
            f"Supported: {', '.join(env_map.keys())}"
        )
    key = os.environ.get(env_var, "").strip()
    if not key:
        raise RuntimeError(
            f"API key for provider '{provider}' is not set. "
            f"Set the environment variable '{env_var}' in your .env file."
        )
    return key


def _safe_get(data: Any, *keys: str | int, default: Any = None) -> Any:
    """
    Safely traverse a nested dict/list using a sequence of keys/indexes.
    Returns `default` if any step fails instead of raising.
    """
    current = data
    for key in keys:
        try:
            if isinstance(current, dict):
                current = current.get(key, default)
            elif isinstance(current, list) and isinstance(key, int):
                current = current[key]
            else:
                return default
            if current is None:
                return default
        except (IndexError, TypeError, KeyError):
            return default
    return current


async def _post_json(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict,
    headers: dict,
) -> dict:
    """
    POST JSON to a URL and return the parsed response dict.
    Raises RuntimeError on HTTP error or non-JSON body.
    """
    async with session.post(
        url,
        json=payload,
        headers=headers,
        timeout=_TIMEOUT,
    ) as resp:
        raw_text = await resp.text()

        if resp.status != 200:
            # Try to extract error message from JSON
            try:
                import json as _json
                err_body = _json.loads(raw_text)
                # OpenAI / Groq / Mistral format
                err_msg = (
                    _safe_get(err_body, "error", "message")
                    or _safe_get(err_body, "error")
                    or raw_text[:300]
                )
                # Gemini format
                if isinstance(err_msg, dict):
                    err_msg = err_msg.get("message", str(err_msg))
            except Exception:
                err_msg = raw_text[:300]

            log.error(
                "AI API HTTP %d from %s: %s",
                resp.status,
                url,
                err_msg,
            )
            raise RuntimeError(
                f"API returned HTTP {resp.status}: {err_msg}"
            )

        try:
            return await resp.json(content_type=None)
        except Exception as parse_err:
            log.error(
                "Failed to parse AI API JSON response from %s: %s | body: %s",
                url,
                parse_err,
                raw_text[:500],
            )
            raise RuntimeError(
                f"API returned invalid JSON: {parse_err} | "
                f"Raw response preview: {raw_text[:200]}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# Provider implementations
# ══════════════════════════════════════════════════════════════════════════════

async def _ask_gemini(
    session: aiohttp.ClientSession,
    api_key: str,
    prompt: str,
    system_prompt: str,
) -> str:
    model = MODELS["gemini"]
    url   = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    # Gemini supports a system_instruction block (v1beta)
    payload: dict = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 0.7,
        },
    }
    headers = {"Content-Type": "application/json"}

    log.debug("Querying Gemini model %s", model)
    data = await _post_json(session, url, payload, headers)

    # Gemini response structure:
    # data["candidates"][0]["content"]["parts"][0]["text"]
    text = _safe_get(data, "candidates", 0, "content", "parts", 0, "text")
    if text:
        return str(text).strip()

    # Check for blocked / safety filtered response
    finish_reason = _safe_get(data, "candidates", 0, "finishReason")
    if finish_reason and finish_reason != "STOP":
        raise RuntimeError(
            f"Gemini stopped generation: finishReason={finish_reason}. "
            "The prompt may have been blocked by safety filters."
        )

    # Check for promptFeedback block
    block_reason = _safe_get(data, "promptFeedback", "blockReason")
    if block_reason:
        raise RuntimeError(
            f"Gemini blocked the prompt: blockReason={block_reason}."
        )

    log.error("Gemini returned unexpected response structure: %s", data)
    raise RuntimeError(
        "Gemini returned an unexpected response format. "
        "Check logs for the raw response."
    )


async def _ask_openai_compatible(
    session: aiohttp.ClientSession,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    system_prompt: str,
    provider_name: str,
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }

    log.debug("Querying %s model %s at %s", provider_name, model, url)
    data = await _post_json(session, url, payload, headers)

    # OpenAI / Groq / Mistral response structure:
    # data["choices"][0]["message"]["content"]
    text = _safe_get(data, "choices", 0, "message", "content")
    if text is not None:
        return str(text).strip()

    # Check finish_reason for hints
    finish_reason = _safe_get(data, "choices", 0, "finish_reason")
    if finish_reason and finish_reason not in ("stop", "length"):
        raise RuntimeError(
            f"{provider_name} stopped with finish_reason='{finish_reason}'. "
            "The response may have been filtered."
        )

    log.error("%s returned unexpected response: %s", provider_name, data)
    raise RuntimeError(
        f"{provider_name} returned an unexpected response format. "
        "Check logs for the raw response."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

async def ask_ai(
    provider: str,
    prompt: str,
    system_prompt: str | None = None,
) -> str:
    """
    Query an AI provider and return the response text.

    Parameters
    ----------
    provider : str
        One of: "gemini", "openai", "groq", "mistral"
    prompt : str
        The user's message / question.
    system_prompt : str | None
        Optional system instruction. Falls back to the default system prompt.

    Returns
    -------
    str
        The AI's response text, stripped of leading/trailing whitespace.

    Raises
    ------
    RuntimeError
        With a human-readable message if the request fails, the API key is
        missing, the provider is unknown, or the response cannot be parsed.
    """
    provider_lower = provider.lower().strip()

    if provider_lower not in MODELS:
        raise RuntimeError(
            f"Unknown provider '{provider}'. "
            f"Supported providers: {', '.join(MODELS.keys())}"
        )

    if not prompt or not prompt.strip():
        raise RuntimeError("Prompt cannot be empty.")

    prompt        = prompt.strip()
    system_prompt = (system_prompt or _DEFAULT_SYSTEM).strip()

    log.info(
        "AI request — provider=%s prompt_len=%d",
        provider_lower,
        len(prompt),
    )

    # Resolve API key (raises RuntimeError if missing)
    api_key = _get_env_key(provider_lower)

    try:
        async with aiohttp.ClientSession() as session:
            if provider_lower == "gemini":
                result = await _ask_gemini(
                    session, api_key, prompt, system_prompt
                )

            elif provider_lower == "openai":
                result = await _ask_openai_compatible(
                    session, api_key,
                    _OPENAI_BASE, MODELS["openai"],
                    prompt, system_prompt,
                    "OpenAI",
                )

            elif provider_lower == "groq":
                result = await _ask_openai_compatible(
                    session, api_key,
                    _GROQ_BASE, MODELS["groq"],
                    prompt, system_prompt,
                    "Groq",
                )

            elif provider_lower == "mistral":
                result = await _ask_openai_compatible(
                    session, api_key,
                    _MISTRAL_BASE, MODELS["mistral"],
                    prompt, system_prompt,
                    "Mistral",
                )

            else:
                # Guard — should be unreachable due to check above
                raise RuntimeError(f"Unhandled provider: {provider_lower}")

    except RuntimeError:
        # Re-raise our own errors unchanged
        raise

    except aiohttp.ClientConnectorError as e:
        log.error("Connection error querying %s: %s", provider_lower, e)
        raise RuntimeError(
            f"Could not connect to {provider_lower} API: {e}. "
            "Check your internet connection."
        )

    except aiohttp.ClientResponseError as e:
        log.error("HTTP error from %s: %s", provider_lower, e)
        raise RuntimeError(
            f"{provider_lower} API HTTP error {e.status}: {e.message}"
        )

    except aiohttp.ServerTimeoutError:
        log.error("Timeout querying %s", provider_lower)
        raise RuntimeError(
            f"{provider_lower} API timed out after {_TIMEOUT.total}s. "
            "Try again or use a different provider."
        )

    except asyncio.TimeoutError:
        log.error("asyncio timeout querying %s", provider_lower)
        raise RuntimeError(
            f"Request to {provider_lower} timed out. Try again."
        )

    except Exception as e:
        log.exception(
            "Unexpected error querying %s: %s", provider_lower, e
        )
        raise RuntimeError(
            f"Unexpected error communicating with {provider_lower}: {e}"
        )

    if not result:
        raise RuntimeError(
            f"{provider_lower} returned an empty response. "
            "Try rephrasing your prompt."
        )

    log.info(
        "AI response — provider=%s response_len=%d",
        provider_lower,
        len(result),
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Convenience wrappers (optional — used by cogs directly)
# ══════════════════════════════════════════════════════════════════════════════

async def ask_gemini(prompt: str, system_prompt: str | None = None) -> str:
    """Shortcut for ask_ai('gemini', ...)"""
    return await ask_ai("gemini", prompt, system_prompt)


async def ask_openai(prompt: str, system_prompt: str | None = None) -> str:
    """Shortcut for ask_ai('openai', ...)"""
    return await ask_ai("openai", prompt, system_prompt)


async def ask_groq(prompt: str, system_prompt: str | None = None) -> str:
    """Shortcut for ask_ai('groq', ...)"""
    return await ask_ai("groq", prompt, system_prompt)


async def ask_mistral(prompt: str, system_prompt: str | None = None) -> str:
    """Shortcut for ask_ai('mistral', ...)"""
    return await ask_ai("mistral", prompt, system_prompt)


async def list_available_providers() -> list[str]:
    """
    Return a list of providers that have an API key configured
    in the current environment.
    """
    env_map = {
        "gemini":  "GEMINI_API_KEY",
        "openai":  "OPENAI_API_KEY",
        "groq":    "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }
    return [
        p for p, env_var in env_map.items()
        if os.environ.get(env_var, "").strip()
    ]
