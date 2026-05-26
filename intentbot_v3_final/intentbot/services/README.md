# Intent™ BOT v3.0 — Services Layer

The `/services` folder contains the **business logic layer** — pure async Python modules that are imported by cogs but contain no Discord command handling themselves. This separation keeps cogs thin and the logic independently testable.

---

## Files

### `ai_service.py`

Multi-provider async AI query engine.

**Public API:**
```python
from services.ai_service import ask_ai, list_available_providers

# Query any supported provider
response = await ask_ai("gemini", "What is Python?")
response = await ask_ai("openai", "Explain async/await", system_prompt="Be concise.")

# Convenience wrappers
from services.ai_service import ask_gemini, ask_openai, ask_groq, ask_mistral
response = await ask_gemini("Hello!")

# Check which providers have keys configured
available = await list_available_providers()
# returns e.g. ["gemini", "groq"]
```

**Supported providers:**

| Provider | Model | Env Variable |
|----------|-------|-------------|
| `gemini` | `gemini-1.5-flash` | `GEMINI_API_KEY` |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `groq` | `llama3-70b-8192` | `GROQ_API_KEY` |
| `mistral` | `mistral-small-latest` | `MISTRAL_API_KEY` |

**Error handling:**
- Raises `RuntimeError` with a human-readable message on any failure
- Never crashes silently — all exceptions are caught, logged, and re-raised
- Timeout protection: 30s total, 10s connect

**Configuration** (`.env`):
```env
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
MISTRAL_API_KEY=...
```

---

### `economy_service.py`

All economy mutations in one place. Ensures consistent balance handling across cogs.

**Public API:**
```python
from services.economy_service import (
    ensure_user,
    get_balance,
    add_wallet,
    transfer,
    deposit,
    withdraw,
    get_leaderboard,
    reset_user,
    add_item,
    remove_item,
    get_inventory,
)

# Ensure user row exists before any operation
row = await ensure_user(user_id, guild_id)

# Add/subtract from wallet (never goes negative)
new_bal = await add_wallet(user_id, guild_id, 100, txn_type="daily")

# Atomic transfer between two users (raises ValueError on insufficient funds)
sender_bal, receiver_bal = await transfer(sender_id, receiver_id, guild_id, 500)

# Deposit wallet → bank
wallet, bank = await deposit(user_id, guild_id, 200)

# Withdraw bank → wallet
wallet, bank = await withdraw(user_id, guild_id, 100)

# Get top 10 by total wealth
leaderboard = await get_leaderboard(guild_id, limit=10)

# Inventory management
await add_item(user_id, guild_id, item_id=5, quantity=2)
success = await remove_item(user_id, guild_id, item_id=5, quantity=1)
inventory = await get_inventory(user_id, guild_id)
```

**Key guarantees:**
- All balance mutations are atomic (use `db.transaction()` where needed)
- `add_wallet` clamps at zero — wallets can never go negative
- `transfer` is race-condition safe via `BEGIN IMMEDIATE` transaction
- All mutations write audit records to `economy_transactions` table

---

### `automod_service.py`

Automod rule evaluation engine with in-memory state tracking.

**Public API:**
```python
from services.automod_service import (
    check_message,
    check_join_raid,
    clear_spam_bucket,
    add_rule,
    remove_rule,
    list_rules,
    clear_rules,
    log_violation,
    get_violation_stats,
)

# Check a Discord message against all rules
result = await check_message(message)
if result.triggered:
    # result.violation_type  — ViolationType enum
    # result.detail          — human-readable explanation
    # result.action          — AutoModAction (DELETE, WARN, MUTE, ...)
    # result.matched_value   — what triggered the rule
    await log_violation(message.guild, message, result)

# Raid detection (call on every member join)
is_raid = check_join_raid(guild_id)

# Custom rule management
rule_id = await add_rule(guild_id, "word", "badword", "delete", ctx.author.id)
rule_id = await add_rule(guild_id, "regex", r"\bscam\b", "warn", ctx.author.id)
await remove_rule(guild_id, rule_id)
rules = await list_rules(guild_id)
```

**Built-in checks (in priority order):**
1. Banned words (from `guild_settings.banned_words`)
2. Anti-spam (configurable threshold/window)
3. Discord invite links
4. External URLs
5. Mass mentions
6. Zalgo / combining-character text
7. Repeated characters (10+ in a row)
8. Excessive caps (≥70% uppercase, minimum 15 chars)
9. Custom DB-backed rules (word, regex, substring)

---

### `updater_service.py`

Automatic bot update system.

**How it works:**
1. Every 60 minutes, fetches `UPDATE_CHECK_URL`
2. Parses `version=X.Y.Z` and `zip=https://...` from the page body
3. Compares to `BOT_VERSION` in `core/constants.py`
4. If newer: downloads the ZIP, creates a backup, applies the update, restarts
5. Preserved files (never overwritten): `data/database.db`, `.env`, `logs/`, `data/backups/`, `config.py`

**Update server page format** (host this at your `UPDATE_CHECK_URL`):
```html
<body>
version=3.0.1
zip=https://github.com/youruser/intentbot/archive/refs/heads/main.zip
</body>
```

**Configuration** (`.env`):
```env
UPDATE_CHECK_URL=https://update.bot.int.yt
```

**Rollback:** If the update fails at any point, the backup in `data/backups/` can be manually restored.

---

## Architecture Notes

```
cogs/          ← Discord command handling only, thin
services/      ← Business logic, no Discord imports except types
core/          ← Infrastructure (DB, cache, settings, logging)
```

Cogs should import from services for complex logic:
```python
# In a cog:
from services.economy_service import add_wallet, transfer
from services.ai_service import ask_ai
from services.automod_service import check_message, log_violation
```

Services should only import from `core/` — never from `cogs/` or other services.
