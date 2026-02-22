import os

DEFAULT_PREFIX = "!"

TOKEN = os.getenv("DISCORD_TOKEN")

LAVALINK_URI = os.getenv("LAVALINK_URI")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")

INTENTS = {
    "members": True,
    "message_content": True,
    "guilds": True,
}
