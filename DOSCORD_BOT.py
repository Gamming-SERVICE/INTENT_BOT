# ══════════════════════════════════════════════════════════════════════════════
# ULTIMATE DISCORD BOT v2.0 - PRODUCTION READY
# Features: Moderation, Leveling, Economy, Tickets (Button Panel), Giveaways,
#           Auto-mod, Logging, Welcome/Leave, Reaction Roles, Color Roles,
#           Fun, Utility, Music (24/7 VC), AI Integration, Waifu, 
#           Dynamic Marketplace with Trading, and more!
# ══════════════════════════════════════════════════════════════════════════════

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiosqlite
import aiohttp
import datetime
import random
import json
import re
import os
import math
from typing import Optional, Literal
from collections import defaultdict
import time
import traceback

try:
    import wavelink
    WAVELINK_AVAILABLE = True
except ImportError:
    WAVELINK_AVAILABLE = False
    print("⚠️ wavelink not installed - music features disabled. Install with: pip install wavelink")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    "TOKEN": "DISCORD_TOKEN",  # REPLACE THIS
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

    # AI Provider API Keys (set via !ai set <provider> <key> or put here)
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

# ══════════════════════════════════════════════════════════════════════════════
# BOT SETUP
# ══════════════════════════════════════════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=CONFIG["PREFIX"], intents=intents, help_command=None)
bot.config = CONFIG

# In-memory caches
spam_tracker = defaultdict(list)
xp_cooldowns = {}
active_giveaways = {}
reaction_roles = {}
custom_commands = {}
warnings_cache = {}
afk_users = {}

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE SETUP + MIGRATION (SAFE - NEVER DROPS DATA)
# ══════════════════════════════════════════════════════════════════════════════

async def init_database():
    async with aiosqlite.connect("bot_database.db") as db:
        # Original tables (unchanged)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                balance INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                daily_claimed TEXT,
                work_claimed TEXT,
                inventory TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                user_id INTEGER,
                guild_id INTEGER,
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_commands (
                name TEXT PRIMARY KEY,
                guild_id INTEGER,
                response TEXT,
                created_by INTEGER,
                uses INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                guild_id INTEGER,
                PRIMARY KEY (message_id, emoji)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                channel_id INTEGER,
                guild_id INTEGER,
                prize TEXT,
                winners INTEGER,
                host_id INTEGER,
                end_time TEXT,
                ended INTEGER DEFAULT 0,
                participants TEXT DEFAULT '[]'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_id INTEGER,
                reminder TEXT,
                remind_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER PRIMARY KEY,
                welcome_channel INTEGER,
                leave_channel INTEGER,
                log_channel INTEGER,
                mute_role INTEGER,
                auto_role INTEGER,
                welcome_message TEXT,
                leave_message TEXT,
                settings TEXT DEFAULT '{}'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                action TEXT,
                reason TEXT,
                duration TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                name TEXT,
                description TEXT,
                price INTEGER,
                role_id INTEGER,
                stock INTEGER DEFAULT -1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ═══════════════════════════════════════════
        # NEW TABLES (v2.0 migration - safe to run)
        # ═══════════════════════════════════════════

        # Market items master catalog
        await db.execute("""
            CREATE TABLE IF NOT EXISTS market_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                category TEXT DEFAULT 'misc',
                description TEXT DEFAULT '',
                emoji TEXT DEFAULT '📦',
                base_price INTEGER DEFAULT 100,
                current_price REAL DEFAULT 100.0,
                total_bought INTEGER DEFAULT 0,
                total_sold INTEGER DEFAULT 0,
                rarity TEXT DEFAULT 'common',
                tradeable INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User market inventory (row-based, better for trading)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                item_id INTEGER,
                quantity INTEGER DEFAULT 1,
                acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, guild_id, item_id)
            )
        """)

        # Trades
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                sender_id INTEGER,
                receiver_id INTEGER,
                item_id INTEGER,
                quantity INTEGER DEFAULT 1,
                price INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
        """)

        # AI tokens storage
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_tokens (
                guild_id INTEGER,
                provider TEXT,
                token TEXT,
                added_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, provider)
            )
        """)

        # Color roles for button panel
        await db.execute("""
            CREATE TABLE IF NOT EXISTS color_roles (
                guild_id INTEGER,
                role_id INTEGER,
                label TEXT,
                emoji TEXT DEFAULT '🎨',
                style INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, role_id)
            )
        """)

        # Music queue persistence (optional)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS music_settings (
                guild_id INTEGER PRIMARY KEY,
                vc_channel_id INTEGER,
                volume INTEGER DEFAULT 50,
                loop_mode TEXT DEFAULT 'off',
                dj_role_id INTEGER
            )
        """)

        # Waifu collection
        await db.execute("""
            CREATE TABLE IF NOT EXISTS waifu_collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                waifu_name TEXT,
                waifu_url TEXT,
                waifu_type TEXT,
                rarity TEXT DEFAULT 'common',
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
        print("✅ Database initialized and migrated successfully!")


async def seed_market_items():
    """Seed the market with items if empty. Safe to call multiple times."""
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute("SELECT COUNT(*) FROM market_items")
        count = (await cursor.fetchone())[0]

        if count > 0:
            return  # Already seeded

        items = [
            # Fish & Sea
            ("Sardine", "fish", "A tiny common fish", "🐟", 10, "common"),
            ("Salmon", "fish", "A healthy pink fish", "🐟", 45, "common"),
            ("Tuna", "fish", "A big ocean fish", "🐟", 80, "uncommon"),
            ("Swordfish", "fish", "A powerful predator fish", "⚔️", 200, "rare"),
            ("Golden Koi", "fish", "A legendary golden fish", "✨", 1500, "legendary"),
            ("Pufferfish", "fish", "Cute but deadly", "🐡", 120, "uncommon"),
            ("Octopus", "fish", "Eight-armed sea creature", "🐙", 250, "rare"),
            ("Whale", "fish", "The biggest catch possible", "🐋", 5000, "legendary"),
            ("Shrimp", "fish", "Tiny but tasty", "🦐", 15, "common"),
            ("Lobster", "fish", "A fancy red crustacean", "🦞", 300, "rare"),
            ("Crab", "fish", "A snappy little fella", "🦀", 60, "common"),
            ("Jellyfish", "fish", "Beautiful and dangerous", "🪼", 90, "uncommon"),

            # Minerals & Gems
            ("Coal", "minerals", "A chunk of coal", "⚫", 5, "common"),
            ("Iron Ore", "minerals", "Raw iron ore", "🪨", 25, "common"),
            ("Copper Ore", "minerals", "Shiny copper ore", "🟤", 30, "common"),
            ("Silver Ore", "minerals", "Gleaming silver ore", "⚪", 80, "uncommon"),
            ("Gold Ore", "minerals", "Precious gold ore", "🟡", 200, "rare"),
            ("Diamond", "minerals", "A brilliant diamond", "💎", 1000, "epic"),
            ("Emerald", "minerals", "A vivid green gem", "💚", 800, "epic"),
            ("Ruby", "minerals", "A fiery red gem", "❤️", 850, "epic"),
            ("Sapphire", "minerals", "A deep blue gem", "💙", 900, "epic"),
            ("Amethyst", "minerals", "A purple crystal", "💜", 400, "rare"),
            ("Obsidian", "minerals", "Volcanic glass", "🖤", 150, "uncommon"),
            ("Meteorite", "minerals", "Fragment from space", "☄️", 3000, "legendary"),

            # Food & Cooking
            ("Apple", "food", "A fresh red apple", "🍎", 8, "common"),
            ("Banana", "food", "A ripe banana", "🍌", 6, "common"),
            ("Pizza Slice", "food", "Cheesy goodness", "🍕", 25, "common"),
            ("Burger", "food", "A juicy burger", "🍔", 30, "common"),
            ("Sushi Roll", "food", "Artisanal sushi", "🍣", 75, "uncommon"),
            ("Steak", "food", "Premium wagyu steak", "🥩", 150, "rare"),
            ("Cake", "food", "A delicious cake", "🎂", 60, "uncommon"),
            ("Cookie", "food", "Warm chocolate chip cookie", "🍪", 12, "common"),
            ("Ramen", "food", "Hot bowl of ramen", "🍜", 40, "common"),
            ("Golden Apple", "food", "A mythical golden apple", "🍏", 2000, "legendary"),
            ("Taco", "food", "A crunchy taco", "🌮", 20, "common"),
            ("Ice Cream", "food", "Cold and sweet", "🍦", 15, "common"),

            # Tools & Equipment
            ("Wooden Pickaxe", "tools", "A basic pickaxe", "⛏️", 50, "common"),
            ("Iron Pickaxe", "tools", "A sturdy pickaxe", "⛏️", 200, "uncommon"),
            ("Diamond Pickaxe", "tools", "The best pickaxe", "⛏️", 1500, "epic"),
            ("Fishing Rod", "tools", "A basic fishing rod", "🎣", 40, "common"),
            ("Golden Fishing Rod", "tools", "Catches rare fish easier", "🎣", 800, "rare"),
            ("Shovel", "tools", "For digging treasures", "🔧", 35, "common"),
            ("Axe", "tools", "A sharp woodcutting axe", "🪓", 45, "common"),
            ("Telescope", "tools", "See the stars", "🔭", 300, "rare"),
            ("Compass", "tools", "Never get lost", "🧭", 100, "uncommon"),
            ("Lantern", "tools", "Lights your way", "🏮", 60, "common"),

            # Collectibles
            ("Common Card", "collectibles", "A common trading card", "🃏", 20, "common"),
            ("Rare Card", "collectibles", "A rare trading card", "🃏", 200, "rare"),
            ("Legendary Card", "collectibles", "A legendary trading card", "🃏", 2000, "legendary"),
            ("Trophy", "collectibles", "A shiny trophy", "🏆", 500, "epic"),
            ("Crown", "collectibles", "A royal crown", "👑", 3000, "legendary"),
            ("Medal", "collectibles", "A medal of honor", "🏅", 250, "rare"),
            ("Gem Stone", "collectibles", "A mysterious gem", "💠", 400, "rare"),
            ("Star Fragment", "collectibles", "Fallen from the sky", "⭐", 600, "epic"),
            ("Ancient Coin", "collectibles", "A coin from ancient times", "🪙", 350, "rare"),
            ("Lucky Clover", "collectibles", "Brings good fortune", "🍀", 150, "uncommon"),

            # Tech & Digital
            ("USB Drive", "tech", "4GB storage device", "💾", 30, "common"),
            ("SSD Drive", "tech", "Fast storage", "💿", 200, "uncommon"),
            ("Graphics Card", "tech", "RTX quality", "🖥️", 800, "rare"),
            ("Laptop", "tech", "A portable computer", "💻", 1200, "epic"),
            ("Smartphone", "tech", "Latest model phone", "📱", 600, "rare"),
            ("Server Rack", "tech", "Enterprise server", "🖥️", 3000, "legendary"),
            ("Robot", "tech", "A tiny robot companion", "🤖", 2500, "legendary"),
            ("Satellite", "tech", "Your own satellite", "📡", 5000, "legendary"),
            ("Drone", "tech", "A flying drone", "🛸", 400, "rare"),
            ("VR Headset", "tech", "Virtual reality device", "🥽", 500, "rare"),

            # Domains & Premium Digital
            (".com Domain", "premium", "A .com domain name", "🌐", 1500, "epic"),
            (".io Domain", "premium", "A .io domain name", "🌐", 2000, "epic"),
            (".gg Domain", "premium", "A .gg domain name", "🌐", 2500, "legendary"),
            (".dev Domain", "premium", "A .dev domain name", "🌐", 1800, "epic"),
            ("Nitro Classic", "premium", "Discord Nitro Classic", "💎", 3000, "legendary"),
            ("Nitro Full", "premium", "Discord Nitro Full", "💎", 5000, "legendary"),
            ("Premium Badge", "premium", "An exclusive badge", "🏷️", 4000, "legendary"),
            ("Custom Bot", "premium", "Your own custom bot", "🤖", 8000, "legendary"),
            ("Private Server", "premium", "Your own game server", "🖥️", 6000, "legendary"),
            ("NFT Certificate", "premium", "A unique certificate", "📜", 1000, "epic"),

            # Nature & Plants
            ("Oak Seed", "nature", "Grow an oak tree", "🌰", 10, "common"),
            ("Rose", "nature", "A beautiful red rose", "🌹", 30, "common"),
            ("Sunflower", "nature", "A bright sunflower", "🌻", 20, "common"),
            ("Bonsai Tree", "nature", "A tiny perfect tree", "🌳", 300, "rare"),
            ("Venus Flytrap", "nature", "A carnivorous plant", "🪴", 150, "uncommon"),
            ("Mushroom", "nature", "A forest mushroom", "🍄", 15, "common"),
            ("Cactus", "nature", "A prickly cactus", "🌵", 25, "common"),
            ("Cherry Blossom", "nature", "A delicate blossom", "🌸", 100, "uncommon"),
            ("Four Leaf Clover", "nature", "Very lucky find", "🍀", 500, "epic"),
            ("World Tree Seed", "nature", "A mythical seed", "🌲", 10000, "legendary"),

            # Potions & Magic
            ("Health Potion", "magic", "Restores vitality", "🧪", 50, "common"),
            ("Mana Potion", "magic", "Restores energy", "🧪", 50, "common"),
            ("Speed Potion", "magic", "Makes you faster", "⚡", 120, "uncommon"),
            ("Luck Potion", "magic", "Increases luck", "🍀", 300, "rare"),
            ("Invisibility Potion", "magic", "Become invisible", "👻", 500, "epic"),
            ("Love Potion", "magic", "Smells like roses", "💕", 200, "rare"),
            ("Dragon Scale", "magic", "From a real dragon", "🐉", 2000, "legendary"),
            ("Phoenix Feather", "magic", "Burns eternally", "🪶", 3000, "legendary"),
            ("Wizard Hat", "magic", "Pointy and magical", "🧙", 400, "rare"),
            ("Crystal Ball", "magic", "See the future", "🔮", 600, "epic"),

            # Vehicles
            ("Bicycle", "vehicles", "A simple bicycle", "🚲", 100, "common"),
            ("Motorcycle", "vehicles", "A fast motorcycle", "🏍️", 500, "rare"),
            ("Sports Car", "vehicles", "A sleek sports car", "🏎️", 3000, "legendary"),
            ("Yacht", "vehicles", "A luxury yacht", "🛥️", 8000, "legendary"),
            ("Helicopter", "vehicles", "A private helicopter", "🚁", 6000, "legendary"),
            ("Rocket", "vehicles", "To the moon!", "🚀", 15000, "legendary"),
            ("Skateboard", "vehicles", "A cool skateboard", "🛹", 40, "common"),
            ("Sailboat", "vehicles", "A sailing boat", "⛵", 800, "rare"),
            ("Hot Air Balloon", "vehicles", "Float in the sky", "🎈", 1200, "epic"),
            ("Submarine", "vehicles", "Explore the deep", "🛟", 5000, "legendary"),

            # Pets
            ("Kitten", "pets", "A cute little kitten", "🐱", 200, "uncommon"),
            ("Puppy", "pets", "A loyal puppy", "🐶", 200, "uncommon"),
            ("Hamster", "pets", "A tiny hamster", "🐹", 80, "common"),
            ("Parrot", "pets", "A colorful parrot", "🦜", 300, "rare"),
            ("Bunny", "pets", "A fluffy bunny", "🐰", 150, "uncommon"),
            ("Turtle", "pets", "A wise old turtle", "🐢", 100, "common"),
            ("Fox", "pets", "A clever fox", "🦊", 500, "rare"),
            ("Owl", "pets", "A wise owl", "🦉", 400, "rare"),
            ("Dragon Egg", "pets", "May hatch someday", "🥚", 5000, "legendary"),
            ("Unicorn", "pets", "A mythical unicorn", "🦄", 10000, "legendary"),
        ]

        for name, cat, desc, emoji, price, rarity in items:
            await db.execute(
                """INSERT OR IGNORE INTO market_items 
                   (name, category, description, emoji, base_price, current_price, rarity) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, cat, desc, emoji, price, float(price), rarity)
            )

        await db.commit()
        print(f"✅ Seeded {len(items)} market items!")


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_level_xp(level):
    return 5 * (level ** 2) + 50 * level + 100

def get_level_from_xp(xp):
    level = 1
    while xp >= get_level_xp(level):
        xp -= get_level_xp(level)
        level += 1
    return level, xp

async def get_user_data(user_id, guild_id):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        row = await cursor.fetchone()

        if not row:
            await db.execute(
                "INSERT INTO users (user_id, guild_id) VALUES (?, ?)",
                (user_id, guild_id)
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            row = await cursor.fetchone()

        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))

async def update_user_data(user_id, guild_id, **kwargs):
    async with aiosqlite.connect("bot_database.db") as db:
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [user_id, guild_id]
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE user_id = ? AND guild_id = ?",
            values
        )
        await db.commit()

async def log_action(guild, embed):
    if not CONFIG["LOGGING_ENABLED"]:
        return
    log_channel_id = CONFIG.get("LOG_CHANNEL")
    if log_channel_id:
        channel = guild.get_channel(log_channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass

def create_embed(title, description=None, color=discord.Color.blue(), **kwargs):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.datetime.utcnow()
    if "author" in kwargs:
        embed.set_author(name=kwargs["author"].name, icon_url=kwargs["author"].display_avatar.url)
    if "footer" in kwargs:
        embed.set_footer(text=kwargs["footer"])
    if "thumbnail" in kwargs and kwargs["thumbnail"]:
        embed.set_thumbnail(url=kwargs["thumbnail"])
    if "image" in kwargs and kwargs["image"]:
        embed.set_image(url=kwargs["image"])
    if "fields" in kwargs:
        for name, value, inline in kwargs["fields"]:
            embed.add_field(name=name, value=value, inline=inline)
    return embed

def parse_time(time_str):
    time_regex = re.compile(r"(\d+)([smhdw])")
    matches = time_regex.findall(time_str.lower())
    if not matches:
        return None
    total_seconds = 0
    for value, unit in matches:
        value = int(value)
        if unit == "s": total_seconds += value
        elif unit == "m": total_seconds += value * 60
        elif unit == "h": total_seconds += value * 3600
        elif unit == "d": total_seconds += value * 86400
        elif unit == "w": total_seconds += value * 604800
    return total_seconds

def get_rarity_color(rarity):
    colors = {
        "common": discord.Color.light_grey(),
        "uncommon": discord.Color.green(),
        "rare": discord.Color.blue(),
        "epic": discord.Color.purple(),
        "legendary": discord.Color.gold()
    }
    return colors.get(rarity, discord.Color.default())

def calculate_market_price(base_price, total_bought, total_sold):
    """Dynamic pricing: more buys = higher price, more sells = lower price"""
    demand_ratio = (total_bought + 1) / (total_sold + 1)
    multiplier = math.log(demand_ratio + 1, 2) + 0.5
    multiplier = max(0.3, min(multiplier, 5.0))  # clamp 30%-500%
    return round(base_price * multiplier, 2)


# ══════════════════════════════════════════════════════════════════════════════
# TICKET PANEL (BUTTON-BASED) - NEW
# ══════════════════════════════════════════════════════════════════════════════

class TicketCloseConfirm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.red, custom_id="ticket:confirm_close")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)

        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE tickets SET status = 'closed', closed_at = ? WHERE channel_id = ?",
                (datetime.datetime.utcnow().isoformat(), interaction.channel.id)
            )
            await db.commit()

        await interaction.channel.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Ticket close cancelled.", ephemeral=True)
        self.stop()


class TicketControlView(discord.ui.View):
    """View shown inside ticket channel with close button"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
                (interaction.channel.id,)
            )
            ticket = await cursor.fetchone()

        if not ticket:
            return await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)

        await interaction.response.send_message(
            "Are you sure you want to close this ticket?",
            view=TicketCloseConfirm(),
            ephemeral=False
        )


class TicketPanelView(discord.ui.View):
    """Persistent panel posted in a channel with Create Ticket button"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Create Ticket", style=discord.ButtonStyle.green, custom_id="ticket:create")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT channel_id FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'",
                (user.id, guild.id)
            )
            existing = await cursor.fetchone()

        if existing:
            return await interaction.response.send_message(
                f"❌ You already have an open ticket: <#{existing[0]}>",
                ephemeral=True
            )

        category = guild.get_channel(CONFIG.get("TICKET_CATEGORY")) if CONFIG.get("TICKET_CATEGORY") else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                attach_files=True, embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, manage_messages=True
            )
        }

        # Add mod roles to overwrites
        for mod_role_id in CONFIG.get("MOD_ROLES", []):
            mod_role = guild.get_role(mod_role_id)
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        for admin_role_id in CONFIG.get("ADMIN_ROLES", []):
            admin_role = guild.get_role(admin_role_id)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{user.name}".replace(" ", "-").lower()[:50],
            category=category if isinstance(category, discord.CategoryChannel) else None,
            overwrites=overwrites,
            topic=f"Support ticket for {user} ({user.id})"
        )

        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "INSERT INTO tickets (channel_id, user_id, guild_id) VALUES (?, ?, ?)",
                (channel.id, user.id, guild.id)
            )
            await db.commit()

        embed = create_embed(
            title="🎫 Support Ticket",
            description=(
                f"Welcome {user.mention}!\n\n"
                f"Please describe your issue below.\n"
                f"A staff member will assist you shortly.\n\n"
                f"Click 🔒 **Close Ticket** when done."
            ),
            color=discord.Color.green(),
            footer=f"Ticket by {user.name}"
        )

        await channel.send(user.mention, embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
# COLOR ROLE PANEL (BUTTON-BASED) - NEW
# ══════════════════════════════════════════════════════════════════════════════

class ColorRoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, emoji: str, style: int):
        button_styles = {
            1: discord.ButtonStyle.primary,
            2: discord.ButtonStyle.secondary,
            3: discord.ButtonStyle.success,
            4: discord.ButtonStyle.danger
        }
        super().__init__(
            label=label,
            emoji=emoji,
            style=button_styles.get(style, discord.ButtonStyle.primary),
            custom_id=f"colorrole:{role_id}"
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("❌ Role not found!", ephemeral=True)

        member = interaction.user

        # Remove other color roles from this panel first
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT role_id FROM color_roles WHERE guild_id = ?",
                (interaction.guild.id,)
            )
            all_color_roles = [r[0] for r in await cursor.fetchall()]

        roles_to_remove = [interaction.guild.get_role(rid) for rid in all_color_roles
                          if rid != self.role_id and interaction.guild.get_role(rid) in member.roles]
        roles_to_remove = [r for r in roles_to_remove if r]

        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"✅ Removed **{role.name}**", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Added **{role.name}**", ephemeral=True)


class ColorRolePanelView(discord.ui.View):
    def __init__(self, roles_data):
        super().__init__(timeout=None)
        for role_id, label, emoji, style in roles_data:
            self.add_item(ColorRoleButton(role_id, label, emoji, style))


# ══════════════════════════════════════════════════════════════════════════════
# MARKETPLACE VIEWS - NEW
# ══════════════════════════════════════════════════════════════════════════════

class MarketPageView(discord.ui.View):
    def __init__(self, pages, current_page=0, author_id=None):
        super().__init__(timeout=120)
        self.pages = pages
        self.current_page = current_page
        self.author_id = author_id

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Not your menu!", ephemeral=True)
        self.current_page = (self.current_page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Not your menu!", ephemeral=True)
        self.current_page = (self.current_page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)


# ══════════════════════════════════════════════════════════════════════════════
# BOT EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    await init_database()
    await seed_market_items()

    print(f"{'═' * 50}")
    print(f"🤖 Bot: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"📊 Servers: {len(bot.guilds)}")
    print(f"👥 Users: {sum(g.member_count for g in bot.guilds)}")
    print(f"{'═' * 50}")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

    # Register persistent views
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())

    # Load color role panels
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute("SELECT role_id, label, emoji, style FROM color_roles WHERE guild_id IS NOT NULL")
        rows = await cursor.fetchall()
        if rows:
            bot.add_view(ColorRolePanelView(rows))

    # Start background tasks
    check_reminders.start()
    check_giveaways.start()
    update_status.start()

    # Load reaction roles and custom commands
    await load_reaction_roles()
    await load_custom_commands()

    # Connect to music VC if configured
    if WAVELINK_AVAILABLE and CONFIG["MUSIC_ENABLED"]:
        try:
            node = wavelink.Node(uri=CONFIG["LAVALINK_URI"], password=CONFIG["LAVALINK_PASSWORD"])
            await wavelink.Pool.connect(client=bot, nodes=[node])
            print("✅ Connected to Lavalink node")
        except Exception as e:
            print(f"⚠️ Lavalink connection failed: {e}")
            print("   Music features will be unavailable until Lavalink is running.")


@bot.event
async def on_member_join(member):
    if not CONFIG["WELCOME_ENABLED"]:
        return

    if CONFIG.get("AUTO_ROLE"):
        role = member.guild.get_role(CONFIG["AUTO_ROLE"])
        if role:
            try:
                await member.add_roles(role)
            except:
                pass

    if CONFIG.get("WELCOME_CHANNEL"):
        channel = member.guild.get_channel(CONFIG["WELCOME_CHANNEL"])
        if channel:
            embed = create_embed(
                title="👋 Welcome!",
                description=f"Welcome to **{member.guild.name}**, {member.mention}!\n\n"
                           f"You are member **#{member.guild.member_count}**",
                color=discord.Color.green(),
                thumbnail=member.display_avatar.url
            )
            embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
            await channel.send(embed=embed)

    log_embed = create_embed(
        title="📥 Member Joined",
        description=f"{member.mention} ({member.name})",
        color=discord.Color.green(),
        fields=[
            ("Account Age", f"<t:{int(member.created_at.timestamp())}:R>", True),
            ("Member Count", str(member.guild.member_count), True)
        ]
    )
    await log_action(member.guild, log_embed)


@bot.event
async def on_member_remove(member):
    if not CONFIG["WELCOME_ENABLED"]:
        return

    if CONFIG.get("LEAVE_CHANNEL"):
        channel = member.guild.get_channel(CONFIG["LEAVE_CHANNEL"])
        if channel:
            embed = create_embed(
                title="👋 Goodbye!",
                description=f"**{member.name}** has left the server.\n"
                           f"We now have **{member.guild.member_count}** members.",
                color=discord.Color.red(),
                thumbnail=member.display_avatar.url
            )
            await channel.send(embed=embed)

    log_embed = create_embed(
        title="📤 Member Left",
        description=f"{member.name}#{member.discriminator}",
        color=discord.Color.red()
    )
    await log_action(member.guild, log_embed)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check AFK
    if message.author.id in afk_users:
        del afk_users[message.author.id]
        await message.channel.send(
            f"Welcome back {message.author.mention}! I've removed your AFK status.",
            delete_after=5
        )

    for user in message.mentions:
        if user.id in afk_users:
            afk_data = afk_users[user.id]
            await message.channel.send(
                f"💤 **{user.name}** is AFK: {afk_data['reason']} - <t:{int(afk_data['time'])}:R>",
                delete_after=10
            )

    # Custom commands
    if message.content.startswith(CONFIG["PREFIX"]):
        cmd_name = message.content[len(CONFIG["PREFIX"]):].split()[0].lower()
        if cmd_name in custom_commands:
            await message.channel.send(custom_commands[cmd_name])
            async with aiosqlite.connect("bot_database.db") as db:
                await db.execute(
                    "UPDATE custom_commands SET uses = uses + 1 WHERE name = ?",
                    (cmd_name,)
                )
                await db.commit()

    # Auto-mod
    if CONFIG["AUTOMOD_ENABLED"] and message.guild and not message.author.guild_permissions.administrator:
        if CONFIG["ANTI_SPAM_ENABLED"]:
            now = time.time()
            spam_tracker[message.author.id].append(now)
            spam_tracker[message.author.id] = [
                t for t in spam_tracker[message.author.id]
                if now - t < CONFIG["SPAM_INTERVAL"]
            ]
            if len(spam_tracker[message.author.id]) >= CONFIG["SPAM_THRESHOLD"]:
                await message.channel.purge(
                    limit=CONFIG["SPAM_THRESHOLD"],
                    check=lambda m: m.author == message.author
                )
                await message.channel.send(
                    f"⚠️ {message.author.mention} Stop spamming!",
                    delete_after=5
                )
                spam_tracker[message.author.id] = []
                return

        content_lower = message.content.lower()
        for word in CONFIG["BANNED_WORDS"]:
            if word.lower() in content_lower:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention} That word is not allowed!",
                    delete_after=5
                )
                return

        if CONFIG["ANTI_LINK_ENABLED"]:
            url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*')
            if url_pattern.search(message.content):
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention} Links are not allowed!",
                    delete_after=5
                )
                return

        if len(message.mentions) > CONFIG["MAX_MENTIONS"]:
            await message.delete()
            await message.channel.send(
                f"⚠️ {message.author.mention} Too many mentions!",
                delete_after=5
            )
            return

    # Leveling system
    if CONFIG["LEVELING_ENABLED"] and message.guild:
        user_id = message.author.id
        now = time.time()
        if user_id not in xp_cooldowns or now - xp_cooldowns[user_id] >= CONFIG["XP_COOLDOWN"]:
            xp_cooldowns[user_id] = now
            xp_gain = random.randint(*CONFIG["XP_PER_MESSAGE"])
            user_data = await get_user_data(user_id, message.guild.id)
            new_xp = user_data["xp"] + xp_gain
            old_level = user_data["level"]
            new_level, remaining_xp = get_level_from_xp(new_xp)

            await update_user_data(
                user_id, message.guild.id,
                xp=new_xp,
                level=new_level,
                messages=user_data["messages"] + 1
            )

            if new_level > old_level:
                level_msg = CONFIG["LEVEL_UP_MESSAGE"].format(
                    user=message.author.mention,
                    level=new_level
                )
                if CONFIG.get("LEVEL_UP_CHANNEL"):
                    channel = message.guild.get_channel(CONFIG["LEVEL_UP_CHANNEL"])
                    if channel:
                        await channel.send(level_msg)
                else:
                    await message.channel.send(level_msg)

    await bot.process_commands(message)


@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    embed = create_embed(
        title="🗑️ Message Deleted",
        color=discord.Color.red(),
        fields=[
            ("Author", f"{message.author.mention}", True),
            ("Channel", f"{message.channel.mention}", True),
            ("Content", message.content[:1000] if message.content else "No content", False)
        ]
    )
    await log_action(message.guild, embed)


@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    embed = create_embed(
        title="✏️ Message Edited",
        color=discord.Color.yellow(),
        fields=[
            ("Author", f"{before.author.mention}", True),
            ("Channel", f"{before.channel.mention}", True),
            ("Before", before.content[:500] if before.content else "No content", False),
            ("After", after.content[:500] if after.content else "No content", False),
            ("Jump", f"[Click here]({after.jump_url})", True)
        ]
    )
    await log_action(before.guild, embed)


@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        added = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        if added:
            embed = create_embed(
                title="🎭 Role Added",
                description=f"{after.mention}",
                color=discord.Color.green(),
                fields=[("Role", ", ".join([r.mention for r in added]), False)]
            )
            await log_action(after.guild, embed)
        if removed:
            embed = create_embed(
                title="🎭 Role Removed",
                description=f"{after.mention}",
                color=discord.Color.red(),
                fields=[("Role", ", ".join([r.mention for r in removed]), False)]
            )
            await log_action(after.guild, embed)

    if before.nick != after.nick:
        embed = create_embed(
            title="📝 Nickname Changed",
            description=f"{after.mention}",
            color=discord.Color.blue(),
            fields=[
                ("Before", before.nick or "None", True),
                ("After", after.nick or "None", True)
            ]
        )
        await log_action(after.guild, embed)


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    key = f"{payload.message_id}-{str(payload.emoji)}"
    if key in reaction_roles:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(reaction_roles[key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.add_roles(role)


@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return
    key = f"{payload.message_id}-{str(payload.emoji)}"
    if key in reaction_roles:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(reaction_roles[key])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.remove_roles(role)


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASKS
# ══════════════════════════════════════════════════════════════════════════════

@tasks.loop(seconds=30)
async def check_reminders():
    now = datetime.datetime.utcnow()
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE remind_at <= ?",
            (now.isoformat(),)
        )
        reminders_list = await cursor.fetchall()
        for reminder in reminders_list:
            try:
                channel = bot.get_channel(reminder[2])
                if channel:
                    user = await bot.fetch_user(reminder[1])
                    await channel.send(f"⏰ {user.mention} Reminder: **{reminder[3]}**")
            except:
                pass
            await db.execute("DELETE FROM reminders WHERE id = ?", (reminder[0],))
        await db.commit()


@tasks.loop(seconds=30)
async def check_giveaways():
    now = datetime.datetime.utcnow()
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM giveaways WHERE end_time <= ? AND ended = 0",
            (now.isoformat(),)
        )
        giveaways = await cursor.fetchall()

        for giveaway in giveaways:
            try:
                # Correct column indexes:
                # 0=id, 1=message_id, 2=channel_id, 3=guild_id, 4=prize,
                # 5=winners, 6=host_id, 7=end_time, 8=ended, 9=participants
                channel = bot.get_channel(giveaway[2])
                if not channel:
                    continue

                message = await channel.fetch_message(giveaway[1])

                # Try to get participants from reactions instead of DB
                reaction = discord.utils.get(message.reactions, emoji="🎉")
                if reaction:
                    users = [user async for user in reaction.users() if not user.bot]
                else:
                    users = []

                winners_count = giveaway[5]
                if len(users) < winners_count:
                    winners_count = len(users)

                if winners_count > 0:
                    winners = random.sample(users, winners_count)
                    winner_mentions = ", ".join([w.mention for w in winners])
                    await channel.send(
                        f"🎉 Congratulations {winner_mentions}! You won **{giveaway[4]}**!"
                    )
                else:
                    await channel.send("😢 No one entered the giveaway.")

                # Update embed
                embed = message.embeds[0] if message.embeds else None
                if embed:
                    new_embed = discord.Embed(
                        title="🎉 GIVEAWAY ENDED 🎉",
                        description=f"🎁 **{giveaway[4]}**\n\n**Ended!**\n"
                                   f"Winners: {winner_mentions if winners_count > 0 else 'None'}",
                        color=discord.Color.red()
                    )
                    new_embed.set_footer(text="Giveaway ended")
                    new_embed.timestamp = now
                    await message.edit(embed=new_embed)

                await db.execute(
                    "UPDATE giveaways SET ended = 1 WHERE id = ?",
                    (giveaway[0],)
                )
            except Exception as e:
                print(f"Giveaway error: {e}")

        await db.commit()


@tasks.loop(minutes=5)
async def update_status():
    statuses = [
        discord.Activity(type=discord.ActivityType.watching, name=f"{sum(g.member_count for g in bot.guilds)} users"),
        discord.Activity(type=discord.ActivityType.playing, name=f"{CONFIG['PREFIX']}help"),
        discord.Activity(type=discord.ActivityType.listening, name=f"{len(bot.guilds)} servers"),
    ]
    await bot.change_presence(activity=random.choice(statuses))


async def load_reaction_roles():
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute("SELECT message_id, emoji, role_id FROM reaction_roles")
        rows = await cursor.fetchall()
        for row in rows:
            key = f"{row[0]}-{row[1]}"
            reaction_roles[key] = row[2]


async def load_custom_commands():
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute("SELECT name, response FROM custom_commands")
        rows = await cursor.fetchall()
        for row in rows:
            custom_commands[row[0]] = row[1]


# ══════════════════════════════════════════════════════════════════════════════
# HELP COMMAND
# ══════════════════════════════════════════════════════════════════════════════

class HelpDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🛡️ Moderation", description="Kick, ban, mute, warn, and more", value="mod"),
            discord.SelectOption(label="🎮 Fun", description="Games and entertainment commands", value="fun"),
            discord.SelectOption(label="🔧 Utility", description="Helpful utility commands", value="util"),
            discord.SelectOption(label="📊 Leveling", description="XP and ranking system", value="level"),
            discord.SelectOption(label="💰 Economy", description="Virtual currency system", value="eco"),
            discord.SelectOption(label="🛒 Marketplace", description="Buy, sell, trade items", value="market"),
            discord.SelectOption(label="🎫 Tickets", description="Support ticket system", value="ticket"),
            discord.SelectOption(label="🎉 Giveaways", description="Giveaway commands", value="giveaway"),
            discord.SelectOption(label="🎵 Music", description="Music player commands", value="music"),
            discord.SelectOption(label="🤖 AI", description="AI assistant commands", value="ai"),
            discord.SelectOption(label="💕 Waifu", description="Waifu collection", value="waifu"),
            discord.SelectOption(label="⚙️ Admin", description="Server configuration", value="admin"),
        ]
        super().__init__(placeholder="Select a category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        embeds = {
            "mod": create_embed(
                "🛡️ Moderation Commands",
                "```\n"
                "!kick <user> [reason]    - Kick a member\n"
                "!ban <user> [reason]     - Ban a member\n"
                "!unban <user_id>         - Unban a user\n"
                "!mute <user> <time>      - Timeout a member\n"
                "!unmute <user>           - Remove timeout\n"
                "!warn <user> <reason>    - Warn a member\n"
                "!warnings <user>         - View warnings\n"
                "!clearwarns <user>       - Clear warnings\n"
                "!purge <amount>          - Delete messages\n"
                "!slowmode <seconds>      - Set slowmode\n"
                "!lock                    - Lock channel\n"
                "!unlock                  - Unlock channel\n"
                "!nick <user> <name>      - Change nickname\n"
                "!role <user> <role>      - Toggle role\n"
                "```",
                discord.Color.red()
            ),
            "fun": create_embed(
                "🎮 Fun Commands",
                "```\n"
                "!8ball <question>        - Ask the magic 8ball\n"
                "!roll [sides]            - Roll a dice\n"
                "!flip                    - Flip a coin\n"
                "!choose <options>        - Random choice\n"
                "!rps <choice>            - Rock paper scissors\n"
                "!joke                    - Random joke\n"
                "!hug <user>              - Hug someone\n"
                "!slap <user>             - Slap someone\n"
                "!rate <thing>            - Rate something\n"
                "!ship <user1> <user2>    - Ship two users\n"
                "!emojify <text>          - Convert to emojis\n"
                "!reverse <text>          - Reverse text\n"
                "```",
                discord.Color.purple()
            ),
            "util": create_embed(
                "🔧 Utility Commands",
                "```\n"
                "!help                    - This menu\n"
                "!ping                    - Bot latency\n"
                "!userinfo [user]         - User information\n"
                "!serverinfo              - Server information\n"
                "!avatar [user]           - Get avatar\n"
                "!banner [user]           - Get banner\n"
                "!roleinfo <role>         - Role information\n"
                "!afk [reason]            - Set AFK status\n"
                "!remind <time> <text>    - Set reminder\n"
                "!poll <question>         - Create a poll\n"
                "!embed <title> | <desc>  - Create embed\n"
                "!steal <emoji>           - Steal emoji\n"
                "```",
                discord.Color.blue()
            ),
            "level": create_embed(
                "📊 Leveling Commands",
                "```\n"
                "!rank [user]             - View rank card\n"
                "!leaderboard [page]      - XP leaderboard\n"
                "!setxp <user> <amount>   - Set user XP\n"
                "!setlevel <user> <level> - Set user level\n"
                "!resetxp <user>          - Reset user XP\n"
                "```",
                discord.Color.gold()
            ),
            "eco": create_embed(
                "💰 Economy Commands",
                "```\n"
                "!balance [user]          - Check balance\n"
                "!daily                   - Claim daily reward\n"
                "!work                    - Work for money\n"
                "!pay <user> <amount>     - Pay someone\n"
                "!deposit <amount>        - Deposit to bank\n"
                "!withdraw <amount>       - Withdraw from bank\n"
                "!rob <user>              - Rob someone\n"
                "!slots <amount>          - Play slots\n"
                "!gamble <amount>         - Gamble coins\n"
                "!baltop [page]           - Rich leaderboard\n"
                "```",
                discord.Color.green()
            ),
            "market": create_embed(
                "🛒 Marketplace Commands",
                "```\n"
                "!market [category] [pg]  - Browse market\n"
                "!mbuy <item_id> [qty]    - Buy from market\n"
                "!msell <item_id> [qty]   - Sell to market\n"
                "!minv [user]             - Market inventory\n"
                "!minfo <item_id>         - Item details\n"
                "!trade <user> <item_id> <qty> <price>\n"
                "                         - Offer a trade\n"
                "!trades                  - View your trades\n"
                "!tradeaccept <trade_id>  - Accept trade\n"
                "!tradedecline <trade_id> - Decline trade\n"
                "!mcategories             - List categories\n"
                "\n"
                "Dynamic pricing: prices change\n"
                "based on supply and demand!\n"
                "```",
                discord.Color.teal()
            ),
            "ticket": create_embed(
                "🎫 Ticket Commands",
                "```\n"
                "!ticketpanel [channel]   - Post ticket panel\n"
                "!ticket                  - Create ticket\n"
                "!close                   - Close ticket\n"
                "!add <user>              - Add to ticket\n"
                "!remove <user>           - Remove from ticket\n"
                "```",
                discord.Color.orange()
            ),
            "giveaway": create_embed(
                "🎉 Giveaway Commands",
                "```\n"
                "!gstart <time> <winners> <prize>\n"
                "                         - Start giveaway\n"
                "!gend <message_id>       - End giveaway\n"
                "!greroll <message_id>    - Reroll winner\n"
                "```",
                discord.Color.magenta()
            ),
            "music": create_embed(
                "🎵 Music Commands",
                "```\n"
                "!play <url/search>       - Play a song\n"
                "!pause                   - Pause playback\n"
                "!resume                  - Resume playback\n"
                "!skip                    - Skip current song\n"
                "!stop                    - Stop & disconnect\n"
                "!queue                   - View queue\n"
                "!nowplaying              - Current song info\n"
                "!volume <0-100>          - Set volume\n"
                "!loop                    - Toggle loop mode\n"
                "!shuffle                 - Shuffle queue\n"
                "!join                    - Join your VC\n"
                "!leave                   - Leave VC\n"
                "!247                     - Toggle 24/7 mode\n"
                "\n"
                "Supports: YouTube, SoundCloud,\n"
                "and more via Lavalink\n"
                "```",
                discord.Color.red()
            ),
            "ai": create_embed(
                "🤖 AI Commands",
                "```\n"
                "!gemini <prompt>         - Ask Google Gemini\n"
                "!gpt <prompt>            - Ask OpenAI GPT\n"
                "!groq <prompt>           - Ask Groq\n"
                "!claude <prompt>         - Ask Claude\n"
                "!mistral <prompt>        - Ask Mistral\n"
                "!cohere <prompt>         - Ask Cohere\n"
                "!perplexity <prompt>     - Ask Perplexity\n"
                "\n"
                "Admin:\n"
                "!ai set <provider> <key> - Set API key\n"
                "!ai providers            - List providers\n"
                "!ai remove <provider>    - Remove API key\n"
                "```",
                discord.Color.blurple()
            ),
            "waifu": create_embed(
                "💕 Waifu Commands",
                "```\n"
                "!waifu [type]            - Get random waifu\n"
                "  Types: waifu, neko, shinobu,\n"
                "         megumin, bully, cuddle,\n"
                "         cry, hug, awoo, kiss,\n"
                "         lick, pat, smug, bonk,\n"
                "         yeet, blush, smile, wave,\n"
                "         highfive, handhold, nom,\n"
                "         bite, glomp, slap, kill,\n"
                "         kick, happy, wink, poke,\n"
                "         dance, cringe\n"
                "!waifucollect [type]     - Collect a waifu\n"
                "!waifubox [user]         - View collection\n"
                "```",
                discord.Color.pink()
            ),
            "admin": create_embed(
                "⚙️ Admin Commands",
                "```\n"
                "!setwelcome <channel>    - Set welcome channel\n"
                "!setleave <channel>      - Set leave channel\n"
                "!setlog <channel>        - Set log channel\n"
                "!setautorole <role>      - Set auto role\n"
                "!setmuterole <role>      - Set mute role\n"
                "!ticketpanel [channel]   - Post ticket panel\n"
                "!addcolorrole <role> <label> <emoji>\n"
                "                         - Add color role\n"
                "!removecolorrole <role>  - Remove color role\n"
                "!colorpanel [channel]    - Post color panel\n"
                "!addcmd <name> <resp>    - Add custom cmd\n"
                "!delcmd <name>           - Delete custom cmd\n"
                "!reactionrole <msg> <emoji> <role>\n"
                "                         - Add reaction role\n"
                "!toggle <feature>        - Toggle features\n"
                "!addword <word>          - Add banned word\n"
                "!removeword <word>       - Remove banned word\n"
                "!addshopitem             - Add shop item\n"
                "!removeshopitem <id>     - Remove shop item\n"
                "```",
                discord.Color.dark_grey()
            )
        }
        await interaction.response.edit_message(embed=embeds[self.values[0]])


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(HelpDropdown())


@bot.command(name="help")
async def help_command(ctx):
    embed = create_embed(
        title="🤖 Bot Help Menu",
        description="Welcome to the Ultimate Discord Bot!\n\n"
                   "**Select a category below to view commands.**\n\n"
                   f"**Prefix:** `{CONFIG['PREFIX']}`\n"
                   f"**Total Commands:** 100+\n"
                   f"**Features:** Moderation, Economy, Market, Music, AI, Waifu & more!",
        color=discord.Color.blurple(),
        author=ctx.author
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=embed, view=HelpView())


# ══════════════════════════════════════════════════════════════════════════════
# MODERATION COMMANDS (UNCHANGED)
# ══════════════════════════════════════════════════════════════════════════════

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ You cannot kick this user.")
    await member.kick(reason=reason)
    embed = create_embed(
        title="👢 Member Kicked",
        color=discord.Color.orange(),
        fields=[
            ("User", f"{member.mention}", True),
            ("Moderator", f"{ctx.author.mention}", True),
            ("Reason", reason, False)
        ]
    )
    await ctx.send(embed=embed)
    await log_action(ctx.guild, embed)
    try:
        await member.send(f"You have been kicked from **{ctx.guild.name}**.\nReason: {reason}")
    except:
        pass

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ You cannot ban this user.")
    await member.ban(reason=reason, delete_message_days=1)
    embed = create_embed(
        title="🔨 Member Banned",
        color=discord.Color.red(),
        fields=[
            ("User", f"{member.mention}", True),
            ("Moderator", f"{ctx.author.mention}", True),
            ("Reason", reason, False)
        ]
    )
    await ctx.send(embed=embed)
    await log_action(ctx.guild, embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ **{user.name}** has been unbanned.")
    except discord.NotFound:
        await ctx.send("❌ User not found in ban list.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
    seconds = parse_time(duration)
    if not seconds:
        return await ctx.send("❌ Invalid duration. Use format: 1d, 2h, 30m, 60s")
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ You cannot mute this user.")
    until = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
    await member.timeout(until, reason=reason)
    embed = create_embed(
        title="🔇 Member Muted",
        color=discord.Color.orange(),
        fields=[
            ("User", f"{member.mention}", True),
            ("Duration", duration, True),
            ("Moderator", f"{ctx.author.mention}", True),
            ("Reason", reason, False)
        ]
    )
    await ctx.send(embed=embed)
    await log_action(ctx.guild, embed)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"✅ {member.mention} has been unmuted.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def warn(ctx, member: discord.Member, *, reason: str):
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (member.id, ctx.guild.id, ctx.author.id, reason)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id)
        )
        count = (await cursor.fetchone())[0]
    embed = create_embed(
        title="⚠️ Member Warned",
        color=discord.Color.yellow(),
        fields=[
            ("User", f"{member.mention}", True),
            ("Moderator", f"{ctx.author.mention}", True),
            ("Total Warnings", str(count), True),
            ("Reason", reason, False)
        ]
    )
    await ctx.send(embed=embed)
    await log_action(ctx.guild, embed)
    try:
        await member.send(f"You have been warned in **{ctx.guild.name}**.\nReason: {reason}\nTotal warnings: {count}")
    except:
        pass

@bot.command()
async def warnings(ctx, member: discord.Member = None):
    member = member or ctx.author
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT reason, moderator_id, created_at FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC LIMIT 10",
            (member.id, ctx.guild.id)
        )
        warns = await cursor.fetchall()
    if not warns:
        return await ctx.send(f"✅ {member.mention} has no warnings.")
    embed = create_embed(title=f"⚠️ Warnings for {member.name}", color=discord.Color.yellow())
    for i, (reason, mod_id, created_at) in enumerate(warns, 1):
        embed.add_field(
            name=f"#{i} - {created_at[:10]}",
            value=f"**Reason:** {reason}\n**Moderator:** <@{mod_id}>",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def clearwarns(ctx, member: discord.Member):
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "DELETE FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id)
        )
        await db.commit()
    await ctx.send(f"✅ Cleared all warnings for {member.mention}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int, member: discord.Member = None):
    if amount > 100:
        return await ctx.send("❌ Cannot delete more than 100 messages at once.")
    def check(m):
        return member is None or m.author == member
    deleted = await ctx.channel.purge(limit=amount + 1, check=check)
    await ctx.send(f"✅ Deleted {len(deleted) - 1} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await ctx.send("✅ Slowmode disabled.")
    else:
        await ctx.send(f"✅ Slowmode set to {seconds} seconds.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 {channel.mention} has been locked.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"🔓 {channel.mention} has been unlocked.")

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, nickname: str = None):
    await member.edit(nick=nickname)
    if nickname:
        await ctx.send(f"✅ Changed {member.mention}'s nickname to **{nickname}**")
    else:
        await ctx.send(f"✅ Reset {member.mention}'s nickname")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, member: discord.Member, role: discord.Role):
    if role >= ctx.author.top_role:
        return await ctx.send("❌ You cannot manage this role.")
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed {role.mention} from {member.mention}")
    else:
        await member.add_roles(role)
        await ctx.send(f"✅ Added {role.mention} to {member.mention}")


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY COMMANDS (UNCHANGED)
# ══════════════════════════════════════════════════════════════════════════════

@bot.command()
async def ping(ctx):
    embed = create_embed(
        title="🏓 Pong!",
        color=discord.Color.green(),
        fields=[
            ("Bot Latency", f"{round(bot.latency * 1000)}ms", True),
            ("API Latency", f"{round(bot.latency * 1000)}ms", True)
        ]
    )
    await ctx.send(embed=embed)

@bot.command(aliases=["ui", "whois"])
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles[1:]][:10]
    roles_str = ", ".join(roles) if roles else "None"
    embed = create_embed(
        title=f"👤 {member.name}",
        color=member.color,
        thumbnail=member.display_avatar.url
    )
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
    embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
    embed.add_field(name="Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
    embed.add_field(name=f"Roles [{len(member.roles) - 1}]", value=roles_str, inline=False)
    await ctx.send(embed=embed)

@bot.command(aliases=["si", "server"])
async def serverinfo(ctx):
    guild = ctx.guild
    embed = create_embed(
        title=f"📊 {guild.name}",
        color=discord.Color.blurple(),
        thumbnail=guild.icon.url if guild.icon else None
    )
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=f"📝 {len(guild.text_channels)} | 🔊 {len(guild.voice_channels)}", inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Emojis", value=len(guild.emojis), inline=True)
    embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier}", inline=True)
    embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)
    embed.add_field(name="Verification", value=str(guild.verification_level).title(), inline=True)
    if guild.banner:
        embed.set_image(url=guild.banner.url)
    await ctx.send(embed=embed)

@bot.command(aliases=["av"])
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = create_embed(
        title=f"🖼️ {member.name}'s Avatar",
        color=member.color,
        image=member.display_avatar.url
    )
    embed.add_field(
        name="Links",
        value=f"[PNG]({member.display_avatar.replace(format='png').url}) | "
              f"[JPG]({member.display_avatar.replace(format='jpg').url}) | "
              f"[WEBP]({member.display_avatar.replace(format='webp').url})",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command()
async def banner(ctx, member: discord.Member = None):
    member = member or ctx.author
    user = await bot.fetch_user(member.id)
    if not user.banner:
        return await ctx.send("❌ This user has no banner.")
    embed = create_embed(
        title=f"🖼️ {member.name}'s Banner",
        color=member.color,
        image=user.banner.url
    )
    await ctx.send(embed=embed)

@bot.command()
async def roleinfo(ctx, role: discord.Role):
    embed = create_embed(title=f"🎭 {role.name}", color=role.color)
    embed.add_field(name="ID", value=role.id, inline=True)
    embed.add_field(name="Color", value=str(role.color), inline=True)
    embed.add_field(name="Position", value=role.position, inline=True)
    embed.add_field(name="Members", value=len(role.members), inline=True)
    embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
    embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
    embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:R>", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def afk(ctx, *, reason: str = "AFK"):
    afk_users[ctx.author.id] = {"reason": reason, "time": time.time()}
    await ctx.send(f"💤 {ctx.author.mention} I've set your AFK: {reason}")

@bot.command()
async def remind(ctx, duration: str, *, reminder: str):
    seconds = parse_time(duration)
    if not seconds:
        return await ctx.send("❌ Invalid duration. Use format: 1d, 2h, 30m, 60s")
    remind_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "INSERT INTO reminders (user_id, channel_id, reminder, remind_at) VALUES (?, ?, ?, ?)",
            (ctx.author.id, ctx.channel.id, reminder, remind_at.isoformat())
        )
        await db.commit()
    await ctx.send(f"✅ I'll remind you about **{reminder}** <t:{int(remind_at.timestamp())}:R>")

@bot.command()
async def poll(ctx, *, question: str):
    embed = create_embed(title="📊 Poll", description=question, color=discord.Color.blurple(), author=ctx.author)
    message = await ctx.send(embed=embed)
    await message.add_reaction("👍")
    await message.add_reaction("👎")
    await message.add_reaction("🤷")

@bot.command(name="embed")
async def embed_cmd(ctx, *, content: str):
    parts = content.split("|")
    title = parts[0].strip()
    description = parts[1].strip() if len(parts) > 1 else ""
    embed = create_embed(title=title, description=description, author=ctx.author)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_emojis=True)
async def steal(ctx, emoji: discord.PartialEmoji, name: str = None):
    name = name or emoji.name
    try:
        emoji_bytes = await emoji.read()
        new_emoji = await ctx.guild.create_custom_emoji(name=name, image=emoji_bytes)
        await ctx.send(f"✅ Added emoji {new_emoji}")
    except Exception as e:
        await ctx.send(f"❌ Failed to add emoji: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# FUN COMMANDS (UNCHANGED)
# ══════════════════════════════════════════════════════════════════════════════

@bot.command(name="8ball")
async def eightball(ctx, *, question: str):
    responses = [
        "It is certain.", "It is decidedly so.", "Without a doubt.",
        "Yes - definitely.", "You may rely on it.", "As I see it, yes.",
        "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
        "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
        "Cannot predict now.", "Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.",
        "Outlook not so good.", "Very doubtful."
    ]
    embed = create_embed(
        title="🎱 Magic 8-Ball",
        color=discord.Color.purple(),
        fields=[("Question", question, False), ("Answer", random.choice(responses), False)]
    )
    await ctx.send(embed=embed)

@bot.command()
async def roll(ctx, sides: int = 6):
    result = random.randint(1, sides)
    await ctx.send(f"🎲 You rolled a **{result}** (1-{sides})")

@bot.command()
async def flip(ctx):
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"🪙 **{result}!**")

@bot.command()
async def choose(ctx, *, choices: str):
    options = re.split(r',|\bor\b', choices)
    options = [o.strip() for o in options if o.strip()]
    if len(options) < 2:
        return await ctx.send("❌ Give me at least 2 options!")
    await ctx.send(f"🤔 I choose **{random.choice(options)}**")

@bot.command()
async def rps(ctx, choice: str):
    choices = ["rock", "paper", "scissors"]
    choice = choice.lower()
    if choice not in choices:
        return await ctx.send("❌ Choose rock, paper, or scissors!")
    bot_choice = random.choice(choices)
    if choice == bot_choice:
        result = "It's a tie! 🤝"
    elif (choice == "rock" and bot_choice == "scissors") or \
         (choice == "paper" and bot_choice == "rock") or \
         (choice == "scissors" and bot_choice == "paper"):
        result = "You win! 🎉"
    else:
        result = "I win! 😎"
    await ctx.send(f"You chose **{choice}**, I chose **{bot_choice}**. {result}")

@bot.command()
async def joke(ctx):
    jokes = [
        "Why don't scientists trust atoms? Because they make up everything!",
        "Why did the scarecrow win an award? He was outstanding in his field!",
        "Why don't eggs tell jokes? They'd crack each other up!",
        "What do you call a fake noodle? An impasta!",
        "Why did the bicycle fall over? Because it was two-tired!",
        "What do you call a bear with no teeth? A gummy bear!",
        "Why can't you give Elsa a balloon? Because she will let it go!",
        "What do you call a fish without eyes? A fsh!",
    ]
    await ctx.send(f"😄 {random.choice(jokes)}")

@bot.command()
async def hug(ctx, member: discord.Member):
    if member == ctx.author:
        return await ctx.send("🤗 *hugs yourself* (You need a friend?)")
    await ctx.send(f"🤗 **{ctx.author.name}** hugs **{member.name}**!")

@bot.command()
async def slap(ctx, member: discord.Member):
    if member == ctx.author:
        return await ctx.send("🤔 Why would you slap yourself?")
    await ctx.send(f"👋 **{ctx.author.name}** slaps **{member.name}**!")

@bot.command()
async def rate(ctx, *, thing: str):
    rating = random.randint(0, 100)
    await ctx.send(f"I rate **{thing}** a **{rating}/100**! {'🔥' if rating > 80 else '👍' if rating > 50 else '👎'}")

@bot.command()
async def ship(ctx, user1: discord.Member, user2: discord.Member = None):
    user2 = user2 or ctx.author
    percentage = random.randint(0, 100)
    if percentage > 80: message = "💕 Perfect match!"
    elif percentage > 60: message = "💖 Great couple!"
    elif percentage > 40: message = "💛 Could work out!"
    elif percentage > 20: message = "💔 Not looking good..."
    else: message = "💀 Stay friends..."
    bar = "█" * (percentage // 10) + "░" * (10 - percentage // 10)
    embed = create_embed(
        title="💘 Love Calculator",
        description=f"**{user1.name}** x **{user2.name}**\n\n"
                   f"`{bar}` **{percentage}%**\n\n{message}",
        color=discord.Color.pink()
    )
    await ctx.send(embed=embed)

@bot.command()
async def emojify(ctx, *, text: str):
    emojis = {
        'a': '🇦', 'b': '🇧', 'c': '🇨', 'd': '🇩', 'e': '🇪',
        'f': '🇫', 'g': '🇬', 'h': '🇭', 'i': '🇮', 'j': '🇯',
        'k': '🇰', 'l': '🇱', 'm': '🇲', 'n': '🇳', 'o': '🇴',
        'p': '🇵', 'q': '🇶', 'r': '🇷', 's': '🇸', 't': '🇹',
        'u': '🇺', 'v': '🇻', 'w': '🇼', 'x': '🇽', 'y': '🇾',
        'z': '🇿', ' ': '  ', '0': '0️⃣', '1': '1️⃣', '2': '2️⃣',
        '3': '3️⃣', '4': '4️⃣', '5': '5️⃣', '6': '6️⃣', '7': '7️⃣',
        '8': '8️⃣', '9': '9️⃣'
    }
    result = " ".join(emojis.get(c.lower(), c) for c in text)
    await ctx.send(result[:2000])

@bot.command()
async def reverse(ctx, *, text: str):
    await ctx.send(text[::-1])


# ══════════════════════════════════════════════════════════════════════════════
# LEVELING COMMANDS (UNCHANGED)
# ══════════════════════════════════════════════════════════════════════════════

@bot.command(aliases=["level", "xp"])
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = await get_user_data(member.id, ctx.guild.id)
    xp_needed = get_level_xp(data["level"])
    current_xp = data["xp"] - sum(get_level_xp(i) for i in range(1, data["level"]))
    if xp_needed > 0:
        progress = max(0, min(20, int((current_xp / xp_needed) * 20)))
    else:
        progress = 0
    bar = "█" * progress + "░" * (20 - progress)

    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE guild_id = ? AND xp > ?",
            (ctx.guild.id, data["xp"])
        )
        rank_pos = (await cursor.fetchone())[0] + 1

    embed = create_embed(
        title=f"📊 {member.name}'s Rank",
        color=member.color,
        thumbnail=member.display_avatar.url
    )
    embed.add_field(name="Rank", value=f"#{rank_pos}", inline=True)
    embed.add_field(name="Level", value=data["level"], inline=True)
    embed.add_field(name="Total XP", value=f"{data['xp']:,}", inline=True)
    embed.add_field(name="Progress", value=f"`{bar}` {current_xp}/{xp_needed}", inline=False)
    embed.add_field(name="Messages", value=f"{data['messages']:,}", inline=True)
    await ctx.send(embed=embed)

@bot.command(aliases=["lb", "top"])
async def leaderboard(ctx, page: int = 1):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT user_id, xp, level FROM users WHERE guild_id = ? ORDER BY xp DESC LIMIT 10 OFFSET ?",
            (ctx.guild.id, (page - 1) * 10)
        )
        rows = await cursor.fetchall()
    if not rows:
        return await ctx.send("❌ No data found.")
    description = ""
    for i, (user_id, xp, level) in enumerate(rows, start=(page - 1) * 10 + 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
        description += f"{medal} <@{user_id}> - Level {level} ({xp:,} XP)\n"
    embed = create_embed(
        title=f"📊 XP Leaderboard - Page {page}",
        description=description,
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setxp(ctx, member: discord.Member, amount: int):
    await update_user_data(member.id, ctx.guild.id, xp=amount)
    new_level, _ = get_level_from_xp(amount)
    await update_user_data(member.id, ctx.guild.id, level=new_level)
    await ctx.send(f"✅ Set {member.mention}'s XP to **{amount}** (Level {new_level})")

@bot.command()
@commands.has_permissions(administrator=True)
async def setlevel(ctx, member: discord.Member, level: int):
    xp = sum(get_level_xp(i) for i in range(1, level))
    await update_user_data(member.id, ctx.guild.id, xp=xp, level=level)
    await ctx.send(f"✅ Set {member.mention} to Level **{level}**")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetxp(ctx, member: discord.Member):
    await update_user_data(member.id, ctx.guild.id, xp=0, level=1, messages=0)
    await ctx.send(f"✅ Reset {member.mention}'s XP and level")


# ══════════════════════════════════════════════════════════════════════════════
# ECONOMY COMMANDS (UNCHANGED)
# ══════════════════════════════════════════════════════════════════════════════

@bot.command(aliases=["bal", "money"])
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = await get_user_data(member.id, ctx.guild.id)
    embed = create_embed(
        title=f"💰 {member.name}'s Balance",
        color=discord.Color.green(),
        thumbnail=member.display_avatar.url
    )
    embed.add_field(name="Wallet", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['balance']:,}", inline=True)
    embed.add_field(name="Bank", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['bank']:,}", inline=True)
    embed.add_field(name="Total", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['balance'] + data['bank']:,}", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def daily(ctx):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    now = datetime.datetime.utcnow()
    last_claimed = data.get("daily_claimed")
    if last_claimed:
        last_claimed = datetime.datetime.fromisoformat(last_claimed)
        if (now - last_claimed).total_seconds() < 86400:
            next_claim = last_claimed + datetime.timedelta(days=1)
            return await ctx.send(f"❌ You already claimed your daily! Next claim: <t:{int(next_claim.timestamp())}:R>")
    amount = CONFIG["DAILY_AMOUNT"]
    await update_user_data(
        ctx.author.id, ctx.guild.id,
        balance=data["balance"] + amount,
        daily_claimed=now.isoformat()
    )
    await ctx.send(f"✅ You claimed your daily reward of {CONFIG['CURRENCY_SYMBOL']} **{amount}**!")

@bot.command()
async def work(ctx):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    now = datetime.datetime.utcnow()
    last_worked = data.get("work_claimed")
    if last_worked:
        last_worked = datetime.datetime.fromisoformat(last_worked)
        if (now - last_worked).total_seconds() < CONFIG["WORK_COOLDOWN"]:
            next_work = last_worked + datetime.timedelta(seconds=CONFIG["WORK_COOLDOWN"])
            return await ctx.send(f"❌ You're tired! Rest until <t:{int(next_work.timestamp())}:R>")
    jobs = [
        "programmed a website", "delivered packages", "taught a class",
        "fixed computers", "walked dogs", "cleaned houses",
        "drove a taxi", "cooked meals", "wrote articles"
    ]
    amount = random.randint(CONFIG["WORK_MIN"], CONFIG["WORK_MAX"])
    await update_user_data(
        ctx.author.id, ctx.guild.id,
        balance=data["balance"] + amount,
        work_claimed=now.isoformat()
    )
    await ctx.send(f"💼 You {random.choice(jobs)} and earned {CONFIG['CURRENCY_SYMBOL']} **{amount}**!")

@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("❌ Invalid amount!")
    if member == ctx.author:
        return await ctx.send("❌ You can't pay yourself!")
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    if data["balance"] < amount:
        return await ctx.send("❌ You don't have enough money!")
    target_data = await get_user_data(member.id, ctx.guild.id)
    await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] - amount)
    await update_user_data(member.id, ctx.guild.id, balance=target_data["balance"] + amount)
    await ctx.send(f"✅ You paid {member.mention} {CONFIG['CURRENCY_SYMBOL']} **{amount}**")

@bot.command(aliases=["dep"])
async def deposit(ctx, amount: str):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    if amount.lower() == "all":
        amount = data["balance"]
    else:
        amount = int(amount)
    if amount <= 0:
        return await ctx.send("❌ Invalid amount!")
    if data["balance"] < amount:
        return await ctx.send("❌ You don't have enough money!")
    await update_user_data(
        ctx.author.id, ctx.guild.id,
        balance=data["balance"] - amount,
        bank=data["bank"] + amount
    )
    await ctx.send(f"✅ Deposited {CONFIG['CURRENCY_SYMBOL']} **{amount}** to your bank!")

@bot.command(aliases=["with"])
async def withdraw(ctx, amount: str):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    if amount.lower() == "all":
        amount = data["bank"]
    else:
        amount = int(amount)
    if amount <= 0:
        return await ctx.send("❌ Invalid amount!")
    if data["bank"] < amount:
        return await ctx.send("❌ You don't have enough in your bank!")
    await update_user_data(
        ctx.author.id, ctx.guild.id,
        balance=data["balance"] + amount,
        bank=data["bank"] - amount
    )
    await ctx.send(f"✅ Withdrew {CONFIG['CURRENCY_SYMBOL']} **{amount}** from your bank!")

@bot.command()
async def rob(ctx, member: discord.Member):
    if member == ctx.author:
        return await ctx.send("❌ You can't rob yourself!")
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    target_data = await get_user_data(member.id, ctx.guild.id)
    if target_data["balance"] < 100:
        return await ctx.send("❌ That person doesn't have enough to rob!")
    if random.random() < 0.4:
        amount = random.randint(1, min(target_data["balance"], 500))
        await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] + amount)
        await update_user_data(member.id, ctx.guild.id, balance=target_data["balance"] - amount)
        await ctx.send(f"💰 You successfully robbed {CONFIG['CURRENCY_SYMBOL']} **{amount}** from {member.mention}!")
    else:
        fine = random.randint(50, 200)
        await update_user_data(ctx.author.id, ctx.guild.id, balance=max(0, data["balance"] - fine))
        await ctx.send(f"👮 You got caught and paid a fine of {CONFIG['CURRENCY_SYMBOL']} **{fine}**!")

@bot.command()
async def slots(ctx, amount: int):
    if amount <= 0:
        return await ctx.send("❌ Invalid amount!")
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    if data["balance"] < amount:
        return await ctx.send("❌ You don't have enough money!")
    symbols = ["🍎", "🍊", "🍇", "🍒", "💎", "7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]
    if result[0] == result[1] == result[2]:
        if result[0] == "💎": winnings = amount * 10
        elif result[0] == "7️⃣": winnings = amount * 7
        else: winnings = amount * 5
        message = f"🎰 | {' '.join(result)} | 🎰\n\n🎉 **JACKPOT!** You won {CONFIG['CURRENCY_SYMBOL']} **{winnings}**!"
        await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] + winnings - amount)
    elif result[0] == result[1] or result[1] == result[2]:
        winnings = amount * 2
        message = f"🎰 | {' '.join(result)} | 🎰\n\n✨ Two in a row! You won {CONFIG['CURRENCY_SYMBOL']} **{winnings}**!"
        await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] + winnings - amount)
    else:
        message = f"🎰 | {' '.join(result)} | 🎰\n\n😢 You lost {CONFIG['CURRENCY_SYMBOL']} **{amount}**!"
        await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] - amount)
    await ctx.send(message)

@bot.command()
async def gamble(ctx, amount: int):
    if amount <= 0:
        return await ctx.send("❌ Invalid amount!")
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    if data["balance"] < amount:
        return await ctx.send("❌ You don't have enough money!")
    if random.random() < 0.45:
        winnings = int(amount * random.uniform(1.5, 2.5))
        await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] + winnings - amount)
        await ctx.send(f"🎲 You won {CONFIG['CURRENCY_SYMBOL']} **{winnings}**! 🎉")
    else:
        await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] - amount)
        await ctx.send(f"🎲 You lost {CONFIG['CURRENCY_SYMBOL']} **{amount}**! 😢")

@bot.command()
async def baltop(ctx, page: int = 1):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT user_id, balance + bank as total FROM users WHERE guild_id = ? ORDER BY total DESC LIMIT 10 OFFSET ?",
            (ctx.guild.id, (page - 1) * 10)
        )
        rows = await cursor.fetchall()
    if not rows:
        return await ctx.send("❌ No data found.")
    description = ""
    for i, (user_id, total) in enumerate(rows, start=(page - 1) * 10 + 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
        description += f"{medal} <@{user_id}> - {CONFIG['CURRENCY_SYMBOL']} {total:,}\n"
    embed = create_embed(
        title=f"💰 Richest Members - Page {page}",
        description=description,
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


# ══════════════════════════════════════════════════════════════════════════════
# DYNAMIC MARKETPLACE - NEW
# ══════════════════════════════════════════════════════════════════════════════

@bot.command(aliases=["shop"])
async def market(ctx, category: str = None, page: int = 1):
    async with aiosqlite.connect("bot_database.db") as db:
        if category:
            cursor = await db.execute(
                "SELECT * FROM market_items WHERE LOWER(category) = ? ORDER BY current_price ASC",
                (category.lower(),)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM market_items ORDER BY category, current_price ASC"
            )
        items = await cursor.fetchall()

    if not items:
        return await ctx.send("❌ No items found!" + (f" Category `{category}` doesn't exist." if category else ""))

    pages = []
    items_per_page = 10
    total_pages = math.ceil(len(items) / items_per_page)

    for pg in range(total_pages):
        start = pg * items_per_page
        end = start + items_per_page
        page_items = items[start:end]

        description = ""
        for item in page_items:
            price = round(item[6])
            base = item[5]
            change = "📈" if price > base else "📉" if price < base else "➡️"
            rarity_icons = {"common": "⬜", "uncommon": "🟩", "rare": "🟦", "epic": "🟪", "legendary": "🟨"}
            rarity_icon = rarity_icons.get(item[9], "⬜")
            description += (
                f"{rarity_icon} `#{item[0]:>3}` {item[4]} **{item[1]}** — "
                f"{CONFIG['CURRENCY_SYMBOL']} **{price:,}** {change}\n"
            )

        embed = create_embed(
            title=f"🛒 Marketplace" + (f" — {category.title()}" if category else ""),
            description=description,
            color=discord.Color.teal(),
            footer=f"Page {pg + 1}/{total_pages} | !mbuy <id> [qty] | !msell <id> [qty]"
        )
        pages.append(embed)

    if page > len(pages):
        page = len(pages)
    view = MarketPageView(pages, current_page=page - 1, author_id=ctx.author.id) if len(pages) > 1 else None
    await ctx.send(embed=pages[page - 1], view=view)


@bot.command()
async def mcategories(ctx):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT DISTINCT category, COUNT(*) FROM market_items GROUP BY category ORDER BY category"
        )
        cats = await cursor.fetchall()

    if not cats:
        return await ctx.send("❌ No categories found.")

    cat_emojis = {
        "fish": "🐟", "minerals": "💎", "food": "🍕", "tools": "⛏️",
        "collectibles": "🃏", "tech": "💻", "premium": "🌐",
        "nature": "🌿", "magic": "🔮", "vehicles": "🚗", "pets": "🐾"
    }
    description = ""
    for cat, count in cats:
        emoji = cat_emojis.get(cat, "📦")
        description += f"{emoji} **{cat.title()}** — {count} items\n"
    description += f"\nUse `!market <category>` to browse!"

    embed = create_embed(title="📂 Market Categories", description=description, color=discord.Color.teal())
    await ctx.send(embed=embed)


@bot.command()
async def minfo(ctx, item_id: int):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute("SELECT * FROM market_items WHERE item_id = ?", (item_id,))
        item = await cursor.fetchone()

    if not item:
        return await ctx.send("❌ Item not found!")

    price = round(item[6])
    base = item[5]
    change_pct = ((price - base) / base * 100) if base > 0 else 0

    embed = create_embed(
        title=f"{item[4]} {item[1]}", description=item[3], color=get_rarity_color(item[9])
    )
    embed.add_field(name="Category", value=item[2].title(), inline=True)
    embed.add_field(name="Rarity", value=item[9].title(), inline=True)
    embed.add_field(name="Tradeable", value="Yes" if item[10] else "No", inline=True)
    embed.add_field(name="Base Price", value=f"{CONFIG['CURRENCY_SYMBOL']} {base:,}", inline=True)
    embed.add_field(name="Current Price", value=f"{CONFIG['CURRENCY_SYMBOL']} {price:,}", inline=True)
    embed.add_field(name="Price Change", value=f"{change_pct:+.1f}%", inline=True)
    embed.add_field(name="Total Bought", value=f"{item[7]:,}", inline=True)
    embed.add_field(name="Total Sold", value=f"{item[8]:,}", inline=True)
    embed.set_footer(text=f"Item ID: {item[0]}")
    await ctx.send(embed=embed)


@bot.command()
async def mbuy(ctx, item_id: int, quantity: int = 1):
    if quantity <= 0:
        return await ctx.send("❌ Quantity must be positive!")

    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute("SELECT * FROM market_items WHERE item_id = ?", (item_id,))
        item = await cursor.fetchone()
        if not item:
            return await ctx.send("❌ Item not found!")

        price_per = round(item[6])
        total_cost = price_per * quantity
        user_data = await get_user_data(ctx.author.id, ctx.guild.id)
        if user_data["balance"] < total_cost:
            return await ctx.send(
                f"❌ Not enough {CONFIG['CURRENCY_NAME']}! "
                f"Need {CONFIG['CURRENCY_SYMBOL']} **{total_cost:,}**, "
                f"you have {CONFIG['CURRENCY_SYMBOL']} **{user_data['balance']:,}**"
            )

        await update_user_data(ctx.author.id, ctx.guild.id, balance=user_data["balance"] - total_cost)
        await db.execute(
            """INSERT INTO user_items (user_id, guild_id, item_id, quantity)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, guild_id, item_id)
               DO UPDATE SET quantity = quantity + ?""",
            (ctx.author.id, ctx.guild.id, item_id, quantity, quantity)
        )
        new_bought = item[7] + quantity
        new_price = calculate_market_price(item[5], new_bought, item[8])
        await db.execute(
            "UPDATE market_items SET total_bought = ?, current_price = ? WHERE item_id = ?",
            (new_bought, new_price, item_id)
        )
        await db.commit()

    embed = create_embed(
        title="✅ Purchase Successful!",
        description=(
            f"Bought **{quantity}x** {item[4]} **{item[1]}**\n"
            f"for {CONFIG['CURRENCY_SYMBOL']} **{total_cost:,}**\n\n"
            f"New market price: {CONFIG['CURRENCY_SYMBOL']} **{round(new_price):,}** 📈"
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.command()
async def msell(ctx, item_id: int, quantity: int = 1):
    if quantity <= 0:
        return await ctx.send("❌ Quantity must be positive!")

    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT quantity FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (ctx.author.id, ctx.guild.id, item_id)
        )
        row = await cursor.fetchone()
        if not row or row[0] < quantity:
            return await ctx.send(f"❌ You don't have enough! (You have {row[0] if row else 0})")

        cursor = await db.execute("SELECT * FROM market_items WHERE item_id = ?", (item_id,))
        item = await cursor.fetchone()
        if not item:
            return await ctx.send("❌ Item not found!")

        sell_price = round(item[6] * 0.7) * quantity
        new_qty = row[0] - quantity
        if new_qty <= 0:
            await db.execute(
                "DELETE FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                (ctx.author.id, ctx.guild.id, item_id)
            )
        else:
            await db.execute(
                "UPDATE user_items SET quantity = ? WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                (new_qty, ctx.author.id, ctx.guild.id, item_id)
            )

        user_data = await get_user_data(ctx.author.id, ctx.guild.id)
        await update_user_data(ctx.author.id, ctx.guild.id, balance=user_data["balance"] + sell_price)

        new_sold = item[8] + quantity
        new_price = calculate_market_price(item[5], item[7], new_sold)
        await db.execute(
            "UPDATE market_items SET total_sold = ?, current_price = ? WHERE item_id = ?",
            (new_sold, new_price, item_id)
        )
        await db.commit()

    embed = create_embed(
        title="✅ Sold Successfully!",
        description=(
            f"Sold **{quantity}x** {item[4]} **{item[1]}**\n"
            f"for {CONFIG['CURRENCY_SYMBOL']} **{sell_price:,}** (70% of market)\n\n"
            f"New market price: {CONFIG['CURRENCY_SYMBOL']} **{round(new_price):,}** 📉"
        ),
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)


@bot.command()
async def minv(ctx, member: discord.Member = None):
    member = member or ctx.author
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            """SELECT ui.quantity, mi.name, mi.emoji, mi.rarity, mi.item_id, mi.current_price
               FROM user_items ui
               JOIN market_items mi ON ui.item_id = mi.item_id
               WHERE ui.user_id = ? AND ui.guild_id = ?
               ORDER BY mi.category, mi.name""",
            (member.id, ctx.guild.id)
        )
        items = await cursor.fetchall()

    if not items:
        return await ctx.send(f"❌ {member.name}'s market inventory is empty!")

    description = ""
    total_value = 0
    for qty, name, emoji, rarity, item_id, price in items:
        value = round(price * 0.7) * qty
        total_value += value
        rarity_icons = {"common": "⬜", "uncommon": "🟩", "rare": "🟦", "epic": "🟪", "legendary": "🟨"}
        ri = rarity_icons.get(rarity, "⬜")
        description += f"{ri} {emoji} **{name}** x{qty} — ~{CONFIG['CURRENCY_SYMBOL']} {value:,}\n"

    description += f"\n**Total sell value:** {CONFIG['CURRENCY_SYMBOL']} {total_value:,}"
    embed = create_embed(
        title=f"🎒 {member.name}'s Market Inventory",
        description=description, color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

# ══════════════════════════════════════════════════════════════════════════════
# TRADING SYSTEM - NEW
# ══════════════════════════════════════════════════════════════════════════════

@bot.command()
async def trade(ctx, member: discord.Member, item_id: int, quantity: int = 1, price: int = 0):
    """Offer a trade to another player. !trade @user <item_id> <qty> <price>"""
    if member == ctx.author:
        return await ctx.send("❌ You can't trade with yourself!")
    if member.bot:
        return await ctx.send("❌ You can't trade with bots!")
    if quantity <= 0:
        return await ctx.send("❌ Quantity must be positive!")
    if price < 0:
        return await ctx.send("❌ Price can't be negative!")

    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT quantity FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (ctx.author.id, ctx.guild.id, item_id)
        )
        row = await cursor.fetchone()

        if not row or row[0] < quantity:
            return await ctx.send(f"❌ You don't have enough! (You have {row[0] if row else 0})")

        cursor = await db.execute("SELECT name, emoji FROM market_items WHERE item_id = ?", (item_id,))
        item = await cursor.fetchone()
        if not item:
            return await ctx.send("❌ Item not found!")

        await db.execute(
            """INSERT INTO trades (guild_id, sender_id, receiver_id, item_id, quantity, price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ctx.guild.id, ctx.author.id, member.id, item_id, quantity, price)
        )
        await db.commit()

        cursor = await db.execute("SELECT last_insert_rowid()")
        trade_id = (await cursor.fetchone())[0]

    price_text = f"for {CONFIG['CURRENCY_SYMBOL']} **{price:,}**" if price > 0 else "**for free**"

    embed = create_embed(
        title="🤝 Trade Offer!",
        description=(
            f"{ctx.author.mention} wants to trade with {member.mention}!\n\n"
            f"**Offering:** {quantity}x {item[1]} **{item[0]}**\n"
            f"**Price:** {price_text}\n\n"
            f"Use `!tradeaccept {trade_id}` to accept\n"
            f"Use `!tradedecline {trade_id}` to decline"
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)


@bot.command()
async def trades(ctx):
    """View your pending trades"""
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            """SELECT t.id, t.sender_id, t.receiver_id, t.quantity, t.price, mi.name, mi.emoji
               FROM trades t
               JOIN market_items mi ON t.item_id = mi.item_id
               WHERE (t.sender_id = ? OR t.receiver_id = ?) AND t.guild_id = ? AND t.status = 'pending'
               ORDER BY t.created_at DESC LIMIT 15""",
            (ctx.author.id, ctx.author.id, ctx.guild.id)
        )
        trade_list = await cursor.fetchall()

    if not trade_list:
        return await ctx.send("❌ You have no pending trades.")

    description = ""
    for tid, sender, receiver, qty, price, name, emoji in trade_list:
        direction = "📤 Outgoing" if sender == ctx.author.id else "📥 Incoming"
        other = f"<@{receiver}>" if sender == ctx.author.id else f"<@{sender}>"
        price_text = f"{CONFIG['CURRENCY_SYMBOL']} {price:,}" if price > 0 else "Free"
        description += f"`#{tid}` {direction} → {other}: **{qty}x** {emoji} {name} ({price_text})\n"

    embed = create_embed(
        title="📋 Your Pending Trades",
        description=description,
        color=discord.Color.blue(),
        footer="Use !tradeaccept <id> or !tradedecline <id>"
    )
    await ctx.send(embed=embed)


@bot.command()
async def tradeaccept(ctx, trade_id: int):
    """Accept a trade offer"""
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM trades WHERE id = ? AND receiver_id = ? AND guild_id = ? AND status = 'pending'",
            (trade_id, ctx.author.id, ctx.guild.id)
        )
        trade_data = await cursor.fetchone()

    if not trade_data:
        return await ctx.send("❌ Trade not found or you're not the receiver!")

    # 0=id, 1=guild_id, 2=sender_id, 3=receiver_id, 4=item_id, 5=quantity, 6=price, 7=status
    sender_id = trade_data[2]
    item_id = trade_data[4]
    quantity = trade_data[5]
    price = trade_data[6]

    async with aiosqlite.connect("bot_database.db") as db:
        # Verify sender still has items
        cursor = await db.execute(
            "SELECT quantity FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (sender_id, ctx.guild.id, item_id)
        )
        sender_items = await cursor.fetchone()

        if not sender_items or sender_items[0] < quantity:
            await db.execute("UPDATE trades SET status = 'cancelled' WHERE id = ?", (trade_id,))
            await db.commit()
            return await ctx.send("❌ Sender no longer has enough items. Trade cancelled.")

        # Check receiver has enough money if price > 0
        if price > 0:
            receiver_data = await get_user_data(ctx.author.id, ctx.guild.id)
            if receiver_data["balance"] < price:
                return await ctx.send(
                    f"❌ You don't have enough {CONFIG['CURRENCY_NAME']}! "
                    f"Need {CONFIG['CURRENCY_SYMBOL']} {price:,}"
                )

            # Transfer money
            sender_data = await get_user_data(sender_id, ctx.guild.id)
            await update_user_data(ctx.author.id, ctx.guild.id, balance=receiver_data["balance"] - price)
            await update_user_data(sender_id, ctx.guild.id, balance=sender_data["balance"] + price)

        # Transfer items: remove from sender
        new_sender_qty = sender_items[0] - quantity
        if new_sender_qty <= 0:
            await db.execute(
                "DELETE FROM user_items WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                (sender_id, ctx.guild.id, item_id)
            )
        else:
            await db.execute(
                "UPDATE user_items SET quantity = ? WHERE user_id = ? AND guild_id = ? AND item_id = ?",
                (new_sender_qty, sender_id, ctx.guild.id, item_id)
            )

        # Add to receiver
        await db.execute(
            """INSERT INTO user_items (user_id, guild_id, item_id, quantity)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, guild_id, item_id)
               DO UPDATE SET quantity = quantity + ?""",
            (ctx.author.id, ctx.guild.id, item_id, quantity, quantity)
        )

        # Update trade status
        await db.execute(
            "UPDATE trades SET status = 'accepted', resolved_at = ? WHERE id = ?",
            (datetime.datetime.utcnow().isoformat(), trade_id)
        )
        await db.commit()

    # Get item name for message
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute("SELECT name, emoji FROM market_items WHERE item_id = ?", (item_id,))
        item = await cursor.fetchone()

    price_msg = f" for {CONFIG['CURRENCY_SYMBOL']} **{price:,}**" if price > 0 else " for free"
    await ctx.send(
        f"✅ Trade #{trade_id} completed! {ctx.author.mention} received "
        f"**{quantity}x** {item[1]} **{item[0]}** from <@{sender_id}>{price_msg}!"
    )


@bot.command()
async def tradedecline(ctx, trade_id: int):
    """Decline a trade offer"""
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM trades WHERE id = ? AND (receiver_id = ? OR sender_id = ?) AND guild_id = ? AND status = 'pending'",
            (trade_id, ctx.author.id, ctx.author.id, ctx.guild.id)
        )
        trade_data = await cursor.fetchone()

    if not trade_data:
        return await ctx.send("❌ Trade not found!")

    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "UPDATE trades SET status = 'declined', resolved_at = ? WHERE id = ?",
            (datetime.datetime.utcnow().isoformat(), trade_id)
        )
        await db.commit()

    await ctx.send(f"✅ Trade #{trade_id} has been declined.")

