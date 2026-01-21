Below is a **clean, professional, production-grade README** you can ship with this repo.
It is written for **GitHub + Railway + VPS users**, explains behavior clearly, and **does NOT expose sensitive adult logic in a risky way**.

You can copy-paste this **as-is**.

---

# 🎥 Video Downloader Telegram Bot

A **fast, clean, and production-ready Telegram bot** for downloading videos from popular platforms like **YouTube, Instagram, TikTok, Twitter/X, and Facebook**, built with **aiogram 3.x**, **yt-dlp**, and **Redis**.

Designed for **group chats, private chats, and large-scale deployment** with proper rate limits, cancel support, and clean UX.

---

## ✨ Features

### Core Features

* 📥 Download videos from supported platforms
* ⚡ Automatic link detection
* 🧹 Clean UX (original link message deleted)
* 📊 Download status updates
* ❌ Cancel download button
* 📌 Auto-pin downloaded videos in groups
* 📦 Smart file handling (video / document based on size)

### Platform Support

* **YouTube** (videos & shorts)
* **Instagram** (videos & reels)
* **TikTok**
* **Twitter / X**
* **Facebook** (videos & reels)

> Unsupported links are silently ignored.

---

## 🔐 Adult Content Handling (Safe & Controlled)

* Adult links are **blocked in group chats**
* Users are redirected to **private chat**
* Bot remembers the original link securely (Redis)
* Download starts automatically in PM
* Files auto-delete after **1 minute**
* No adult hints shown in `/start` or public UI

This design **reduces reports, abuse, and storage risk**.

---

## 🛡️ Safety & Stability

* Per-user **rate limiting**
* Redis-backed state (scales well)
* Cancel-safe downloads
* Automatic cleanup of temp files
* Non-root Docker container
* Production-ready logging

---

## 👑 Admin Features

* `/chatid` → get current chat ID
* `/premium <chat_id>` → enable **adult-only mode** for a private group
* Owner-only access (via `OWNER_ID`)

---

## 🧠 Tech Stack

* **Python 3.11**
* **aiogram 3.x**
* **yt-dlp**
* **Redis**
* **Docker**

---

## 📁 Project Structure

```
.
├── main.py
├── config.py
├── requirements.txt
├── Dockerfile
├── .env.example
│
├── handlers/
│   ├── start.py
│   ├── messages.py
│   ├── admin.py
│   └── callbacks.py
│
├── services/
│   └── downloader.py
│
├── utils/
│   ├── state.py
│   ├── rate_limit.py
│   ├── platforms.py
│   └── mp3.py
│
└── ui/
    ├── keyboards.py
    └── text.py
```

---

## 🚀 Deployment (Railway – Recommended)

### 1️⃣ Fork the Repository

Push this code to your GitHub account.

---

### 2️⃣ Create a New Railway Project

👉 [https://railway.app/new](https://railway.app/new)
Connect your GitHub repo.

---

### 3️⃣ Add Redis Plugin

In Railway dashboard:

```
Add → Plugin → Redis
```

---

### 4️⃣ Set Environment Variables

Use values from `.env.example`:

```env
BOT_TOKEN=your_bot_token_here
REDIS_URL=redis://default:password@redis-host:6379
OWNER_ID=123456789
```

* **BOT_TOKEN** → from @BotFather
* **REDIS_URL** → provided by Railway Redis plugin
* **OWNER_ID** → your Telegram user ID (use @userinfobot)

---

### 5️⃣ Deploy 🚀

Railway will:

* Build Docker image
* Install dependencies
* Start polling automatically

Logs should show:

```
Bot started successfully
```

---

## 🐳 Docker (VPS / Local)

```bash
docker build -t video-downloader-bot .
docker run -d \
  -e BOT_TOKEN=xxx \
  -e REDIS_URL=redis://... \
  -e OWNER_ID=123 \
  video-downloader-bot
```

---

## 📌 Commands

| Command              | Description                      |
| -------------------- | -------------------------------- |
| `/start`             | Show welcome message             |
| `/chatid`            | Get current chat ID (admin only) |
| `/premium <chat_id>` | Enable premium adult-only mode   |

---

## ⚠️ Notes & Limitations

* Telegram video limit: **45 MB**
* Larger files are sent as **documents**
* Some platforms may block downloads due to regional restrictions
* Bot uses **polling** (no webhook)

---

## 📜 License

This project is provided **as-is** for educational and personal use.
You are responsible for complying with **local laws** and **platform terms of service**.

