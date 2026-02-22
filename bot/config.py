import json

with open("config.json") as f:
    data = json.load(f)

TOKEN = data["token"]
OWNER_ID = data["owner_id"]
DEFAULT_PREFIX = data["default_prefix"]

LAVALINK_HOST = data["lavalink"]["host"]
LAVALINK_PORT = data["lavalink"]["port"]
LAVALINK_PASSWORD = data["lavalink"]["password"]
