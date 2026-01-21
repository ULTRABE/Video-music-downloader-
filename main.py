#!/usr/bin/env python3.10
import os
import re
import asyncio
import logging
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ───────────── LOGGING ─────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("media-bot")

# ───────────── ENV ─────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set")

# ───────────── CONSTANTS ─────────────
BASE_DIR = Path("/tmp/media_bot")
BASE_DIR.mkdir(exist_ok=True)

DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)

PUBLIC_DOMAINS = {
    "youtube.com", "youtu.be",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "tiktok.com",
}

ADULT_DOMAINS = {
    "pornhub.com", "xvideos.com",
    "xhamster.com", "xnxx.com",
    "youporn.com",
}

SHORT_MARKERS = ("/shorts", "/reel", "/reels", "/p/")

VIDEO_TTL = 600          # keep files for 10 min
ADULT_DELETE_DELAY = 300 # 5 min

# message_id → metadata
VIDEO_STORE: dict[int, dict] = {}

# ───────────── UTIL ─────────────
def normalize_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host

def is_short(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(m in path for m in SHORT_MARKERS) or "tiktok.com" in url

async def delayed_delete(bot, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

async def cleanup_store():
    while True:
        now = time.time()
        for mid, data in list(VIDEO_STORE.items()):
            if now - data["ts"] > VIDEO_TTL:
                VIDEO_STORE.pop(mid, None)
                try:
                    data["path"].unlink(missing_ok=True)
                except:
                    pass
        await asyncio.sleep(60)

# ───────────── DOWNLOAD ─────────────
async def download_video(url: str, out_dir: Path) -> Path | None:
    out_dir.mkdir(exist_ok=True)
    template = out_dir / "video.%(ext)s"

    fmt = (
        "best[ext=mp4][filesize<5M]/best[ext=mp4]"
        if is_short(url)
        else "bestvideo[ext=mp4][height<=720][fps<=30]+bestaudio/best"
    )

    cmd = [
        "yt-dlp",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", str(template),
        url,
    ]

    async with DOWNLOAD_SEMAPHORE:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=90)
        except asyncio.TimeoutError:
            return None

    files = list(out_dir.glob("video.*"))
    return files[0] if files else None

# ───────────── MP3 ─────────────
async def extract_mp3(video: Path) -> Path | None:
    mp3 = video.with_suffix(".mp3")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "192k",
        str(mp3),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        return None
    return mp3 if mp3.exists() else None

# ───────────── HANDLERS ─────────────
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    urls = re.findall(r"https?://\S+", msg.text)
    if not urls:
        return

    url = urls[0]
    domain = normalize_domain(url)
    chat = msg.chat
    is_private = chat.type == chat.PRIVATE
    is_adult = domain in ADULT_DOMAINS
    is_public = domain in PUBLIC_DOMAINS

    try:
        await msg.delete()
    except:
        pass

    if is_adult and not is_private:
        warn = await context.bot.send_message(
            chat.id, "🚫 Adult content is allowed only in private chat."
        )
        asyncio.create_task(delayed_delete(context.bot, chat.id, warn.message_id, 5))
        return

    if not is_public and not is_adult:
        return

    status = await context.bot.send_message(chat.id, "⏳ Processing…")

    try:
        await status.edit_text("⬇️ Downloading…")
        work = BASE_DIR / f"{chat.id}_{msg.message_id}"
        video = await download_video(url, work)
        if not video:
            raise RuntimeError

        await status.edit_text("📤 Uploading…")
        caption = "✅ Video ready"
        ttl = ADULT_DELETE_DELAY if is_adult else 0

        with open(video, "rb") as f:
            sent = await context.bot.send_video(
                chat.id,
                f,
                caption=caption,
                supports_streaming=True,
            )

        VIDEO_STORE[sent.message_id] = {
            "path": video,
            "ts": time.time(),
            "chat": chat.id,
        }

        if chat.type in (chat.GROUP, chat.SUPERGROUP) and not is_adult:
            try:
                await context.bot.pin_chat_message(chat.id, sent.message_id)
            except:
                pass

        if is_adult:
            asyncio.create_task(
                delayed_delete(context.bot, chat.id, sent.message_id, ttl)
            )

    except:
        fail = await context.bot.send_message(chat.id, "❌ Failed to process video.")
        asyncio.create_task(delayed_delete(context.bot, chat.id, fail.message_id, 5))
    finally:
        try:
            await status.delete()
        except:
            pass

async def handle_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    ref = msg.reply_to_message
    if ref.message_id not in VIDEO_STORE:
        return

    try:
        await msg.delete()
    except:
        pass

    status = await context.bot.send_message(msg.chat.id, "🎵 Converting to MP3…")
    try:
        video_path = VIDEO_STORE[ref.message_id]["path"]
        mp3 = await extract_mp3(video_path)
        if mp3:
            with open(mp3, "rb") as f:
                await context.bot.send_audio(msg.chat.id, f)
    finally:
        await status.delete()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("ℹ️ How it works", callback_data="help")]]
    await update.message.reply_text(
        "🎥 **Premium Media Downloader**\n\n"
        "• Send a supported video link\n"
        "• Bot deletes it, downloads & sends video\n"
        "• Reply `/mp3` to get audio\n\n"
        "Fast • Clean • Reliable",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )

async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Send a video link.\n"
        "Bot handles everything automatically.\n\n"
        "Reply `/mp3` to a bot video to extract audio."
    )

# ───────────── MAIN ─────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mp3", handle_mp3))
    app.add_handler(CallbackQueryHandler(help_cb, pattern="help"))
    app.add_handler(MessageHandler(filters.Regex(r"https?://"), handle_media))

    app.job_queue.run_once(lambda *_: asyncio.create_task(cleanup_store()), 1)

    logger.info("BOT READY (polling)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
