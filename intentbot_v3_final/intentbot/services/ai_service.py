# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — AI Service
#                   Reads keys from environment variables only.
#                   Supports: openai, gemini, groq, mistral
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import os

import aiohttp

from core.logger import get_logger

log = get_logger("ai")

# ── Models ────────────────────────────────────────────────────────────────────

MODELS: dict[str, str] = {
    "gemini":  "gemini-1.5-flash",
    "openai":  "gpt-4o-mini",
    "groq":    "llama3-70b-8192",
    "mistral": "mistral-small-latest",
}

# ── Base URLs ─────────────────────────────────────────────────────────────────

_GEMINI_BASE  = "https://generativelanguage.googleapis.com/v1beta/models"
_OPENAI_BASE  = "https://api.openai.com/v1/chat/completions"
_GROQ_BASE    = "https://api.groq.com/openai/v1/chat/completions"
_MISTRAL_BASE = "https://api.mistral.ai/v1/chat/completions"

# ── Env var names ─────────────────────────────────────────────────────────────

_ENV_KEYS: dict[str, str] = {
    "gemini":  "GEMINI_API_KEY",
    "openai":  "OPENAI_API_KEY",
    "groq":    "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}

_DEFAULT_SYSTEM = (
    "You are Intent BOT, a helpful and concise Discord bot assistant. "
    "Use Discord markdown where appropriate. Keep replies under 1500 characters."
)

_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=8)


# ── Key resolution ─────────────────────────────────────────────────────────────

def get_api_key(provider: str) -> str:
    """
    Read the API key for a provider from environment variables.
    Raises RuntimeError with a clear message if the key is missing or empty.
    """
    env_var = _ENV_KEYS.get(provider)
    if not env_var:
        raise RuntimeError(
            f"Unknown provider '{provider}'. "
            f"Supported: {', '.join(MODELS.keys())}"
        )
    key = os.getenv(env_var, "").strip()
    if not key:
        raise RuntimeError(
            f"No API key found for '{provider}'. "
            f"Set '{env_var}' in your .env file."
        )
    return key


# ── OpenAI-compatible (OpenAI, Groq, Mistral) ─────────────────────────────────

async def _query_openai_compat(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str,
    provider_label: str,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens":  1024,
        "temperature": 0.7,
    }

    log.debug("%s request → model=%s prompt_len=%d", provider_label, model, len(prompt))

    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            raw = await resp.text()
            log.debug("%s raw response (HTTP %d): %s", provider_label, resp.status, raw[:600])

            if resp.status != 200:
                log.error("%s HTTP %d: %s", provider_label, resp.status, raw[:400])
                raise RuntimeError(
                    f"{provider_label} API returned HTTP {resp.status}.\n"
                    f"Response: {raw[:300]}"
                )

            try:
                data = await resp.json(content_type=None)
            except Exception as e:
                log.error("%s JSON parse failed: %s | raw: %s", provider_label, e, raw[:400])
                raise RuntimeError(
                    f"{provider_label} returned invalid JSON: {e}\n"
                    f"Raw preview: {raw[:200]}"
                )

    # Parse: data["choices"][0]["message"]["content"]
    choices = data.get("choices")
    if not choices or not isinstance(choices, list) or len(choices) == 0:
        log.error("%s missing 'choices'. Full response: %s", provider_label, data)
        raise RuntimeError(
            f"{provider_label} response missing 'choices'.\n"
            f"Raw keys returned: {list(data.keys())}"
        )

    first = choices[0]
    if not isinstance(first, dict):
        log.error("%s choices[0] not a dict: %s", provider_label, first)
        raise RuntimeError(f"{provider_label} response format unexpected: choices[0]={first!r}")

    message = first.get("message")
    if not message or not isinstance(message, dict):
        log.error("%s missing 'message' in choices[0]: %s", provider_label, first)
        raise RuntimeError(
            f"{provider_label} response missing 'message' in choices[0].\n"
            f"choices[0] keys: {list(first.keys())}"
        )

    content = message.get("content")
    if content is None:
        log.error("%s 'content' is None. message dict: %s", provider_label, message)
        raise RuntimeError(
            f"{provider_label} returned empty content.\n"
            f"finish_reason: {first.get('finish_reason')}"
        )

    return str(content).strip()


# ── Gemini ────────────────────────────────────────────────────────────────────

async def _query_gemini(api_key: str, prompt: str, system_prompt: str) -> str:
    model = MODELS["gemini"]
    url   = f"{_GEMINI_BASE}/{model}:generateContent?key={api_key}"

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature":     0.7,
        },
    }

    log.debug("Gemini request → model=%s prompt_len=%d", model, len(prompt))

    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        async with session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as resp:
            raw = await resp.text()
            log.debug("Gemini raw response (HTTP %d): %s", resp.status, raw[:600])

            if resp.status != 200:
                log.error("Gemini HTTP %d: %s", resp.status, raw[:400])
                raise RuntimeError(
                    f"Gemini API returned HTTP {resp.status}.\n"
                    f"Response: {raw[:300]}"
                )

            try:
                data = await resp.json(content_type=None)
            except Exception as e:
                log.error("Gemini JSON parse failed: %s | raw: %s", e, raw[:400])
                raise RuntimeError(
                    f"Gemini returned invalid JSON: {e}\n"
                    f"Raw preview: {raw[:200]}"
                )

    # Parse: data["candidates"][0]["content"]["parts"][0]["text"]
    candidates = data.get("candidates")
    if not candidates or not isinstance(candidates, list) or len(candidates) == 0:
        # Check for prompt block
        feedback = data.get("promptFeedback", {})
        block    = feedback.get("blockReason")
        if block:
            raise RuntimeError(f"Gemini blocked the prompt: blockReason={block}")
        log.error("Gemini missing 'candidates'. Full response: %s", data)
        raise RuntimeError(
            f"Gemini response missing 'candidates'.\n"
            f"Raw keys: {list(data.keys())}"
        )

    first = candidates[0]
    if not isinstance(first, dict):
        raise RuntimeError(f"Gemini candidates[0] unexpected type: {first!r}")

    # Check finish_reason for safety blocks
    finish_reason = first.get("finishReason", "")
    if finish_reason not in ("STOP", "MAX_TOKENS", ""):
        log.warning("Gemini finishReason=%s", finish_reason)
        raise RuntimeError(
            f"Gemini stopped generation: finishReason={finish_reason}.\n"
            "The prompt may have been filtered by safety settings."
        )

    content_block = first.get("content")
    if not content_block or not isinstance(content_block, dict):
        log.error("Gemini missing 'content' in candidates[0]: %s", first)
        raise RuntimeError(
            f"Gemini response missing 'content' block.\n"
            f"candidates[0] keys: {list(first.keys())}"
        )

    parts = content_block.get("parts")
    if not parts or not isinstance(parts, list) or len(parts) == 0:
        log.error("Gemini missing 'parts' in content: %s", content_block)
        raise RuntimeError("Gemini response missing 'parts' in content block.")

    text = parts[0].get("text") if isinstance(parts[0], dict) else None
    if text is None:
        log.error("Gemini parts[0] has no 'text': %s", parts[0])
        raise RuntimeError("Gemini returned empty text in parts[0].")

    return str(text).strip()


# ══════════════════════════════════════════════════════════════════════════════
# Public entry point
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
    provider    : "openai" | "gemini" | "groq" | "mistral"
    prompt      : User message
    system_prompt : Optional override. Falls back to _DEFAULT_SYSTEM.

    Returns
    -------
    str  — stripped response text

    Raises
    ------
    RuntimeError — human-readable message on any failure
    """
    provider = provider.lower().strip()

    if provider not in MODELS:
        raise RuntimeError(
            f"Unknown provider '{provider}'. "
            f"Choose: {', '.join(MODELS.keys())}"
        )

    if not prompt or not prompt.strip():
        raise RuntimeError("Prompt cannot be empty.")

    prompt        = prompt.strip()
    sys_prompt    = (system_prompt or _DEFAULT_SYSTEM).strip()

    # Resolve key — raises RuntimeError with clear message if missing
    api_key = get_api_key(provider)

    try:
        if provider == "gemini":
            result = await _query_gemini(api_key, prompt, sys_prompt)

        elif provider == "openai":
            result = await _query_openai_compat(
                _OPENAI_BASE, api_key, MODELS["openai"],
                prompt, sys_prompt, "OpenAI",
            )

        elif provider == "groq":
            result = await _query_openai_compat(
                _GROQ_BASE, api_key, MODELS["groq"],
                prompt, sys_prompt, "Groq",
            )

        elif provider == "mistral":
            result = await _query_openai_compat(
                _MISTRAL_BASE, api_key, MODELS["mistral"],
                prompt, sys_prompt, "Mistral",
            )

        else:
            raise RuntimeError(f"Unhandled provider: {provider}")

    except RuntimeError:
        raise  # pass through our own readable errors unchanged

    except asyncio.TimeoutError:
        log.error("Timeout querying %s", provider)
        raise RuntimeError(
            f"{provider} API timed out after {_TIMEOUT.total}s. "
            "Try again in a moment."
        )

    except aiohttp.ClientConnectorError as e:
        log.error("Connection error querying %s: %s", provider, e)
        raise RuntimeError(
            f"Could not connect to {provider} API: {e}. "
            "Check your internet connection."
        )

    except aiohttp.ClientError as e:
        log.error("aiohttp error querying %s: %s", provider, e)
        raise RuntimeError(f"{provider} network error: {e}")

    except Exception as e:
        log.exception("Unexpected error querying %s: %s", provider, e)
        raise RuntimeError(f"Unexpected error from {provider}: {e}")

    if not result:
        raise RuntimeError(f"{provider} returned an empty response.")

    log.info("AI ok — provider=%s response_len=%d", provider, len(result))
    return result


def list_configured_providers() -> list[str]:
    """Return providers that have an API key set in the environment."""
    return [p for p, env in _ENV_KEYS.items() if os.getenv(env, "").strip()]
ENDOFFILE
python3 -c "import ast; ast.parse(open('/home/claude/intentbot/services/ai_service.py').read()); print('ai_service.py syntax OK')"
