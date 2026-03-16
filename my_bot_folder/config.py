import os

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    # Reads token from environment first (recommended for production hosts like Pterodactyl)
    # Fallback allows local quick testing, but should be replaced.
    "TOKEN": os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN") or "DISCORD_TOKEN",
    "GUILD_ID": 1429056625183948882,
    "PREFIX": "!",
    "OWNER_IDS": [],

    # Channel IDs (set via commands)
    "WELCOME_CHANNEL": None,
    "LEAVE_CHANNEL": None,
    "LOG_CHANNEL": None,
    "TICKET_CATEGORY": None,
    "LEVEL_UP_CHANNEL": None,
    "GIVEAWAY_CHANNEL": None,
    "MUSIC_VC_CHANNEL": None,  # 24/7 VC channel ID

    # Role IDs
    "MUTE_ROLE": None,
    "AUTO_ROLE": None,
    "MOD_ROLES": [],
    "ADMIN_ROLES": [],

    # Feature Toggles
    "WELCOME_ENABLED": True,
    "LEVELING_ENABLED": True,
    "ECONOMY_ENABLED": True,
    "AUTOMOD_ENABLED": True,
    "LOGGING_ENABLED": True,
    "MUSIC_ENABLED": True,

    # Auto-mod Settings
    "BANNED_WORDS": ["badword1", "badword2"],
    "ANTI_SPAM_ENABLED": True,
    "ANTI_LINK_ENABLED": False,
    "MAX_MENTIONS": 5,
    "SPAM_THRESHOLD": 5,
    "SPAM_INTERVAL": 5,

    # Economy Settings
    "CURRENCY_NAME": "coins",
    "CURRENCY_SYMBOL": "🪙",
    "DAILY_AMOUNT": 100,
    "WORK_MIN": 50,
    "WORK_MAX": 200,
    "WORK_COOLDOWN": 3600,

    # Leveling Settings
    "XP_PER_MESSAGE": (15, 25),
    "XP_COOLDOWN": 60,
    "LEVEL_UP_MESSAGE": "🎉 Congratulations {user}! You've reached level **{level}**!",

    # Lavalink Settings (for music)
    "LAVALINK_URI": "http://localhost:2333",
    "LAVALINK_PASSWORD": "youshallnotpass",

    # AI Provider API Keys
    "AI_KEYS": {
        "gemini": "",
        "openai": "",
        "groq": "",
        "claude": "",
        "mistral": "",
        "cohere": "",
        "perplexity": "",
    },
}
