# 🎵 TikTok Downloader Bot — Production-Ready

A fully async, modular, and scalable Telegram bot that downloads public TikTok videos, extracts audio, and handles slideshow posts — with no watermark when available.

---

## ✨ Features

| Feature | Details |
|---|---|
| 📹 Video download | Standard MP4, no-watermark when available |
| 🎬 HD Video | Best available quality (2/day per user) |
| 🎵 Audio extraction | MP3, 192kbps |
| 🖼 Slideshow support | Downloads photo carousel posts as album |
| 📌 Metadata display | Title, author, duration, caption |
| ⚡ Rate limiting | 5 downloads/day, 2 HD/day per user |
| 🚦 Queue system | Max 4 concurrent downloads, overflow queued |
| 🔒 Anti-abuse | Per-user rate limiting, ban/unban commands |
| 🧹 Auto cleanup | Temp files deleted immediately after sending |
| 📊 Admin panel | Stats, ban, unban, broadcast commands |
| 🔄 Polling + Webhook | Works without SSL (polling default) |
| 🐳 Docker-ready | Dockerfile included |
| 🆓 Free-tier compatible | Runs on Render, Railway, Replit |

---

## 🗂 Project Structure

```
tiktok_bot/
├── bot.py                  # Entry point — registers handlers, starts bot
├── config.py               # All settings loaded from environment variables
├── keep_alive.py           # HTTP health server for free-tier hosts
├── requirements.txt
├── Dockerfile
├── .env.example            # Template for your .env file
│
├── handlers/
│   ├── message_handler.py  # Processes incoming TikTok URLs
│   ├── callback_handler.py # Handles inline button taps → executes download
│   └── admin_handler.py    # /start /help /stats /ban /unban /broadcast
│
├── services/
│   ├── downloader.py       # yt-dlp wrapper: video, audio, slideshow
│   ├── rate_limiter.py     # Per-user daily quota tracking
│   └── queue_manager.py    # Concurrency control via asyncio.Semaphore
│
└── utils/
    ├── logger.py           # Rotating file + console logger
    ├── validators.py       # TikTok URL detection & input sanitization
    └── file_utils.py       # Temp directory lifecycle management
```

---

## 🚀 Quick Start (Local)

### 1. Prerequisites

- Python 3.11+
- **FFmpeg** installed and in your PATH (required for MP3 extraction)
  ```bash
  # Ubuntu / Debian
  sudo apt install ffmpeg
  # macOS
  brew install ffmpeg
  # Windows: download from https://ffmpeg.org/download.html
  ```

### 2. Clone & install

```bash
git clone https://github.com/yourname/tiktok-bot.git
cd tiktok-bot
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_IDS=your_telegram_user_id
```

To get your bot token: message **@BotFather** → `/newbot` → follow prompts.  
To get your Telegram user ID: message **@userinfobot**.

### 4. Run

```bash
python bot.py
```

You should see:
```
2024-01-01 12:00:00 | INFO     | __main__ | Polling mode started.
```

---

## ☁️ Deployment Guides

### 🔵 Railway (Recommended)

Railway offers a free tier with 500 hours/month — enough for 24/7 operation.

1. Create an account at [railway.app](https://railway.app)
2. Click **New Project → Deploy from GitHub Repo**
3. Connect your GitHub repo
4. Go to **Variables** tab and add:
   - `BOT_TOKEN` = your token
   - `ADMIN_IDS` = your user ID
5. Railway auto-detects the `Dockerfile` — click **Deploy**
6. Your bot is live! ✅

> **Keep-alive**: Railway doesn't need UptimeRobot — it runs containers continuously.

---

### 🟢 Render (Free Tier)

Render free tier sleeps after 15 minutes of inactivity. Use `keep_alive.py` + UptimeRobot.

1. Create account at [render.com](https://render.com)
2. New → **Web Service** → connect your repo
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: 
   ```bash
   python -c "from keep_alive import keep_alive; keep_alive()" & python bot.py
   ```
5. Add environment variables in Render dashboard
6. Set up a free UptimeRobot monitor to ping your Render URL every 14 minutes

---

### 🟣 Replit

1. Create a new Python Repl
2. Upload all project files (or use Git import)
3. In **Secrets** tab, add `BOT_TOKEN` and `ADMIN_IDS`
4. In `bot.py`, add at the top of `main()`:
   ```python
   from keep_alive import keep_alive
   keep_alive()
   ```
5. Click ▶️ **Run**
6. Set up UptimeRobot to ping your Replit URL every 14 minutes

---

### 🐳 Docker (Self-hosted / VPS)

```bash
docker build -t tiktok-bot .
docker run -d \
  --name tiktok-bot \
  --restart unless-stopped \
  -e BOT_TOKEN=your_token \
  -e ADMIN_IDS=123456789 \
  tiktok-bot
```

View logs:
```bash
docker logs -f tiktok-bot
```

---

## ⚙️ Configuration Reference

All settings are loaded from environment variables. See `.env.example` for the complete list.

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(required)* | Telegram bot token from @BotFather |
| `ADMIN_IDS` | *(empty)* | Comma-separated admin user IDs |
| `MAX_DOWNLOADS_PER_DAY` | `5` | Max downloads per user per 24h |
| `HD_DOWNLOADS_PER_DAY` | `2` | Max HD downloads per user per 24h |
| `MAX_CONCURRENT` | `4` | Simultaneous yt-dlp processes |
| `MAX_QUEUE_SIZE` | `20` | Max requests waiting in queue |
| `DOWNLOAD_TIMEOUT` | `120` | Seconds before download times out |
| `MAX_FILE_SIZE_MB` | `50` | Max file size (Telegram limit is 50 MB) |
| `TEMP_DIR` | `/tmp/tiktok_bot` | Where temp files are stored |
| `WEBHOOK_URL` | *(empty)* | Set to enable webhook mode |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |

---

## 🤖 Bot Commands

### User Commands
| Command | Description |
|---|---|
| `/start` | Welcome message and feature overview |
| `/help` | Detailed usage instructions |
| `/stats` | Your daily download quota and usage |

### Admin Commands (ADMIN_IDS only)
| Command | Description |
|---|---|
| `/ban <user_id>` | Ban a user from using the bot |
| `/unban <user_id>` | Remove a ban |
| `/broadcast <text>` | Send a message to all active users |

---

## 🔧 Troubleshooting

### ❌ "BOT_TOKEN is not set"
→ Make sure your `.env` file exists and `BOT_TOKEN` is filled in.

### ❌ "FFmpeg not found" / Audio won't extract
→ Install FFmpeg on your system. On Railway/Render use the Dockerfile which installs it automatically.

### ❌ Videos download but can't be sent (file size error)
→ TikTok videos over 50 MB cannot be sent via Telegram bots. This is a hard platform limit. The bot will inform the user.

### ❌ "Private video" error on a public TikTok
→ TikTok occasionally geo-blocks or region-restricts videos. The bot's server region may not have access. Try a VPN-accessible server region.

### ❌ Bot stops working after a few hours (Render/Replit)
→ The free tier host is sleeping. Make sure `keep_alive.py` is running and UptimeRobot is pinging the URL every 14 minutes.

### ❌ yt-dlp errors increase suddenly
→ TikTok changes its API. Run `pip install -U yt-dlp` to update to the latest version. This is the most common fix.

### ❌ "Too many requests" from Telegram
→ Reduce `MAX_CONCURRENT` in your `.env` to `2` or `1`.

---

## 🔒 Security Notes

- Only public TikTok videos are downloaded
- No user data is stored beyond the current runtime session
- Temp files are deleted immediately after delivery
- Rate limiting prevents abuse
- Admin commands silently fail for non-admins
- No credentials, cookies, or TikTok accounts required

---

## 📈 Scaling Beyond Free Tier

When you outgrow free hosting:

1. **Persistent rate limiting**: Replace `RateLimiter`'s in-memory dict with **Redis** (Upstash offers a free tier) or **SQLite**
2. **User database**: Add a SQLite/PostgreSQL table to persist user stats across restarts
3. **Webhook mode**: Set `WEBHOOK_URL` for faster response times vs. polling
4. **Multiple workers**: Run 2–4 bot instances behind a load balancer (each needs its own webhook path)
5. **Monitoring**: Add Sentry for error tracking (`pip install sentry-sdk`)

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Credits

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — async Telegram wrapper
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — video/audio downloading engine
