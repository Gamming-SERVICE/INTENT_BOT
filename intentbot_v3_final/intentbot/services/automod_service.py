# ══════════════════════════════════════════════════════════════════════════════
#                   Intent™ BOT v3.0 — AutoMod Service
#
# Centralised automod business logic and rule management.
# Used by cogs/automod.py to keep the cog thin and testable.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import discord

from core.database import db
from core.logger import get_logger
from core.settings import GuildSettings

log = get_logger("automod_service")


# ══════════════════════════════════════════════════════════════════════════════
# Types
# ══════════════════════════════════════════════════════════════════════════════

class AutoModAction(Enum):
    DELETE    = auto()
    WARN      = auto()
    MUTE      = auto()
    KICK      = auto()
    BAN       = auto()


class ViolationType(Enum):
    BANNED_WORD     = "banned_word"
    SPAM            = "spam"
    LINK            = "link"
    INVITE          = "invite"
    MASS_MENTION    = "mass_mention"
    ZALGO           = "zalgo"
    REPEAT_CHARS    = "repeat_chars"
    EXCESSIVE_CAPS  = "excessive_caps"
    CUSTOM_RULE     = "custom_rule"


@dataclass
class ViolationResult:
    """Returned by check_message() when a rule fires."""
    triggered:      bool
    violation_type: ViolationType | None = None
    detail:         str                  = ""
    action:         AutoModAction        = AutoModAction.DELETE
    matched_value:  str                  = ""


# ══════════════════════════════════════════════════════════════════════════════
# In-memory state (per-process, resets on restart — acceptable for automod)
# ══════════════════════════════════════════════════════════════════════════════

# guild_id → user_id → deque[float]  (message timestamps for spam detection)
_spam_buckets: dict[int, dict[int, deque[float]]] = defaultdict(
    lambda: defaultdict(deque)
)

# guild_id → deque[float]  (join timestamps for raid detection)
_join_buckets: dict[int, deque[float]] = defaultdict(deque)


# ══════════════════════════════════════════════════════════════════════════════
# Compiled regex patterns
# ══════════════════════════════════════════════════════════════════════════════

_URL_RE     = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_INVITE_RE  = re.compile(r"discord(?:\.gg|(?:app)?\.com/invite)/\S+", re.IGNORECASE)
_ZALGO_RE   = re.compile(r"[\u0300-\u036f\u0489]{4,}")
_REPEAT_RE  = re.compile(r"(.)\1{9,}")

_CAPS_RATIO     = 0.70   # 70 % uppercase triggers the caps filter
_CAPS_MIN_LEN   = 15     # only check messages at least this many chars long
_RAID_WINDOW    = 10     # seconds to look back for raid detection
_RAID_THRESHOLD = 10     # joins in _RAID_WINDOW seconds to trigger raid alert


# ══════════════════════════════════════════════════════════════════════════════
# Core message checker
# ══════════════════════════════════════════════════════════════════════════════

async def check_message(message: discord.Message) -> ViolationResult:
    """
    Run all enabled automod rules against a message.

    Returns a ViolationResult with triggered=False if nothing fired,
    or triggered=True with details of the first rule that matched.

    This function never raises — all exceptions are caught and logged.
    """
    _clean = ViolationResult(triggered=False)

    try:
        if not message.guild:
            return _clean
        if message.author.bot:
            return _clean

        member = message.author
        # Never automod administrators or users with manage_messages
        if (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_messages
        ):
            return _clean

        gs = await GuildSettings.fetch(message.guild.id)
        if not gs.automod_enabled:
            return _clean

        content       = message.content or ""
        content_lower = content.lower()

        # ── 1. Banned words ────────────────────────────────────────────────────
        for word in gs.banned_words:
            if word and word in content_lower:
                log.debug(
                    "AutoMod BANNED_WORD: guild=%d user=%d word=%s",
                    message.guild.id, member.id, word,
                )
                return ViolationResult(
                    triggered=True,
                    violation_type=ViolationType.BANNED_WORD,
                    detail=f"Matched banned word: `{word}`",
                    action=AutoModAction.DELETE,
                    matched_value=word,
                )

        # ── 2. Anti-spam ───────────────────────────────────────────────────────
        if gs.anti_spam_enabled:
            result = _check_spam(
                guild_id=message.guild.id,
                user_id=member.id,
                threshold=gs.spam_threshold,
                window=gs.spam_interval,
            )
            if result:
                log.debug(
                    "AutoMod SPAM: guild=%d user=%d threshold=%d window=%d",
                    message.guild.id, member.id, gs.spam_threshold, gs.spam_interval,
                )
                return ViolationResult(
                    triggered=True,
                    violation_type=ViolationType.SPAM,
                    detail=f"{gs.spam_threshold} messages in {gs.spam_interval}s",
                    action=AutoModAction.DELETE,
                )

        # ── 3. Invite links ────────────────────────────────────────────────────
        if gs.anti_link_enabled:
            invite_match = _INVITE_RE.search(content)
            if invite_match:
                return ViolationResult(
                    triggered=True,
                    violation_type=ViolationType.INVITE,
                    detail="Discord invite link detected",
                    action=AutoModAction.DELETE,
                    matched_value=invite_match.group(0)[:100],
                )

            url_match = _URL_RE.search(content)
            if url_match:
                return ViolationResult(
                    triggered=True,
                    violation_type=ViolationType.LINK,
                    detail="External URL detected",
                    action=AutoModAction.DELETE,
                    matched_value=url_match.group(0)[:100],
                )

        # ── 4. Mass mentions ───────────────────────────────────────────────────
        real_mentions = [m for m in message.mentions if not m.bot]
        if len(real_mentions) > gs.max_mentions:
            return ViolationResult(
                triggered=True,
                violation_type=ViolationType.MASS_MENTION,
                detail=f"{len(real_mentions)} mentions (max {gs.max_mentions})",
                action=AutoModAction.DELETE,
            )

        # ── 5. Zalgo text ──────────────────────────────────────────────────────
        if _ZALGO_RE.search(content):
            return ViolationResult(
                triggered=True,
                violation_type=ViolationType.ZALGO,
                detail="Zalgo / combining-character text detected",
                action=AutoModAction.DELETE,
            )

        # ── 6. Repeated characters ─────────────────────────────────────────────
        repeat_match = _REPEAT_RE.search(content)
        if repeat_match:
            return ViolationResult(
                triggered=True,
                violation_type=ViolationType.REPEAT_CHARS,
                detail=f"10+ repeated '{repeat_match.group(1)}' characters",
                action=AutoModAction.DELETE,
            )

        # ── 7. Excessive caps ──────────────────────────────────────────────────
        if len(content) >= _CAPS_MIN_LEN:
            alpha = [c for c in content if c.isalpha()]
            if alpha:
                caps_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
                if caps_ratio >= _CAPS_RATIO:
                    return ViolationResult(
                        triggered=True,
                        violation_type=ViolationType.EXCESSIVE_CAPS,
                        detail=f"{int(caps_ratio * 100)}% uppercase",
                        action=AutoModAction.DELETE,
                    )

        # ── 8. Custom DB rules ─────────────────────────────────────────────────
        custom_result = await _check_custom_rules(
            message.guild.id, content, content_lower
        )
        if custom_result.triggered:
            return custom_result

    except Exception as e:
        log.exception(
            "AutoMod check_message error in guild %s: %s",
            getattr(message.guild, "id", "?"),
            e,
        )

    return _clean


# ══════════════════════════════════════════════════════════════════════════════
# Spam detection
# ══════════════════════════════════════════════════════════════════════════════

def _check_spam(
    guild_id: int,
    user_id: int,
    threshold: int,
    window: int,
) -> bool:
    """
    Return True if the user has sent >= threshold messages within `window` seconds.
    Updates the in-memory bucket as a side effect.
    """
    now    = time.monotonic()
    bucket = _spam_buckets[guild_id][user_id]
    bucket.append(now)

    # Evict timestamps outside the window
    while bucket and now - bucket[0] > window:
        bucket.popleft()

    if len(bucket) >= threshold:
        bucket.clear()
        return True
    return False


def clear_spam_bucket(guild_id: int, user_id: int) -> None:
    """Manually clear a user's spam bucket (e.g. after a manual mute)."""
    _spam_buckets[guild_id].pop(user_id, None)


# ══════════════════════════════════════════════════════════════════════════════
# Raid detection
# ══════════════════════════════════════════════════════════════════════════════

def check_join_raid(guild_id: int) -> bool:
    """
    Register a join event and return True if a raid threshold is crossed.
    Call from on_member_join.
    """
    now    = time.monotonic()
    bucket = _join_buckets[guild_id]
    bucket.append(now)

    while bucket and now - bucket[0] > _RAID_WINDOW:
        bucket.popleft()

    if len(bucket) >= _RAID_THRESHOLD:
        bucket.clear()
        log.warning(
            "Raid detected in guild %d — %d joins in %ds",
            guild_id, _RAID_THRESHOLD, _RAID_WINDOW,
        )
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Custom DB-backed rules
# ══════════════════════════════════════════════════════════════════════════════

async def _check_custom_rules(
    guild_id: int,
    content: str,
    content_lower: str,
) -> ViolationResult:
    """Check message against custom rules stored in the automod_rules table."""
    try:
        rules = await db.fetchall(
            "SELECT rule_type, value, action FROM automod_rules WHERE guild_id = ?",
            (guild_id,),
        )
    except Exception as e:
        log.warning("Failed to fetch custom automod rules for guild %d: %s", guild_id, e)
        return ViolationResult(triggered=False)

    for rule in rules:
        rule_type = rule.get("rule_type", "")
        value     = rule.get("value", "")
        action    = _parse_action(rule.get("action", "delete"))

        if not value:
            continue

        matched = False
        detail  = ""

        if rule_type == "word":
            if value.lower() in content_lower:
                matched = True
                detail  = f"Custom banned word: `{value}`"

        elif rule_type == "regex":
            try:
                if re.search(value, content, re.IGNORECASE):
                    matched = True
                    detail  = f"Custom regex match: `{value[:50]}`"
            except re.error:
                log.warning("Invalid custom regex in guild %d: %s", guild_id, value)

        elif rule_type == "substring":
            if value.lower() in content_lower:
                matched = True
                detail  = f"Custom substring: `{value}`"

        if matched:
            return ViolationResult(
                triggered=True,
                violation_type=ViolationType.CUSTOM_RULE,
                detail=detail,
                action=action,
                matched_value=value,
            )

    return ViolationResult(triggered=False)


def _parse_action(action_str: str) -> AutoModAction:
    mapping = {
        "delete": AutoModAction.DELETE,
        "warn":   AutoModAction.WARN,
        "mute":   AutoModAction.MUTE,
        "kick":   AutoModAction.KICK,
        "ban":    AutoModAction.BAN,
    }
    return mapping.get(action_str.lower(), AutoModAction.DELETE)


# ══════════════════════════════════════════════════════════════════════════════
# Custom rule management (admin API)
# ══════════════════════════════════════════════════════════════════════════════

async def add_rule(
    guild_id: int,
    rule_type: str,
    value: str,
    action: str,
    created_by: int,
) -> int:
    """
    Add a custom automod rule. Returns the new rule's ID.
    rule_type: "word" | "regex" | "substring"
    action:    "delete" | "warn" | "mute" | "kick" | "ban"
    """
    valid_types   = {"word", "regex", "substring"}
    valid_actions = {"delete", "warn", "mute", "kick", "ban"}

    if rule_type not in valid_types:
        raise ValueError(f"Invalid rule_type '{rule_type}'. Choose: {valid_types}")
    if action not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Choose: {valid_actions}")
    if not value or not value.strip():
        raise ValueError("Rule value cannot be empty.")
    if rule_type == "regex":
        try:
            re.compile(value)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

    rule_id = await db.execute_returning_id(
        "INSERT INTO automod_rules (guild_id, rule_type, value, action, created_by) "
        "VALUES (?,?,?,?,?)",
        (guild_id, rule_type, value.strip(), action, created_by),
    )
    log.info(
        "Custom automod rule added: guild=%d id=%d type=%s action=%s",
        guild_id, rule_id, rule_type, action,
    )
    return rule_id


async def remove_rule(guild_id: int, rule_id: int) -> bool:
    """
    Remove a custom automod rule by ID.
    Returns True if a rule was deleted, False if not found.
    """
    existing = await db.fetchone(
        "SELECT id FROM automod_rules WHERE id = ? AND guild_id = ?",
        (rule_id, guild_id),
    )
    if not existing:
        return False
    await db.execute(
        "DELETE FROM automod_rules WHERE id = ? AND guild_id = ?",
        (rule_id, guild_id),
    )
    log.info("Custom automod rule removed: guild=%d id=%d", guild_id, rule_id)
    return True


async def list_rules(guild_id: int) -> list[dict]:
    """Return all custom automod rules for a guild."""
    return await db.fetchall(
        "SELECT id, rule_type, value, action, created_by, created_at "
        "FROM automod_rules WHERE guild_id = ? ORDER BY id ASC",
        (guild_id,),
    )


async def clear_rules(guild_id: int) -> int:
    """Delete all custom automod rules for a guild. Returns count deleted."""
    rows = await db.fetchall(
        "SELECT COUNT(*) AS c FROM automod_rules WHERE guild_id = ?",
        (guild_id,),
    )
    count = rows[0]["c"] if rows else 0
    await db.execute("DELETE FROM automod_rules WHERE guild_id = ?", (guild_id,))
    log.info("Cleared %d custom automod rules for guild %d", count, guild_id)
    return count


# ══════════════════════════════════════════════════════════════════════════════
# Violation logging helper
# ══════════════════════════════════════════════════════════════════════════════

async def log_violation(
    guild: discord.Guild,
    message: discord.Message,
    result: ViolationResult,
) -> None:
    """
    Send an automod violation embed to the guild's log channel.
    Fetches the log channel from GuildSettings — does nothing if not configured.
    """
    try:
        gs = await GuildSettings.fetch(guild.id)
        if not gs.logging_enabled or not gs.log_channel:
            return
        channel = guild.get_channel(gs.log_channel)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        import core.embeds as emb
        violation_name = (
            result.violation_type.value.replace("_", " ").title()
            if result.violation_type
            else "Unknown"
        )
        embed = emb.build(
            title=f"🛡️ AutoMod — {violation_name}",
            color=discord.Color.orange(),
            fields=[
                ("User",    f"{message.author.mention} (`{message.author}`, ID: {message.author.id})", True),
                ("Channel", message.channel.mention,                                                    True),
                ("Action",  result.action.name.title(),                                                 True),
                ("Detail",  result.detail or "N/A",                                                    True),
                ("Content", (message.content[:500] if message.content else "*empty*"),                 False),
            ],
        )
        await channel.send(embed=embed)

    except Exception as e:
        log.warning("Failed to log automod violation: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# Statistics helpers
# ══════════════════════════════════════════════════════════════════════════════

async def get_violation_stats(guild_id: int, days: int = 7) -> dict[str, int]:
    """
    Return a count of each violation type logged to analytics in the past N days.
    Uses the analytics_events table if populated; returns empty dict otherwise.
    """
    import datetime
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
    try:
        rows = await db.fetchall(
            "SELECT event_type, COUNT(*) AS c FROM analytics_events "
            "WHERE guild_id = ? AND event_type LIKE 'automod_%' AND created_at >= ? "
            "GROUP BY event_type",
            (guild_id, cutoff),
        )
        return {r["event_type"]: r["c"] for r in rows}
    except Exception:
        return {}
