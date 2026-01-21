#!/usr/bin/env python3
import os
import re
import asyncio
import logging
import shutil
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

import yt_dlp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# ───────────── LOGGING ─────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("downloader")

# ───────────── ENV ─────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

# ───────────── PATHS ─────────────
BASE_DIR = Path("/tmp/media")
BASE_DIR.mkdir(exist_ok=True)

# ───────────── LIMITS ─────────────
MAX_CONCURRENT = 2
VIDEO_LIMIT_MB = 45
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# ───────────── DOMAIN RULES ─────────────
PUBLIC_SUFFIXES = (
    "youtube.com", "youtu.be",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "tiktok.com",
)

ADULT_SUFFIXES = (
    "pornhub.org",
    "xvideos.com",
    "xhamster44.desi",
    "xnxx.con",
    "youporn.com",
)

# message_id → file_path
KNOWN_VIDEOS = {}

# ───────────── HELPERS ─────────────
def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()

def is_public(url: str) -> bool:
    d = domain_of(url)
    return any(d.endswith(s) for s in PUBLIC_SUFFIXES)

def is_adult(url: str) -> bool:
    d = domain_of(url)
    return any(s in d for s in ADULT_SUFFIXES)

def is_short(url: str) -> bool:
    u = url.lower()
    return any(k in u for k in ["/shorts", "/reel", "/reels", "tiktok.com"])

def file_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)

# ───────────── YT-DLP OPTIONS ─────────────
def ydl_opts_public(url: str, out: Path):
    if is_short(url):
        fmt = "best[ext=mp4][filesize<25M]/best[ext=mp4]"
    else:
        fmt = "bestvideo[ext=mp4][height<=720][fps<=30]+bestaudio/best[ext=m4a]/best"
    return {
        "outtmpl": str(out),
        "format": fmt,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

def ydl_opts_adult(out: Path):
    return {
        "outtmpl": str(out),
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

# ───────────── DOWNLOAD ─────────────
async def download(url: str, opts: dict) -> Path | None:
    async with download_semaphore:
        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    files = list(Path(opts["outtmpl"]).parent.glob("*"))
    return files[0] if files else None

# ───────────── HANDLERS ─────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎥 **Premium Video Downloader**\n\n"
        "• Send a video link\n"
        "• Works in groups & private\n"
        "• Reply `/mp3` to my video for audio\n\n"
        "⚡ Fast • Clean • Reliable",
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
            "🔞 Adult content is private-only.\nOpen the bot in DM.",
        )
        return

    if not is_public(url) and not is_adult(url):
        await context.bot.send_message(chat.id, "❌ Unsupported link.")
        return

    status = await context.bot.send_message(chat.id, "⬇️ Downloading…")

    work = BASE_DIR / f"{chat.id}_{msg.message_id}"
    work.mkdir(exist_ok=True)
    out = work / "%(title)s.%(ext)s"

    opts = (
        ydl_opts_adult(out)
        if is_adult(url)
        else ydl_opts_public(url, out)
    )

    file = await download(url, opts)
    if not file:
        await status.edit_text("❌ Download failed.")
        shutil.rmtree(work, ignore_errors=True)
        return

    size = file_mb(file)
    caption = "✅ Video ready"

    try:
        if is_adult(url) and private and size > VIDEO_LIMIT_MB:
            await context.bot.send_document(
                chat.id,
                document=open(file, "rb"),
                caption="📁 Sent as document (size limit)",
                filename=file.name,
            )
        else:
            await context.bot.send_video(
                chat.id,
                video=open(file, "rb"),
                supports_streaming=True,
                caption=caption,
            )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(chat.id, "❌ Upload failed.")
    finally:
        try:
            await status.delete()
        except:
            pass

    if chat.type in ("group", "supergroup") and not is_adult(url):
        try:
            await context.bot.pin_chat_message(chat.id, msg.message_id + 1)
        except:
            pass

    KNOWN_VIDEOS[msg.message_id + 1] = file
    shutil.rmtree(work, ignore_errors=True)

async def mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.reply_to_message
    if not reply or reply.message_id not in KNOWN_VIDEOS:
        return

    video = KNOWN_VIDEOS.pop(reply.message_id)
    audio = video.with_suffix(".mp3")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vn", "-ab", "192k",
        str(audio),
    ]

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

    try:
        audio.unlink()
    except:
        pass

# ───────────── MAIN ─────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mp3", mp3))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    logger.info("BOT READY (polling)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
