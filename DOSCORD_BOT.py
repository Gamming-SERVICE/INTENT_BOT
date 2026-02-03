# ══════════════════════════════════════════════════════════════════════════════
# ULTIMATE DISCORD BOT - PRODUCTION READY
# Features: Moderation, Leveling, Economy, Tickets, Giveaways, Auto-mod,
#           Logging, Welcome/Leave, Reaction Roles, Fun, Utility, and more!
# ══════════════════════════════════════════════════════════════════════════════

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiosqlite
import datetime
import random
import json
import re
import os
from typing import Optional, Literal
from collections import defaultdict
import time

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - CHANGE THESE VALUES
# ══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    "TOKEN": "DISCORD_TOKEN",  # REPLACE THIS!
    "GUILD_ID": 1429056625183948882,
    "PREFIX": "!",
    "OWNER_IDS": [],  # Add your Discord user ID(s)
    
    # Channel IDs (set these after bot joins)
    "WELCOME_CHANNEL": None,
    "LEAVE_CHANNEL": None,
    "LOG_CHANNEL": None,
    "TICKET_CATEGORY": None,
    "LEVEL_UP_CHANNEL": None,
    "GIVEAWAY_CHANNEL": None,
    
    # Role IDs
    "MUTE_ROLE": None,
    "AUTO_ROLE": None,  # Role given on join
    "MOD_ROLES": [],
    "ADMIN_ROLES": [],
    
    # Features Toggle
    "WELCOME_ENABLED": True,
    "LEVELING_ENABLED": True,
    "ECONOMY_ENABLED": True,
    "AUTOMOD_ENABLED": True,
    "LOGGING_ENABLED": True,
    
    # Auto-mod Settings
    "BANNED_WORDS": ["badword1", "badword2"],
    "ANTI_SPAM_ENABLED": True,
    "ANTI_LINK_ENABLED": False,
    "MAX_MENTIONS": 5,
    "SPAM_THRESHOLD": 5,  # messages
    "SPAM_INTERVAL": 5,   # seconds
    
    # Economy Settings
    "CURRENCY_NAME": "coins",
    "CURRENCY_SYMBOL": "🪙",
    "DAILY_AMOUNT": 100,
    "WORK_MIN": 50,
    "WORK_MAX": 200,
    "WORK_COOLDOWN": 3600,  # seconds
    
    # Leveling Settings
    "XP_PER_MESSAGE": (15, 25),
    "XP_COOLDOWN": 60,
    "LEVEL_UP_MESSAGE": "🎉 Congratulations {user}! You've reached level **{level}**!",
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
reminders = []
afk_users = {}

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE SETUP
# ══════════════════════════════════════════════════════════════════════════════

async def init_database():
    async with aiosqlite.connect("bot_database.db") as db:
        # Users table (economy + leveling)
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
        
        # Warnings table
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
        
        # Tickets table
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
        
        # Custom commands table
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
        
        # Reaction roles table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                guild_id INTEGER,
                PRIMARY KEY (message_id, emoji)
            )
        """)
        
        # Giveaways table
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
        
        # Reminders table
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
        
        # Server settings table
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
        
        # Infractions/Mod logs table
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
        
        # Shop items table
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
        
        await db.commit()
        print("✅ Database initialized successfully!")

# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_level_xp(level):
    """Calculate XP needed for a level"""
    return 5 * (level ** 2) + 50 * level + 100

def get_level_from_xp(xp):
    """Calculate level from total XP"""
    level = 1
    while xp >= get_level_xp(level):
        xp -= get_level_xp(level)
        level += 1
    return level, xp

async def get_user_data(user_id, guild_id):
    """Get or create user data"""
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
    """Update user data"""
    async with aiosqlite.connect("bot_database.db") as db:
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [user_id, guild_id]
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE user_id = ? AND guild_id = ?",
            values
        )
        await db.commit()

async def log_action(guild, embed):
    """Send log to log channel"""
    if not CONFIG["LOGGING_ENABLED"]:
        return
    
    log_channel_id = CONFIG.get("LOG_CHANNEL")
    if log_channel_id:
        channel = guild.get_channel(log_channel_id)
        if channel:
            await channel.send(embed=embed)

def create_embed(title, description=None, color=discord.Color.blue(), **kwargs):
    """Create a standard embed"""
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.datetime.utcnow()
    
    if "author" in kwargs:
        embed.set_author(name=kwargs["author"].name, icon_url=kwargs["author"].display_avatar.url)
    if "footer" in kwargs:
        embed.set_footer(text=kwargs["footer"])
    if "thumbnail" in kwargs:
        embed.set_thumbnail(url=kwargs["thumbnail"])
    if "image" in kwargs:
        embed.set_image(url=kwargs["image"])
    if "fields" in kwargs:
        for name, value, inline in kwargs["fields"]:
            embed.add_field(name=name, value=value, inline=inline)
    
    return embed

def parse_time(time_str):
    """Parse time string like 1d, 2h, 30m, 60s"""
    time_regex = re.compile(r"(\d+)([smhdw])")
    matches = time_regex.findall(time_str.lower())
    
    if not matches:
        return None
    
    total_seconds = 0
    for value, unit in matches:
        value = int(value)
        if unit == "s":
            total_seconds += value
        elif unit == "m":
            total_seconds += value * 60
        elif unit == "h":
            total_seconds += value * 3600
        elif unit == "d":
            total_seconds += value * 86400
        elif unit == "w":
            total_seconds += value * 604800
    
    return total_seconds

# ══════════════════════════════════════════════════════════════════════════════
# BOT EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    await init_database()
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
    
    # Start background tasks
    check_reminders.start()
    check_giveaways.start()
    update_status.start()
    
    # Load reaction roles from database
    await load_reaction_roles()
    await load_custom_commands()

@bot.event
async def on_member_join(member):
    if not CONFIG["WELCOME_ENABLED"]:
        return
    
    # Auto role
    if CONFIG.get("AUTO_ROLE"):
        role = member.guild.get_role(CONFIG["AUTO_ROLE"])
        if role:
            try:
                await member.add_roles(role)
            except:
                pass
    
    # Welcome message
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
    
    # Log
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
    
    # Log
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
        await message.channel.send(f"Welcome back {message.author.mention}! I've removed your AFK status.", delete_after=5)
    
    # Check mentioned AFK users
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
    if CONFIG["AUTOMOD_ENABLED"] and not message.author.guild_permissions.administrator:
        # Anti-spam
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
        
        # Banned words
        content_lower = message.content.lower()
        for word in CONFIG["BANNED_WORDS"]:
            if word.lower() in content_lower:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention} That word is not allowed!",
                    delete_after=5
                )
                return
        
        # Anti-link
        if CONFIG["ANTI_LINK_ENABLED"]:
            url_pattern = re.compile(
                r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
            )
            if url_pattern.search(message.content):
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention} Links are not allowed!",
                    delete_after=5
                )
                return
        
        # Max mentions
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
            
            # Level up notification
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
    # Role changes
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
    
    # Nickname changes
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
    
    # Check reaction roles
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
        reminders = await cursor.fetchall()
        
        for reminder in reminders:
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
                channel = bot.get_channel(giveaway[2])
                message = await channel.fetch_message(giveaway[1])
                
                participants = json.loads(giveaway[8])
                winners_count = giveaway[5]
                
                if len(participants) < winners_count:
                    winners_count = len(participants)
                
                if winners_count > 0:
                    winners = random.sample(participants, winners_count)
                    winner_mentions = ", ".join([f"<@{w}>" for w in winners])
                    await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{giveaway[4]}**!")
                else:
                    await channel.send("😢 No one entered the giveaway.")
                
                # Update message
                embed = message.embeds[0]
                embed.description = f"🎁 **{giveaway[4]}**\n\n**Ended!**"
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
                
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
            discord.SelectOption(label="🎫 Tickets", description="Support ticket system", value="ticket"),
            discord.SelectOption(label="🎉 Giveaways", description="Giveaway commands", value="giveaway"),
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
                "!meme                    - Random meme\n"
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
                "!channelinfo [channel]   - Channel info\n"
                "!afk [reason]            - Set AFK status\n"
                "!remind <time> <text>    - Set reminder\n"
                "!poll <question>         - Create a poll\n"
                "!embed <title> | <desc>  - Create embed\n"
                "!steal <emoji>           - Steal emoji\n"
                "!translate <lang> <text> - Translate text\n"
                "```",
                discord.Color.blue()
            ),
            "level": create_embed(
                "📊 Leveling Commands",
                "```\n"
                "!rank [user]             - View rank card\n"
                "!leaderboard             - XP leaderboard\n"
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
                "!shop                    - View shop\n"
                "!buy <item>              - Buy an item\n"
                "!inventory               - View inventory\n"
                "!rob <user>              - Rob someone\n"
                "!slots <amount>          - Play slots\n"
                "!gamble <amount>         - Gamble coins\n"
                "!baltop                  - Rich leaderboard\n"
                "```",
                discord.Color.green()
            ),
            "ticket": create_embed(
                "🎫 Ticket Commands",
                "```\n"
                "!ticket                  - Create ticket\n"
                "!close                   - Close ticket\n"
                "!add <user>              - Add user to ticket\n"
                "!remove <user>           - Remove from ticket\n"
                "!transcript              - Save transcript\n"
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
            "admin": create_embed(
                "⚙️ Admin Commands",
                "```\n"
                "!setup                   - Interactive setup\n"
                "!setwelcome <channel>    - Set welcome channel\n"
                "!setleave <channel>      - Set leave channel\n"
                "!setlog <channel>        - Set log channel\n"
                "!setautorole <role>      - Set auto role\n"
                "!setmuterole <role>      - Set mute role\n"
                "!addcmd <name> <response>- Add custom cmd\n"
                "!delcmd <name>           - Delete custom cmd\n"
                "!reactionrole <msg_id> <emoji> <role>\n"
                "                         - Add reaction role\n"
                "!toggle <feature>        - Toggle features\n"
                "!addword <word>          - Add banned word\n"
                "!removeword <word>       - Remove banned word\n"
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
        description="Welcome to the ultimate Discord bot!\n\n"
                   "**Select a category below to view commands.**\n\n"
                   f"**Prefix:** `{CONFIG['PREFIX']}`\n"
                   f"**Total Commands:** 70+\n"
                   f"**Support Server:** [Click Here](https://discord.gg/support)",
        color=discord.Color.blurple(),
        author=ctx.author
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=embed, view=HelpView())

# ══════════════════════════════════════════════════════════════════════════════
# MODERATION COMMANDS
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
    
    # DM user
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
    
    # DM user
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
    
    embed = create_embed(
        title=f"⚠️ Warnings for {member.name}",
        color=discord.Color.yellow()
    )
    
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
# UTILITY COMMANDS
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
    embed = create_embed(
        title=f"🎭 {role.name}",
        color=role.color
    )
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
    afk_users[ctx.author.id] = {
        "reason": reason,
        "time": time.time()
    }
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
    embed = create_embed(
        title="📊 Poll",
        description=question,
        color=discord.Color.blurple(),
        author=ctx.author
    )
    
    message = await ctx.send(embed=embed)
    await message.add_reaction("👍")
    await message.add_reaction("👎")
    await message.add_reaction("🤷")

@bot.command()
async def embed(ctx, *, content: str):
    """Create an embed. Format: title | description"""
    parts = content.split("|")
    title = parts[0].strip()
    description = parts[1].strip() if len(parts) > 1 else ""
    
    embed = create_embed(title=title, description=description, author=ctx.author)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_emojis=True)
async def steal(ctx, emoji: discord.PartialEmoji, name: str = None):
    """Steal an emoji from another server"""
    name = name or emoji.name
    
    try:
        emoji_bytes = await emoji.read()
        new_emoji = await ctx.guild.create_custom_emoji(name=name, image=emoji_bytes)
        await ctx.send(f"✅ Added emoji {new_emoji}")
    except Exception as e:
        await ctx.send(f"❌ Failed to add emoji: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# FUN COMMANDS
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
        fields=[
            ("Question", question, False),
            ("Answer", random.choice(responses), False)
        ]
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
    """Random choice. Separate options with commas or 'or'"""
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
    
    if percentage > 80:
        message = "💕 Perfect match!"
    elif percentage > 60:
        message = "💖 Great couple!"
    elif percentage > 40:
        message = "💛 Could work out!"
    elif percentage > 20:
        message = "💔 Not looking good..."
    else:
        message = "💀 Stay friends..."
    
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
# LEVELING COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@bot.command(aliases=["level", "xp"])
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = await get_user_data(member.id, ctx.guild.id)
    
    xp_needed = get_level_xp(data["level"])
    current_xp = data["xp"] - sum(get_level_xp(i) for i in range(1, data["level"]))
    progress = int((current_xp / xp_needed) * 20)
    bar = "█" * progress + "░" * (20 - progress)
    
    # Get rank position
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE guild_id = ? AND xp > ?",
            (ctx.guild.id, data["xp"])
        )
        rank = (await cursor.fetchone())[0] + 1
    
    embed = create_embed(
        title=f"📊 {member.name}'s Rank",
        color=member.color,
        thumbnail=member.display_avatar.url
    )
    embed.add_field(name="Rank", value=f"#{rank}", inline=True)
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
# ECONOMY COMMANDS
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
    
    if random.random() < 0.4:  # 40% success rate
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
        if result[0] == "💎":
            winnings = amount * 10
        elif result[0] == "7️⃣":
            winnings = amount * 7
        else:
            winnings = amount * 5
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
    
    if random.random() < 0.45:  # 45% win rate
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

@bot.command()
async def shop(ctx):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM shop_items WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        items = await cursor.fetchall()
    
    if not items:
        return await ctx.send("❌ The shop is empty!")
    
    embed = create_embed(
        title="🛒 Shop",
        description="Use `!buy <item_id>` to purchase an item",
        color=discord.Color.blue()
    )
    
    for item in items:
        embed.add_field(
            name=f"#{item[0]} - {item[3]} - {CONFIG['CURRENCY_SYMBOL']} {item[5]:,}",
            value=item[4] or "No description",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command()
async def buy(ctx, item_id: int):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM shop_items WHERE id = ? AND guild_id = ?",
            (item_id, ctx.guild.id)
        )
        item = await cursor.fetchone()
    
    if not item:
        return await ctx.send("❌ Item not found!")
    
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    
    if data["balance"] < item[5]:
        return await ctx.send("❌ You don't have enough money!")
    
    await update_user_data(ctx.author.id, ctx.guild.id, balance=data["balance"] - item[5])
    
    # Add role if item has one
    if item[6]:
        role = ctx.guild.get_role(item[6])
        if role:
            await ctx.author.add_roles(role)
    
    # Add to inventory
    inventory = json.loads(data.get("inventory", "[]"))
    inventory.append({"id": item[0], "name": item[3]})
    await update_user_data(ctx.author.id, ctx.guild.id, inventory=json.dumps(inventory))
    
    await ctx.send(f"✅ You purchased **{item[3]}** for {CONFIG['CURRENCY_SYMBOL']} **{item[5]}**!")

@bot.command(aliases=["inv"])
async def inventory(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = await get_user_data(member.id, ctx.guild.id)
    
    inventory = json.loads(data.get("inventory", "[]"))
    
    if not inventory:
        return await ctx.send(f"❌ {member.name}'s inventory is empty!")
    
    items = [f"• {item['name']}" for item in inventory]
    
    embed = create_embed(
        title=f"🎒 {member.name}'s Inventory",
        description="\n".join(items),
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

# ══════════════════════════════════════════════════════════════════════════════
# TICKET COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@bot.command()
async def ticket(ctx):
    # Check for existing ticket
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'",
            (ctx.author.id, ctx.guild.id)
        )
        existing = await cursor.fetchone()
    
    if existing:
        return await ctx.send(f"❌ You already have an open ticket: <#{existing[1]}>")
    
    # Create ticket channel
    category = ctx.guild.get_channel(CONFIG.get("TICKET_CATEGORY"))
    
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    
    channel = await ctx.guild.create_text_channel(
        f"ticket-{ctx.author.name}",
        category=category,
        overwrites=overwrites
    )
    
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "INSERT INTO tickets (channel_id, user_id, guild_id) VALUES (?, ?, ?)",
            (channel.id, ctx.author.id, ctx.guild.id)
        )
        await db.commit()
    
    embed = create_embed(
        title="🎫 Ticket Created",
        description=f"Welcome {ctx.author.mention}!\n\n"
                   f"Please describe your issue and a staff member will assist you shortly.\n\n"
                   f"Use `!close` to close this ticket.",
        color=discord.Color.green()
    )
    await channel.send(ctx.author.mention, embed=embed)
    await ctx.send(f"✅ Ticket created: {channel.mention}")

@bot.command()
async def close(ctx):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
            (ctx.channel.id,)
        )
        ticket = await cursor.fetchone()
    
    if not ticket:
        return await ctx.send("❌ This is not a ticket channel!")
    
    await ctx.send("🔒 Closing ticket in 5 seconds...")
    await asyncio.sleep(5)
    
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ? WHERE channel_id = ?",
            (datetime.datetime.utcnow().isoformat(), ctx.channel.id)
        )
        await db.commit()
    
    await ctx.channel.delete()

@bot.command()
@commands.has_permissions(manage_channels=True)
async def add(ctx, member: discord.Member):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
            (ctx.channel.id,)
        )
        ticket = await cursor.fetchone()
    
    if not ticket:
        return await ctx.send("❌ This is not a ticket channel!")
    
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
    await ctx.send(f"✅ Added {member.mention} to the ticket")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def remove(ctx, member: discord.Member):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
            (ctx.channel.id,)
        )
        ticket = await cursor.fetchone()
    
    if not ticket:
        return await ctx.send("❌ This is not a ticket channel!")
    
    await ctx.channel.set_permissions(member, overwrite=None)
    await ctx.send(f"✅ Removed {member.mention} from the ticket")

# ══════════════════════════════════════════════════════════════════════════════
# GIVEAWAY COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@bot.command()
@commands.has_permissions(manage_guild=True)
async def gstart(ctx, duration: str, winners: int, *, prize: str):
    seconds = parse_time(duration)
    if not seconds:
        return await ctx.send("❌ Invalid duration!")
    
    end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
    
    embed = create_embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"🎁 **{prize}**\n\n"
                   f"React with 🎉 to enter!\n\n"
                   f"**Winners:** {winners}\n"
                   f"**Ends:** <t:{int(end_time.timestamp())}:R>\n"
                   f"**Hosted by:** {ctx.author.mention}",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Giveaway ends at")
    embed.timestamp = end_time
    
    message = await ctx.send(embed=embed)
    await message.add_reaction("🎉")
    
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "INSERT INTO giveaways (message_id, channel_id, guild_id, prize, winners, host_id, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message.id, ctx.channel.id, ctx.guild.id, prize, winners, ctx.author.id, end_time.isoformat())
        )
        await db.commit()

@bot.command()
@commands.has_permissions(manage_guild=True)
async def gend(ctx, message_id: int):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM giveaways WHERE message_id = ? AND ended = 0",
            (message_id,)
        )
        giveaway = await cursor.fetchone()
    
    if not giveaway:
        return await ctx.send("❌ Giveaway not found!")
    
    try:
        channel = bot.get_channel(giveaway[2])
        message = await channel.fetch_message(message_id)
        
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        users = [user async for user in reaction.users() if not user.bot]
        
        winners_count = giveaway[5]
        if len(users) < winners_count:
            winners_count = len(users)
        
        if winners_count > 0:
            winners = random.sample(users, winners_count)
            winner_mentions = ", ".join([w.mention for w in winners])
            await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{giveaway[4]}**!")
        else:
            await channel.send("😢 No one entered the giveaway.")
        
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("UPDATE giveaways SET ended = 1 WHERE message_id = ?", (message_id,))
            await db.commit()
        
        await ctx.send("✅ Giveaway ended!")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def greroll(ctx, message_id: int):
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM giveaways WHERE message_id = ?",
            (message_id,)
        )
        giveaway = await cursor.fetchone()
    
    if not giveaway:
        return await ctx.send("❌ Giveaway not found!")
    
    try:
        channel = bot.get_channel(giveaway[2])
        message = await channel.fetch_message(message_id)
        
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        users = [user async for user in reaction.users() if not user.bot]
        
        if users:
            winner = random.choice(users)
            await channel.send(f"🎉 New winner: {winner.mention}! Congratulations, you won **{giveaway[4]}**!")
        else:
            await ctx.send("❌ No valid participants found.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN/SETUP COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@bot.command()
@commands.has_permissions(administrator=True)
async def setwelcome(ctx, channel: discord.TextChannel):
    CONFIG["WELCOME_CHANNEL"] = channel.id
    await ctx.send(f"✅ Welcome channel set to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setleave(ctx, channel: discord.TextChannel):
    CONFIG["LEAVE_CHANNEL"] = channel.id
    await ctx.send(f"✅ Leave channel set to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel):
    CONFIG["LOG_CHANNEL"] = channel.id
    await ctx.send(f"✅ Log channel set to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setautorole(ctx, role: discord.Role):
    CONFIG["AUTO_ROLE"] = role.id
    await ctx.send(f"✅ Auto role set to {role.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setmuterole(ctx, role: discord.Role):
    CONFIG["MUTE_ROLE"] = role.id
    await ctx.send(f"✅ Mute role set to {role.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def addcmd(ctx, name: str, *, response: str):
    name = name.lower()
    
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "INSERT OR REPLACE INTO custom_commands (name, guild_id, response, created_by) VALUES (?, ?, ?, ?)",
            (name, ctx.guild.id, response, ctx.author.id)
        )
        await db.commit()
    
    custom_commands[name] = response
    await ctx.send(f"✅ Custom command `{CONFIG['PREFIX']}{name}` created!")

@bot.command()
@commands.has_permissions(administrator=True)
async def delcmd(ctx, name: str):
    name = name.lower()
    
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("DELETE FROM custom_commands WHERE name = ? AND guild_id = ?", (name, ctx.guild.id))
        await db.commit()
    
    if name in custom_commands:
        del custom_commands[name]
    
    await ctx.send(f"✅ Custom command `{name}` deleted!")

@bot.command()
@commands.has_permissions(administrator=True)
async def reactionrole(ctx, message_id: int, emoji: str, role: discord.Role):
    try:
        message = await ctx.channel.fetch_message(message_id)
        await message.add_reaction(emoji)
        
        key = f"{message_id}-{emoji}"
        reaction_roles[key] = role.id
        
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "INSERT OR REPLACE INTO reaction_roles (message_id, emoji, role_id, guild_id) VALUES (?, ?, ?, ?)",
                (message_id, emoji, role.id, ctx.guild.id)
            )
            await db.commit()
        
        await ctx.send(f"✅ Reaction role set! React with {emoji} to get {role.mention}")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def toggle(ctx, feature: str):
    feature = feature.lower()
    
    toggles = {
        "welcome": "WELCOME_ENABLED",
        "leveling": "LEVELING_ENABLED",
        "economy": "ECONOMY_ENABLED",
        "automod": "AUTOMOD_ENABLED",
        "logging": "LOGGING_ENABLED",
        "antispam": "ANTI_SPAM_ENABLED",
        "antilink": "ANTI_LINK_ENABLED"
    }
    
    if feature not in toggles:
        return await ctx.send(f"❌ Unknown feature. Available: {', '.join(toggles.keys())}")
    
    key = toggles[feature]
    CONFIG[key] = not CONFIG[key]
    status = "enabled" if CONFIG[key] else "disabled"
    
    await ctx.send(f"✅ **{feature.title()}** has been **{status}**")

@bot.command()
@commands.has_permissions(administrator=True)
async def addword(ctx, *, word: str):
    CONFIG["BANNED_WORDS"].append(word.lower())
    await ctx.send(f"✅ Added `{word}` to banned words list")

@bot.command()
@commands.has_permissions(administrator=True)
async def removeword(ctx, *, word: str):
    if word.lower() in CONFIG["BANNED_WORDS"]:
        CONFIG["BANNED_WORDS"].remove(word.lower())
        await ctx.send(f"✅ Removed `{word}` from banned words list")
    else:
        await ctx.send("❌ Word not found in banned list")

@bot.command()
@commands.has_permissions(administrator=True)
async def addshopitem(ctx, name: str, price: int, role: discord.Role = None, *, description: str = None):
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "INSERT INTO shop_items (guild_id, name, description, price, role_id) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, name, description, price, role.id if role else None)
        )
        await db.commit()
    
    await ctx.send(f"✅ Added **{name}** to the shop for {CONFIG['CURRENCY_SYMBOL']} **{price}**")

@bot.command()
@commands.has_permissions(administrator=True)
async def removeshopitem(ctx, item_id: int):
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("DELETE FROM shop_items WHERE id = ? AND guild_id = ?", (item_id, ctx.guild.id))
        await db.commit()
    
    await ctx.send(f"✅ Removed item #{item_id} from the shop")

# ══════════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    embed = create_embed(
        title="🏓 Pong!",
        description=f"Latency: **{round(bot.latency * 1000)}ms**",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Get information about a user")
async def slash_userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    
    roles = [r.mention for r in member.roles[1:]][:10]
    roles_str = ", ".join(roles) if roles else "None"
    
    embed = create_embed(
        title=f"👤 {member.name}",
        color=member.color,
        thumbnail=member.display_avatar.url
    )
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
    embed.add_field(name=f"Roles [{len(member.roles) - 1}]", value=roles_str, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rank", description="Check your rank")
async def slash_rank(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    data = await get_user_data(member.id, interaction.guild.id)
    
    xp_needed = get_level_xp(data["level"])
    current_xp = data["xp"] - sum(get_level_xp(i) for i in range(1, data["level"]))
    progress = int((current_xp / xp_needed) * 20)
    bar = "█" * progress + "░" * (20 - progress)
    
    embed = create_embed(
        title=f"📊 {member.name}'s Rank",
        color=member.color,
        thumbnail=member.display_avatar.url
    )
    embed.add_field(name="Level", value=data["level"], inline=True)
    embed.add_field(name="XP", value=f"{data['xp']:,}", inline=True)
    embed.add_field(name="Progress", value=f"`{bar}`", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="balance", description="Check your balance")
async def slash_balance(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    data = await get_user_data(member.id, interaction.guild.id)
    
    embed = create_embed(
        title=f"💰 {member.name}'s Balance",
        color=discord.Color.green()
    )
    embed.add_field(name="Wallet", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['balance']:,}", inline=True)
    embed.add_field(name="Bank", value=f"{CONFIG['CURRENCY_SYMBOL']} {data['bank']:,}", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ticket", description="Create a support ticket")
async def slash_ticket(interaction: discord.Interaction):
    # Check for existing ticket
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'",
            (interaction.user.id, interaction.guild.id)
        )
        existing = await cursor.fetchone()
    
    if existing:
        return await interaction.response.send_message(f"❌ You already have an open ticket!", ephemeral=True)
    
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    
    channel = await interaction.guild.create_text_channel(
        f"ticket-{interaction.user.name}",
        overwrites=overwrites
    )
    
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            "INSERT INTO tickets (channel_id, user_id, guild_id) VALUES (?, ?, ?)",
            (channel.id, interaction.user.id, interaction.guild.id)
        )
        await db.commit()
    
    embed = create_embed(
        title="🎫 Ticket Created",
        description=f"Welcome! Please describe your issue.",
        color=discord.Color.green()
    )
    await channel.send(interaction.user.mention, embed=embed)
    await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

@bot.tree.command(name="poll", description="Create a poll")
async def slash_poll(interaction: discord.Interaction, question: str):
    embed = create_embed(
        title="📊 Poll",
        description=question,
        color=discord.Color.blurple(),
        author=interaction.user
    )
    
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    await message.add_reaction("👍")
    await message.add_reaction("👎")
    await message.add_reaction("🤷")

# ══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found!")
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send("❌ Role not found!")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("❌ Channel not found!")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"❌ Command on cooldown! Try again in {error.retry_after:.1f}s")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        await ctx.send(f"❌ An error occurred: {error}")
        print(f"Error: {error}")

# ══════════════════════════════════════════════════════════════════════════════
# RUN BOT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 Starting bot...")
    bot.run(CONFIG["TOKEN"])
