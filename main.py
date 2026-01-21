#!/usr/bin/env python3
import os
import re
import asyncio
import logging
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Dict

import yt_dlp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# ───────── LOGGING ─────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("downloader")

# ───────── ENV ─────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

# ───────── CONFIG ─────────
TEMP_DIR = Path("/tmp/downloader")
TEMP_DIR.mkdir(exist_ok=True)

MAX_CONCURRENT = 2
download_sem = asyncio.Semaphore(MAX_CONCURRENT)

PUBLIC_DOMAINS = {
    "youtube.com", "youtu.be",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "tiktok.com",
}

ADULT_DOMAINS = {
    "pornhub.com",
    "xvideos.com",
    "xhamster.com",
    "xnxx.com",
    "youporn.com",
}

# message_id -> (file_path, timestamp)
VIDEO_STORE: Dict[int, tuple[Path, float]] = {}
VIDEO_STORE_TTL = 900  # 15 min

# ───────── UTIL ─────────
def domain_of(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc

def is_short(url: str) -> bool:
    u = url.lower()
    return any(x in u for x in ["/shorts/", "/reel/", "/reels/", "tiktok.com"])

def premium_status(step: str) -> str:
    return {
        "recv": "✨ Link received. Preparing…",
        "dl": "⬇️ Downloading media…",
        "mux": "⚡ Optimizing video…",
        "up": "📤 Uploading…",
    }[step]

# ───────── DOWNLOAD ─────────
async def download_video(url: str) -> Optional[Path]:
    ts = int(time.time() * 1000)
    out = TEMP_DIR / f"video_{ts}.%(ext)s"

    fmt = (
        "best[ext=mp4][filesize<15M]/best[ext=mp4]"
        if is_short(url)
        else "bestvideo[ext=mp4][height<=720][fps<=30]+bestaudio/best/best"
    )

    ydl_opts = {
        "format": fmt,
        "outtmpl": str(out),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

    async with download_sem:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]),
            )
        except Exception as e:
            logger.error(f"yt-dlp failed: {e}")
            return None

    files = list(TEMP_DIR.glob(f"video_{ts}.*"))
    return files[0] if files else None

# ───────── HANDLERS ─────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **Premium Media Downloader**\n\n"
        "• Send a video link\n"
        "• Supports Shorts & Reels\n"
        "• Reply `/mp3` to my video\n\n"
        "Fast. Clean. Reliable.",
        parse_mode="Markdown",
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = msg.chat

    urls = re.findall(r"https?://\S+", msg.text or "")
    if not urls:
        return

    url = urls[0]
    dom = domain_of(url)

    # Delete original message
    try:
        await msg.delete()
    except:
        pass

    is_adult = dom in ADULT_DOMAINS
    is_public = dom in PUBLIC_DOMAINS

    if is_adult and chat.type != "private":
        await context.bot.send_message(
            chat.id,
            "🔞 Adult content is only allowed in private chat.\n"
            "Open bot privately and send the link there.",
        )
        return

    if not (is_public or is_adult):
        await context.bot.send_message(chat.id, "❌ Unsupported link.")
        return

    status = await context.bot.send_message(chat.id, premium_status("recv"))

    try:
        await status.edit_text(premium_status("dl"))
        video = await download_video(url)
        if not video:
            raise RuntimeError("download failed")

        await status.edit_text(premium_status("up"))

        with open(video, "rb") as f:
            sent = await context.bot.send_video(
                chat.id,
                f,
                supports_streaming=True,
            )

        VIDEO_STORE[sent.message_id] = (video, time.time())

        if chat.type in ("group", "supergroup") and not is_adult:
            try:
                await context.bot.pin_chat_message(chat.id, sent.message_id)
            except:
                pass

        if is_adult:
            asyncio.create_task(auto_delete(chat.id, sent.message_id, 300))

    except Exception as e:
        logger.error(e)
        await context.bot.send_message(chat.id, "❌ Failed to process video.")
    finally:
        await status.delete()

async def handle_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message:
        return

    ref = msg.reply_to_message
    data = VIDEO_STORE.pop(ref.message_id, None)
    if not data:
        return

    await msg.delete()
    video, _ = data
    mp3 = video.with_suffix(".mp3")

    status = await context.bot.send_message(msg.chat.id, "🎵 Extracting audio…")

    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(mp3.with_suffix(".%(ext)s")),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
        }

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: yt_dlp.YoutubeDL(ydl_opts).download([str(video)]),
        )

        with open(mp3, "rb") as f:
            await context.bot.send_audio(msg.chat.id, f)

    finally:
        await status.delete()
        video.unlink(missing_ok=True)
        mp3.unlink(missing_ok=True)

async def auto_delete(chat_id: int, msg_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await app.bot.delete_message(chat_id, msg_id)
    except:
        pass

# ───────── MAIN ─────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mp3", handle_mp3))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    logger.info("BOT READY (polling)")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

if __name__ == "__main__":
    main()
