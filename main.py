#!/usr/bin/env python3.11
"""
Production Telegram Media Downloader Bot
Webhook-only • Railway-safe • Long-running stable
"""

import os
import re
import asyncio
import logging
import shutil
import signal
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ───────────────── LOGGING ─────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("media-bot")

# ───────────────── ENV ─────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PUBLIC_URL = os.getenv("PUBLIC_URL")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or not WEBHOOK_SECRET or not PUBLIC_URL:
    raise RuntimeError("BOT_TOKEN, WEBHOOK_SECRET, PUBLIC_URL must be set")

# ───────────────── CONSTANTS ─────────────────
BASE_DIR = Path("/tmp/media_bot")
BASE_DIR.mkdir(exist_ok=True)

DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)
ACTIVE_PROCS: set[subprocess.Popen] = set()

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

SHORT_PATH_MARKERS = ("/shorts", "/reel", "/reels")

# message_id -> (video_path, timestamp)
KNOWN_VIDEOS: dict[int, tuple[Path, float]] = {}
KNOWN_VIDEO_TTL = 600  # 10 minutes

# ───────────────── UTILITIES ─────────────────
def normalize_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    parts = netloc.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc

def is_short(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(p in path for p in SHORT_PATH_MARKERS) or "tiktok.com" in url

async def kill_proc(proc: subprocess.Popen):
    try:
        if proc.poll() is None:
            proc.terminate()
            await asyncio.sleep(1)
            if proc.poll() is None:
                proc.kill()
    except:
        pass
    ACTIVE_PROCS.discard(proc)

async def cleanup_known_videos():
    while True:
        now = time.time()
        for mid, (path, ts) in list(KNOWN_VIDEOS.items()):
            if now - ts > KNOWN_VIDEO_TTL:
                KNOWN_VIDEOS.pop(mid, None)
                try:
                    path.unlink(missing_ok=True)
                except:
                    pass
        await asyncio.sleep(60)

async def delayed_delete(bot, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

# ───────────────── DOWNLOAD ─────────────────
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
        ACTIVE_PROCS.add(proc)
        try:
            await asyncio.wait_for(proc.communicate(), timeout=90)
        except asyncio.TimeoutError:
            await kill_proc(proc)
            return None
        finally:
            ACTIVE_PROCS.discard(proc)

    files = list(out_dir.glob("video.*"))
    return files[0] if files else None

# ───────────────── MP3 ─────────────────
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
    ACTIVE_PROCS.add(proc)
    try:
        await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        await kill_proc(proc)
        return None
    finally:
        ACTIVE_PROCS.discard(proc)
    return mp3 if mp3.exists() else None

# ───────────────── HANDLERS ─────────────────
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

    try:
        await msg.delete()
    except:
        pass

    is_adult = domain in ADULT_DOMAINS
    is_public = domain in PUBLIC_DOMAINS

    if is_adult and chat.type != chat.PRIVATE:
        warn = await context.bot.send_message(chat.id, "🚫 This content isn't supported here.")
        asyncio.create_task(delayed_delete(context.bot, chat.id, warn.message_id, 5))
        return

    if not is_public and not is_adult:
        return

    status = await context.bot.send_message(chat.id, "⬇️ Processing media…")

    try:
        work = BASE_DIR / f"{chat.id}_{msg.message_id}"
        video = await download_video(url, work)
        if not video:
            raise RuntimeError("download failed")

        caption = ""
        ttl = 0
        if is_adult:
            caption = (
                "🔒 This video will be deleted in 5 minutes.\n"
                "Forward it to Saved Messages if you want to keep it."
            )
            ttl = 300

        with open(video, "rb") as f:
            sent = await context.bot.send_video(
                chat.id,
                f,
                caption=caption,
                supports_streaming=True,
            )

        KNOWN_VIDEOS[sent.message_id] = (video, time.time())

        if chat.type in (chat.GROUP, chat.SUPERGROUP) and not is_adult:
            try:
                await context.bot.pin_chat_message(chat.id, sent.message_id)
            except:
                pass

        if ttl:
            asyncio.create_task(delayed_delete(context.bot, chat.id, sent.message_id, ttl))

    except Exception:
        fail = await context.bot.send_message(chat.id, "❌ Failed to process media.")
        asyncio.create_task(delayed_delete(context.bot, chat.id, fail.message_id, 5))
    finally:
        try:
            await context.bot.delete_message(chat.id, status.message_id)
        except:
            pass

async def handle_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    ref = msg.reply_to_message
    if ref.message_id not in KNOWN_VIDEOS:
        return

    try:
        await msg.delete()
    except:
        pass

    status = await context.bot.send_message(msg.chat.id, "🎵 Extracting audio…")
    try:
        video, _ = KNOWN_VIDEOS.pop(ref.message_id)
        mp3 = await extract_mp3(video)
        if mp3:
            with open(mp3, "rb") as f:
                await context.bot.send_audio(msg.chat.id, f)
    finally:
        await context.bot.delete_message(msg.chat.id, status.message_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("ℹ️ How it works", callback_data="help")]]
    await update.message.reply_text(
        "🎥 Media Downloader\n\n"
        "Send a supported video link.\n"
        "The rest is automatic.\n\n"
        "Works in groups and private chats.",
        reply_markup=InlineKeyboardMarkup(kb),
    )

async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Send a video link.\n"
        "Bot deletes it, downloads, sends video, and pins it in groups.\n\n"
        "Reply /mp3 to extract audio."
    )

# ───────────────── SHUTDOWN ─────────────────
async def shutdown():
    for p in list(ACTIVE_PROCS):
        await kill_proc(p)
    shutil.rmtree(BASE_DIR, ignore_errors=True)

def sig_handler(*_):
    asyncio.create_task(shutdown())
    raise SystemExit

# ───────────────── MAIN ─────────────────
async def main():
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mp3", handle_mp3))
    app.add_handler(CallbackQueryHandler(help_cb, pattern="help"))
    app.add_handler(MessageHandler(filters.Regex(r"https?://"), handle_media))

    asyncio.create_task(cleanup_known_videos())

    await app.bot.set_webhook(
        url=f"{PUBLIC_URL}/{WEBHOOK_SECRET}",
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )

    logger.info("BOT READY")

    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_SECRET,
        webhook_url=f"{PUBLIC_URL}/{WEBHOOK_SECRET}",
        secret_token=WEBHOOK_SECRET,
    )

if __name__ == "__main__":
    asyncio.run(main())
