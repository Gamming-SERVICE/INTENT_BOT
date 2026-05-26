# ⚡ Intent™ BOT v3.0

> Production-ready, multi-server scalable Discord bot with modular cog architecture, async SQLite, per-guild settings, economy, leveling, AI chat, auto-moderation, giveaways, marketplace, tickets, and automatic updates.

---

## 📋 Table of Contents
- [Features](#-features)
- [Quick Start](#-quick-start)
- [VPS Deployment](#-vps-deployment-ubuntu)
- [Docker Deployment](#-docker-deployment)
- [Windows Setup](#-windows-setup)
- [Configuration](#-configuration)
- [Commands](#-commands)
- [Auto-Updater](#-auto-updater)
- [Project Structure](#-project-structure)
- [Database Schema](#-database-schema)

---

## ✨ Features

| Category | Features |
|----------|----------|
| **Moderation** | Ban, kick, mute, timeout, warn, purge, lock/unlock, slowmode, nick, role, mod logs |
| **Economy** | Balance, daily, work, pay, rob, deposit/withdraw, bank, rich list |
| **Marketplace** | 100+ items, buy/sell, inventory, trade system, rarity system, dynamic pricing |
| **Leveling** | XP per message, level-up announcements, leaderboard, configurable XP rates |
| **AutoMod** | Anti-spam, banned words, anti-link, mass-mention protection, per-guild rules |
| **AI Chat** | Gemini, GPT-4, Groq, Claude, Mistral — per-server API keys |
| **Tickets** | Panel buttons, auto-channel creation, claim, force-close, persistent across restarts |
| **Giveaways** | Timed giveaways, entry button, reroll, early end, multi-winner |
| **Welcome/Leave** | Custom messages with placeholders, per-guild channels |
| **Logging** | Message edit/delete, joins/leaves, bans, voice state, role changes |
| **Fun** | 8-ball, coinflip, dice, RPS, jokes, facts, cat/dog/meme/waifu, hug/pat |
| **Utility** | Userinfo, serverinfo, avatar, AFK, reminders, polls, embed builder, uptime |
| **Admin** | All setup commands, reaction roles, color role panels, custom commands |
| **Auto-Update** | Hourly version check, safe backup, rollback protection, auto-restart |

---

## ⚡ Quick Start

```bash
git clone https://github.com/yourusername/intentbot.git
cd intentbot
cp .env.example .env
nano .env          # Add your DISCORD_TOKEN
pip install -r requirements.txt
python main.py
```

---

## 🖥️ VPS Deployment (Ubuntu)

### One-command setup:
```bash
git clone https://github.com/yourusername/intentbot.git
cd intentbot
chmod +x setup.sh && ./setup.sh
nano .env          # Add DISCORD_TOKEN
sudo systemctl start intentbot
sudo journalctl -u intentbot -f    # View live logs
```

### Manual steps:
```bash
# 1. Install system dependencies
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip ffmpeg libsodium-dev -y

# 2. Create virtualenv
python3.11 -m venv venv && source venv/bin/activate

# 3. Install Python packages
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env && nano .env

# 5. Create directories
mkdir -p data/backups logs

# 6. Run
python main.py
```

### Systemd service:
```bash
sudo cp intentbot.service /etc/systemd/system/
# Edit User= and WorkingDirectory= inside the file
sudo nano /etc/systemd/system/intentbot.service
sudo systemctl daemon-reload
sudo systemctl enable intentbot
sudo systemctl start intentbot

# Commands:
sudo systemctl status intentbot
sudo systemctl restart intentbot
sudo journalctl -u intentbot -f
```

---

## 🐋 Docker Deployment

```bash
# Build and run (detached)
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down

# Rebuild after code changes
docker compose up -d --build
```

> **Data persistence:** The `./data` and `./logs` folders are mounted as volumes.  
> Your database and logs survive container restarts and rebuilds.

---

## 🪟 Windows Setup

```batch
git clone https://github.com/yourusername/intentbot.git
cd intentbot
copy .env.example .env
notepad .env

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

start.bat
```

---

## ⚙️ Configuration

Edit `.env` (never commit this file):

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | ✅ Yes | Your bot token from [Discord Developer Portal](https://discord.com/developers/applications) |
| `OWNER_IDS` | Optional | Comma-separated admin user IDs |
| `DEFAULT_PREFIX` | Optional | Default prefix (default: `!`) |
| `DEBUG` | Optional | Enable debug logging (`true`/`false`) |
| `UPDATE_CHECK_URL` | Optional | Auto-update endpoint URL |

### Per-Server Setup (slash commands):
```
/setwelcome #channel      — Welcome messages
/setleave   #channel      — Leave messages
/setlog     #channel      — Moderation logs
/setmuterole @role        — Mute role
/setautorole @role        — Auto-assign on join
/setticketcategory cat    — Ticket channel category
/setprefix !              — Change command prefix
/toggle Welcome           — Enable/disable features
/aisetkey gemini <key>    — Add AI provider key
/settings                 — View all current settings
```

---

## 📜 Commands

### 🛡️ Moderation
| Command | Description |
|---------|-------------|
| `/ban @user [days] [reason]` | Ban a member |
| `/unban <user_id>` | Unban a user |
| `/kick @user [reason]` | Kick a member |
| `/timeout @user <duration> [reason]` | Timeout (10m, 1h, 2d) |
| `/mute @user [reason]` | Mute using role |
| `/unmute @user` | Remove mute |
| `/warn @user <reason>` | Warn a member |
| `/warnings @user` | View warnings |
| `/clearwarns @user` | Clear all warnings |
| `/purge <1-200> [@user]` | Bulk delete messages |
| `/slowmode [seconds]` | Set channel slowmode |
| `/lock [#channel]` | Lock a channel |
| `/unlock [#channel]` | Unlock a channel |
| `/nick @user [nickname]` | Change nickname |
| `/modlogs @user` | View mod action history |

### 💰 Economy
| Command | Description |
|---------|-------------|
| `/balance [@user]` | Check wallet + bank |
| `/daily` | Claim daily reward (24h cooldown) |
| `/work` | Work for coins (1h cooldown) |
| `/pay @user <amount>` | Transfer coins |
| `/rob @user` | Attempt to rob (risky!) |
| `/deposit [amount\|all]` | Move wallet → bank |
| `/withdraw [amount\|all]` | Move bank → wallet |
| `/richlist` | Top 10 wealthiest members |

### 🛒 Marketplace
| Command | Description |
|---------|-------------|
| `/shop [category]` | Browse items |
| `/buy <item> [qty]` | Purchase an item |
| `/sell <item> [qty]` | Sell from inventory |
| `/inventory [@user]` | View item inventory |
| `/trade @user <item> <qty> <price>` | Send trade offer |
| `/iteminfo <item>` | Item details and pricing |

### ⭐ Leveling
| Command | Description |
|---------|-------------|
| `/rank [@user]` | XP rank card |
| `/leveltop` | XP leaderboard |

### 🎫 Tickets
| Command | Description |
|---------|-------------|
| `/ticketpanel [#channel]` | Post ticket open button |
| `/tickets` | List open tickets |
| `/closeticket [#channel]` | Force-close a ticket |
| `/addtosupport @user` | Add member to ticket |

### 🎉 Giveaways
| Command | Description |
|---------|-------------|
| `/gstart <duration> <prize>` | Start a giveaway |
| `/gend <message_id>` | End giveaway early |
| `/greroll <message_id>` | Reroll winner |
| `/glist` | List active giveaways |

### 🤖 AI Chat
| Command | Description |
|---------|-------------|
| `/ai <prompt> [provider]` | Chat with AI |
| `/aisetkey <provider> <key>` | Set API key (admin) |
| `/aikeys` | List configured providers |

### 🎮 Fun
`/8ball`, `/coinflip`, `/roll [dice]`, `/rps`, `/joke`, `/fact`, `/choose`, `/meme`, `/cat`, `/dog`, `/waifu`, `/hug @user`, `/pat @user`

---

## 🔄 Auto-Updater

The bot checks `UPDATE_CHECK_URL` every hour. The page must contain:
```
version=3.0.1
zip=https://github.com/.../archive/main.zip
```

**What gets preserved during update:**
- `data/database.db` ✅
- `data/backups/` ✅  
- `.env` ✅
- `logs/` ✅

See `update_server_example.html` for a complete hosted example.

---

## 🗂️ Project Structure

```
intentbot/
├── main.py                    # Bot entry point
├── config.py                  # Environment configuration
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── setup.sh                   # VPS one-command setup
├── start.sh                   # Linux/Mac run script
├── start.bat                  # Windows run script
├── intentbot.service          # Systemd unit file
├── update_server_example.html # Update server template
│
├── core/
│   ├── constants.py           # Items, defaults, messages
│   ├── database.py            # Async SQLite + migrations
│   ├── settings.py            # Per-guild settings manager
│   ├── cache.py               # In-memory caches
│   ├── embeds.py              # Embed factory
│   ├── logger.py              # Colored rotating logger
│   ├── permissions.py         # Permission helpers
│   └── scheduler.py           # Background task runner
│
├── cogs/
│   ├── admin.py               # Server setup commands
│   ├── moderation.py          # Ban/kick/mute/warn
│   ├── economy.py             # Economy system
│   ├── leveling.py            # XP and levels
│   ├── automod.py             # Auto-moderation
│   ├── welcome.py             # Join/leave/logging events
│   ├── tickets.py             # Ticket system
│   ├── giveaway.py            # Giveaway system
│   ├── marketplace.py         # Item marketplace
│   ├── utility.py             # Utility commands
│   ├── fun.py                 # Fun commands
│   └── ai.py                  # AI chat integration
│
├── views/
│   ├── ticket_views.py        # Ticket panel buttons
│   ├── role_views.py          # Color role + paginator
│   └── market_views.py        # Trade confirm buttons
│
├── services/
│   └── updater_service.py     # Auto-update system
│
├── data/
│   └── database.db            # SQLite database (auto-created)
│
└── logs/                      # Rotating log files
```

---

## 🗄️ Database Schema

| Table | Purpose |
|-------|---------|
| `guild_settings` | Per-guild JSON config blob |
| `users` | XP, level, balance, bank, cooldowns |
| `warnings` | Mod warnings per user/guild |
| `mod_logs` | All moderation actions |
| `tickets` | Ticket channels and status |
| `giveaways` | Active and ended giveaways |
| `reaction_roles` | Message→emoji→role mappings |
| `color_roles` | Color role panel per guild |
| `reminders` | Scheduled reminders |
| `custom_commands` | Guild-specific text commands |
| `market_items` | Global item catalog (100+ items) |
| `user_items` | Per-user inventory |
| `trades` | Trade offers between users |
| `ai_tokens` | Per-guild AI provider keys |
| `automod_rules` | Custom automod rules |

---

## 📄 License

MIT — see LICENSE file.

---

*Built with [discord.py](https://discordpy.readthedocs.io/) · [aiosqlite](https://aiosqlite.omnilib.dev/) · [aiohttp](https://docs.aiohttp.org/)*
