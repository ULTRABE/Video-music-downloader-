#!/usr/bin/env python3
import os
import re
import asyncio
import logging
import shutil
from pathlib import Path
from urllib.parse import urlparse

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
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("downloader")

# ───────── ENV ─────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

# ───────── PATHS ─────────
BASE_DIR = Path("/tmp/media")
BASE_DIR.mkdir(exist_ok=True)

# ───────── LIMITS ─────────
MAX_CONCURRENT = 2
VIDEO_LIMIT_MB = 45
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# ───────── DOMAIN RULES ─────────
PUBLIC_SUFFIXES = (
    "youtube.com", "youtu.be",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "tiktok.com",
)

ADULT_KEYWORDS = (
    "pornhub",
    "xvideos",
    "xhamster",
    "xnxx",
    "youporn",
)

# message_id → file_path
KNOWN_VIDEOS = {}

# ───────── HELPERS ─────────
def domain(url: str) -> str:
    return urlparse(url).netloc.lower()

def is_public(url: str) -> bool:
    d = domain(url)
    return any(d.endswith(s) for s in PUBLIC_SUFFIXES)

def is_adult(url: str) -> bool:
    d = domain(url)
    return any(k in d for k in ADULT_KEYWORDS)

def is_short(url: str) -> bool:
    u = url.lower()
    return any(k in u for k in ["/shorts", "/reel", "/reels", "tiktok.com"])

def size_mb(p: Path) -> float:
    return p.stat().st_size / (1024 * 1024)

# ───────── DOWNLOAD ─────────
async def download(url: str, ydl_opts: dict, workdir: Path) -> Path | None:
    async with download_semaphore:
        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])
        except Exception as e:
            logger.error(f"yt-dlp error: {e}")
            return None

    files = list(workdir.glob("*"))
    return files[0] if files else None

# ───────── HANDLERS ─────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎥 **Premium Video Downloader**\n\n"
        "• Send a video link\n"
        "• Works in groups & private\n"
        "• Reply `/mp3` to my video for audio\n\n"
        "⚡ Fast • Stable • Clean",
        parse_mode="Markdown"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = msg.chat
    text = msg.text or ""

    urls = re.findall(r"https?://\S+", text)
    if not urls:
        return

    url = urls[0]
    private = chat.type == "private"

    try:
        await msg.delete()
    except:
        pass

    if is_adult(url) and not private:
        await context.bot.send_message(
            chat.id,
            "🔞 Adult content is private-only.\nOpen the bot in DM."
        )
        return

    if not is_public(url) and not is_adult(url):
        await context.bot.send_message(chat.id, "❌ Unsupported link.")
        return

    status = await context.bot.send_message(chat.id, "⬇️ Downloading…")

    work = BASE_DIR / f"{chat.id}_{msg.message_id}"
    work.mkdir(exist_ok=True)

    outtmpl = str(work / "%(title)s.%(ext)s")

    if is_adult(url):
        ydl_opts = {
            "outtmpl": outtmpl,
            "format": "best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }
    else:
        fmt = (
            "best[ext=mp4][filesize<25M]/best[ext=mp4]"
            if is_short(url)
            else "bestvideo[ext=mp4][height<=720][fps<=30]+bestaudio/best"
        )
        ydl_opts = {
            "outtmpl": outtmpl,
            "format": fmt,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }

    file = await download(url, ydl_opts, work)
    if not file:
        await status.edit_text("❌ Download failed.")
        shutil.rmtree(work, ignore_errors=True)
        return

    try:
        if is_adult(url) and private and size_mb(file) > VIDEO_LIMIT_MB:
            await context.bot.send_document(
                chat.id,
                document=open(file, "rb"),
                caption="📁 Sent as document (Telegram size limit)",
                filename=file.name,
            )
        else:
            sent = await context.bot.send_video(
                chat.id,
                video=open(file, "rb"),
                supports_streaming=True,
                caption="✅ Video ready",
            )
            KNOWN_VIDEOS[sent.message_id] = file
            if chat.type in ("group", "supergroup") and not is_adult(url):
                try:
                    await context.bot.pin_chat_message(chat.id, sent.message_id)
                except:
                    pass
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(chat.id, "❌ Upload failed.")
    finally:
        try:
            await status.delete()
        except:
            pass
        shutil.rmtree(work, ignore_errors=True)

async def mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.reply_to_message
    if not reply or reply.message_id not in KNOWN_VIDEOS:
        return

    video = KNOWN_VIDEOS.pop(reply.message_id)
    audio = video.with_suffix(".mp3")

    cmd = ["ffmpeg", "-y", "-i", str(video), "-vn", "-ab", "192k", str(audio)]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()

    if audio.exists():
        await context.bot.send_audio(
            update.effective_chat.id,
            audio=open(audio, "rb"),
            title=audio.stem,
        )
        audio.unlink(missing_ok=True)

# ───────── MAIN ─────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # IMPORTANT: kill webhook before polling
    asyncio.get_event_loop().run_until_complete(app.bot.delete_webhook())

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mp3", mp3))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    logger.info("BOT READY (polling)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
