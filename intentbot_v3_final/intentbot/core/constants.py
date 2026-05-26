# ══════════════════════════════════════════════════════════════════════════════
#                       Intent™ BOT v3.0 — Constants
# ══════════════════════════════════════════════════════════════════════════════

import discord

BOT_VERSION = "3.0.0"
BOT_NAME = "Intent™ BOT"
UPDATE_CHECK_URL = "https://update.bot.int.yt"
DB_PATH = "data/database.db"
LOG_DIR = "logs"
BACKUP_DIR = "data/backups"

# ─── Rarity system ────────────────────────────────────────────────────────────
RARITY_COLORS: dict[str, discord.Color] = {
    "common":    discord.Color.light_grey(),
    "uncommon":  discord.Color.green(),
    "rare":      discord.Color.blue(),
    "epic":      discord.Color.purple(),
    "legendary": discord.Color.gold(),
}

RARITY_STARS: dict[str, str] = {
    "common":    "⚪",
    "uncommon":  "🟢",
    "rare":      "🔵",
    "epic":      "🟣",
    "legendary": "🟡",
}

# ─── Market item catalog ──────────────────────────────────────────────────────
# (name, category, description, emoji, base_price, rarity)
MARKET_ITEMS: list[tuple] = [
    # Fish & Sea
    ("Sardine",        "fish",       "A tiny common fish",           "🐟", 10,    "common"),
    ("Salmon",         "fish",       "A healthy pink fish",          "🐟", 45,    "common"),
    ("Tuna",           "fish",       "A big ocean fish",             "🐟", 80,    "uncommon"),
    ("Swordfish",      "fish",       "A powerful predator fish",     "⚔️",  200,   "rare"),
    ("Golden Koi",     "fish",       "A legendary golden fish",      "✨",  1500,  "legendary"),
    ("Pufferfish",     "fish",       "Cute but deadly",              "🐡", 120,   "uncommon"),
    ("Octopus",        "fish",       "Eight-armed sea creature",     "🐙", 250,   "rare"),
    ("Whale",          "fish",       "The biggest catch possible",   "🐋", 5000,  "legendary"),
    ("Shrimp",         "fish",       "Tiny but tasty",               "🦐", 15,    "common"),
    ("Lobster",        "fish",       "A fancy red crustacean",       "🦞", 300,   "rare"),
    ("Crab",           "fish",       "A snappy little fella",        "🦀", 60,    "common"),
    ("Jellyfish",      "fish",       "Beautiful and dangerous",      "🪼", 90,    "uncommon"),
    # Minerals & Gems
    ("Coal",           "minerals",   "A chunk of coal",              "⚫", 5,     "common"),
    ("Iron Ore",       "minerals",   "Raw iron ore",                 "🪨", 25,    "common"),
    ("Copper Ore",     "minerals",   "Shiny copper ore",             "🟤", 30,    "common"),
    ("Silver Ore",     "minerals",   "Gleaming silver ore",          "⚪", 80,    "uncommon"),
    ("Gold Ore",       "minerals",   "Precious gold ore",            "🟡", 200,   "rare"),
    ("Diamond",        "minerals",   "A brilliant diamond",          "💎", 1000,  "epic"),
    ("Emerald",        "minerals",   "A vivid green gem",            "💚", 800,   "epic"),
    ("Ruby",           "minerals",   "A fiery red gem",              "❤️",  850,   "epic"),
    ("Sapphire",       "minerals",   "A deep blue gem",              "💙", 900,   "epic"),
    ("Amethyst",       "minerals",   "A purple crystal",             "💜", 400,   "rare"),
    ("Obsidian",       "minerals",   "Volcanic glass",               "🖤", 150,   "uncommon"),
    ("Meteorite",      "minerals",   "Fragment from space",          "☄️",  3000,  "legendary"),
    # Food & Cooking
    ("Apple",          "food",       "A fresh red apple",            "🍎", 8,     "common"),
    ("Banana",         "food",       "A ripe banana",                "🍌", 6,     "common"),
    ("Pizza Slice",    "food",       "Cheesy goodness",              "🍕", 25,    "common"),
    ("Burger",         "food",       "A juicy burger",               "🍔", 30,    "common"),
    ("Sushi Roll",     "food",       "Artisanal sushi",              "🍣", 75,    "uncommon"),
    ("Steak",          "food",       "Premium wagyu steak",          "🥩", 150,   "rare"),
    ("Cake",           "food",       "A delicious cake",             "🎂", 60,    "uncommon"),
    ("Cookie",         "food",       "Warm chocolate chip cookie",   "🍪", 12,    "common"),
    ("Ramen",          "food",       "Hot bowl of ramen",            "🍜", 40,    "common"),
    ("Golden Apple",   "food",       "A mythical golden apple",      "🍏", 2000,  "legendary"),
    ("Taco",           "food",       "A crunchy taco",               "🌮", 20,    "common"),
    ("Ice Cream",      "food",       "Cold and sweet",               "🍦", 15,    "common"),
    # Tools & Equipment
    ("Wooden Pickaxe", "tools",      "A basic pickaxe",              "⛏️",  50,    "common"),
    ("Iron Pickaxe",   "tools",      "A sturdy pickaxe",             "⛏️",  200,   "uncommon"),
    ("Diamond Pickaxe","tools",      "The best pickaxe",             "⛏️",  1500,  "epic"),
    ("Fishing Rod",    "tools",      "A basic fishing rod",          "🎣", 40,    "common"),
    ("Golden Rod",     "tools",      "Catches rare fish easier",     "🎣", 800,   "rare"),
    ("Shovel",         "tools",      "For digging treasures",        "🔧", 35,    "common"),
    ("Axe",            "tools",      "A sharp woodcutting axe",      "🪓", 45,    "common"),
    ("Telescope",      "tools",      "See the stars",                "🔭", 300,   "rare"),
    ("Compass",        "tools",      "Never get lost",               "🧭", 100,   "uncommon"),
    ("Lantern",        "tools",      "Lights your way",              "🏮", 60,    "common"),
    # Collectibles
    ("Common Card",    "collectibles","A common trading card",       "🃏", 20,    "common"),
    ("Rare Card",      "collectibles","A rare trading card",         "🃏", 200,   "rare"),
    ("Legendary Card", "collectibles","A legendary trading card",    "🃏", 2000,  "legendary"),
    ("Trophy",         "collectibles","A shiny trophy",              "🏆", 500,   "epic"),
    ("Crown",          "collectibles","A royal crown",               "👑", 3000,  "legendary"),
    ("Medal",          "collectibles","A medal of honor",            "🏅", 250,   "rare"),
    ("Gem Stone",      "collectibles","A mysterious gem",            "💠", 400,   "rare"),
    ("Star Fragment",  "collectibles","Fallen from the sky",         "⭐", 600,   "epic"),
    ("Ancient Coin",   "collectibles","A coin from ancient times",   "🪙", 350,   "rare"),
    ("Lucky Clover",   "collectibles","Brings good fortune",         "🍀", 150,   "uncommon"),
    # Tech & Digital
    ("USB Drive",      "tech",       "4GB storage device",           "💾", 30,    "common"),
    ("SSD Drive",      "tech",       "Fast storage",                 "💿", 200,   "uncommon"),
    ("Graphics Card",  "tech",       "RTX quality",                  "🖥️",  800,   "rare"),
    ("Laptop",         "tech",       "A portable computer",          "💻", 1200,  "epic"),
    ("Smartphone",     "tech",       "Latest model phone",           "📱", 600,   "rare"),
    ("Server Rack",    "tech",       "Enterprise server",            "🖥️",  3000,  "legendary"),
    ("Robot",          "tech",       "A tiny robot companion",       "🤖", 2500,  "legendary"),
    ("Satellite",      "tech",       "Your own satellite",           "📡", 5000,  "legendary"),
    ("Drone",          "tech",       "A flying drone",               "🛸", 400,   "rare"),
    ("VR Headset",     "tech",       "Virtual reality device",       "🥽", 500,   "rare"),
    # Premium Digital
    (".com Domain",    "premium",    "A .com domain name",           "🌐", 1500,  "epic"),
    (".io Domain",     "premium",    "A .io domain name",            "🌐", 2000,  "epic"),
    (".gg Domain",     "premium",    "A .gg domain name",            "🌐", 2500,  "legendary"),
    (".dev Domain",    "premium",    "A .dev domain name",           "🌐", 1800,  "epic"),
    ("Nitro Classic",  "premium",    "Discord Nitro Classic",        "💎", 3000,  "legendary"),
    ("Nitro Full",     "premium",    "Discord Nitro Full",           "💎", 5000,  "legendary"),
    ("Premium Badge",  "premium",    "An exclusive badge",           "🏷️",  4000,  "legendary"),
    ("Custom Bot",     "premium",    "Your own custom bot",          "🤖", 8000,  "legendary"),
    ("Private Server", "premium",    "Your own game server",         "🖥️",  6000,  "legendary"),
    ("NFT Certificate","premium",    "A unique certificate",         "📜", 1000,  "epic"),
    # Nature & Plants
    ("Oak Seed",       "nature",     "Grow an oak tree",             "🌰", 10,    "common"),
    ("Rose",           "nature",     "A beautiful red rose",         "🌹", 30,    "common"),
    ("Sunflower",      "nature",     "A bright sunflower",           "🌻", 20,    "common"),
    ("Bonsai Tree",    "nature",     "A tiny perfect tree",          "🌳", 300,   "rare"),
    ("Venus Flytrap",  "nature",     "A carnivorous plant",          "🪴", 150,   "uncommon"),
    ("Mushroom",       "nature",     "A forest mushroom",            "🍄", 15,    "common"),
    ("Cactus",         "nature",     "A prickly cactus",             "🌵", 25,    "common"),
    ("Cherry Blossom", "nature",     "A delicate blossom",           "🌸", 100,   "uncommon"),
    ("Four Leaf Clover","nature",    "Very lucky find",              "🍀", 500,   "epic"),
    ("World Tree Seed","nature",     "A mythical seed",              "🌲", 10000, "legendary"),
    # Potions & Magic
    ("Health Potion",  "magic",      "Restores vitality",            "🧪", 50,    "common"),
    ("Mana Potion",    "magic",      "Restores energy",              "🧪", 50,    "common"),
    ("Speed Potion",   "magic",      "Makes you faster",             "⚡", 120,   "uncommon"),
    ("Luck Potion",    "magic",      "Increases luck",               "🍀", 300,   "rare"),
    ("Invisibility",   "magic",      "Become invisible",             "👻", 500,   "epic"),
    ("Love Potion",    "magic",      "Smells like roses",            "💕", 200,   "rare"),
    ("Dragon Scale",   "magic",      "From a real dragon",           "🐉", 2000,  "legendary"),
    ("Phoenix Feather","magic",      "Burns eternally",              "🪶", 3000,  "legendary"),
    ("Wizard Hat",     "magic",      "Pointy and magical",           "🧙", 400,   "rare"),
    ("Crystal Ball",   "magic",      "See the future",               "🔮", 600,   "epic"),
    # Vehicles
    ("Bicycle",        "vehicles",   "A simple bicycle",             "🚲", 100,   "common"),
    ("Motorcycle",     "vehicles",   "A fast motorcycle",            "🏍️",  500,   "rare"),
    ("Sports Car",     "vehicles",   "A sleek sports car",           "🏎️",  3000,  "legendary"),
    ("Yacht",          "vehicles",   "A luxury yacht",               "🛥️",  8000,  "legendary"),
    ("Helicopter",     "vehicles",   "A private helicopter",         "🚁", 6000,  "legendary"),
    ("Rocket",         "vehicles",   "To the moon!",                 "🚀", 15000, "legendary"),
    ("Skateboard",     "vehicles",   "A cool skateboard",            "🛹", 40,    "common"),
    ("Sailboat",       "vehicles",   "A sailing boat",               "⛵", 800,   "rare"),
    ("Hot Air Balloon","vehicles",   "Float in the sky",             "🎈", 1200,  "epic"),
    ("Submarine",      "vehicles",   "Explore the deep",             "🛟", 5000,  "legendary"),
    # Pets
    ("Kitten",         "pets",       "A cute little kitten",         "🐱", 200,   "uncommon"),
    ("Puppy",          "pets",       "A loyal puppy",                "🐶", 200,   "uncommon"),
    ("Hamster",        "pets",       "A tiny hamster",               "🐹", 80,    "common"),
    ("Parrot",         "pets",       "A colorful parrot",            "🦜", 300,   "rare"),
    ("Bunny",          "pets",       "A fluffy bunny",               "🐰", 150,   "uncommon"),
    ("Turtle",         "pets",       "A wise old turtle",            "🐢", 100,   "common"),
    ("Fox",            "pets",       "A clever fox",                 "🦊", 500,   "rare"),
    ("Owl",            "pets",       "A wise owl",                   "🦉", 400,   "rare"),
    ("Dragon Egg",     "pets",       "May hatch someday",            "🥚", 5000,  "legendary"),
    ("Unicorn",        "pets",       "A mythical unicorn",           "🦄", 10000, "legendary"),
]

# ─── Default per-guild settings ───────────────────────────────────────────────
DEFAULT_GUILD_SETTINGS: dict = {
    "prefix":              "!",
    "welcome_channel":     None,
    "leave_channel":       None,
    "log_channel":         None,
    "level_up_channel":    None,
    "ticket_category":     None,
    "mute_role":           None,
    "auto_role":           None,
    "dj_role":             None,
    # Feature toggles
    "welcome_enabled":     True,
    "leave_enabled":       True,
    "leveling_enabled":    True,
    "economy_enabled":     True,
    "automod_enabled":     True,
    "logging_enabled":     True,
    # Automod
    "anti_spam_enabled":   True,
    "anti_link_enabled":   False,
    "max_mentions":        5,
    "spam_threshold":      5,
    "spam_interval":       5,
    "banned_words":        [],
    "link_whitelist":      [],
    # Economy
    "currency_name":       "coins",
    "currency_symbol":     "🪙",
    "daily_amount":        100,
    "work_min":            50,
    "work_max":            200,
    # Leveling
    "xp_per_message_min":  15,
    "xp_per_message_max":  25,
    "xp_cooldown":         60,
    "level_up_message":    "🎉 {user} reached level **{level}**!",
    # Welcome/Leave messages
    "welcome_message":     "Welcome to **{server}**, {user}! You are member #{count}.",
    "leave_message":       "**{username}** has left the server. We now have {count} members.",
}

# ─── Status rotation messages ─────────────────────────────────────────────────
STATUS_MESSAGES: list[str] = [
    "Intent™ BOT v3.0",
    "Serving {guilds} servers",
    "!help | /help",
    "Type /help for commands",
    "Multi-server • Scalable",
]

# ─── Work responses ───────────────────────────────────────────────────────────
WORK_RESPONSES: list[str] = [
    "You delivered packages and earned {amount} {symbol}!",
    "You fixed some bugs and earned {amount} {symbol}!",
    "You drove a taxi and earned {amount} {symbol}!",
    "You walked dogs and earned {amount} {symbol}!",
    "You wrote code all night and earned {amount} {symbol}!",
    "You mined crypto and earned {amount} {symbol}!",
    "You flipped burgers and earned {amount} {symbol}!",
    "You streamed games and earned {amount} {symbol}!",
    "You sold lemonade and earned {amount} {symbol}!",
    "You tutored students and earned {amount} {symbol}!",
]

# ─── Fun facts ────────────────────────────────────────────────────────────────
FUN_FACTS: list[str] = [
    "A group of flamingos is called a flamboyance.",
    "Honey never spoils — archaeologists have found 3000-year-old honey in Egyptian tombs.",
    "Octopuses have three hearts and blue blood.",
    "Bananas are technically berries, but strawberries are not.",
    "A day on Venus is longer than a year on Venus.",
    "Cleopatra lived closer to the Moon landing than to the construction of the Great Pyramid.",
    "The shortest war in history lasted only 38–45 minutes.",
    "Water can boil and freeze at the same time under the right pressure.",
    "There are more possible chess games than atoms in the observable universe.",
    "Sharks are older than trees.",
]

# ─── 8-ball responses ─────────────────────────────────────────────────────────
EIGHTBALL_RESPONSES: list[str] = [
    "It is certain.", "Without a doubt.", "Yes, definitely.", "You may rely on it.",
    "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.",
    "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
    "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]
