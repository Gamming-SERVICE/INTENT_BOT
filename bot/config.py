import os
from dotenv import load_dotenv

load_dotenv()  # This loads .env file

DEFAULT_PREFIX = os.getenv("DEFAULT_PREFIX", "!")

TOKEN = os.getenv("DISCORD_TOKEN")

LAVALINK_URI = os.getenv("LAVALINK_URI")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is missing in environment variables.")
