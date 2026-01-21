# main.py
import os
import re
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

import yt_dlp
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
logger = logging.getLogger("premium-downloader")

# ───────────────── ENV ─────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

# ───────────────── CONFIG ─────────────────
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

MAX_CONCURRENT = 2
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

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

# message_id -> local video file
SENT_VIDEOS = {}

# ───────────────── HELPERS ─────────────────
def normalize_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc.replace("www.", "")

def is_short_form(url: str) -> bool:
    u = url.lower()
    return any(x in u for x in [
        "/shorts",
        "/reel",
        "/reels",
        "tiktok.com",
        "instagram.com/reel",
    ])

def premium_status(step: int) -> str:
    steps = [
        "⏳ Analyzing link…",
        "⬇️ Downloading media…",
        "⚡ Optimizing for Telegram…",
        "📤 Uploading…",
    ]
    return steps[min(step, len(steps) - 1)]

# ───────────────── DOWNLOADERS ─────────────────
async def download_public_video(url: str, short: bool) -> Path | None:
    ts = int(datetime.now().timestamp())
    out = TEMP_DIR / f"public_{ts}.%(ext)s"

    fmt = (
        "bv*+ba/b"                     # SHORTS / REELS (fast)
        if short else
        "bv*[height<=720][fps<=30]+ba/b"  # NORMAL VIDEOS
    )

    ydl_opts = {
        "outtmpl": str(out),
        "format": fmt,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

    async with download_semaphore:
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])

            for f in TEMP_DIR.glob(f"public_{ts}.*"):
                return f
        except Exception as e:
            logger.error(f"Public download failed: {e}")
            return None

async def download_adult_video(url: str) -> Path | None:
    ts = int(datetime.now().timestamp())
    out = TEMP_DIR / f"adult_{ts}.%(ext)s"

    # Adult sites prefer simple formats, no constraints
    ydl_opts = {
        "outtmpl": str(out),
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

    async with download_semaphore:
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])

            for f in TEMP_DIR.glob(f"adult_{ts}.*"):
                return f
        except Exception as e:
            logger.error(f"Adult download failed: {e}")
            return None

async def extract_mp3_from_video(video_path: Path) -> Path | None:
    ts = int(datetime.now().timestamp())
    out = TEMP_DIR / f"audio_{ts}.%(ext)s"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await loop.run_in_executor(None, ydl.download, [video_path.as_uri()])

        for f in TEMP_DIR.glob(f"audio_{ts}.*"):
            return f
    except Exception as e:
        logger.error(f"MP3 extraction failed: {e}")
        return None

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
    is_private = chat.type == "private"

    try:
        await msg.delete()
    except:
        pass

    is_adult = any(d in domain for d in ADULT_DOMAINS)
    is_public = any(d in domain for d in PUBLIC_DOMAINS)

    # ── GROUP + ADULT BLOCK ──
    if is_adult and not is_private:
        warn = await context.bot.send_message(
            chat.id,
            "🚫 Adult content is only available in private chat."
        )
        await asyncio.sleep(5)
        await warn.delete()
        return

    if not is_public and not is_adult:
        return

    status = await context.bot.send_message(chat.id, premium_status(0))

    try:
        await status.edit_text(premium_status(1))

        if is_adult:
            video = await download_adult_video(url)
        else:
            video = await download_public_video(url, is_short_form(url))

        if not video:
            raise RuntimeError("download failed")

        await status.edit_text(premium_status(3))

        with open(video, "rb") as f:
            sent = await context.bot.send_video(
                chat.id,
                f,
                supports_streaming=True,
                caption="✅ Download complete",
            )

        SENT_VIDEOS[sent.message_id] = video

        if chat.type in ("group", "supergroup") and not is_adult:
            try:
                await sent.pin()
            except:
                pass

        if is_adult:
            note = await context.bot.send_message(
                chat.id,
                "🔒 This video will auto-delete in 5 minutes.\nSave it if needed."
            )
            await asyncio.sleep(300)
            await sent.delete()
            await note.delete()

    except Exception:
        await status.edit_text("❌ Failed to process this video.")
    finally:
        await asyncio.sleep(2)
        await status.delete()

async def handle_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    ref = msg.reply_to_message
    if ref.message_id not in SENT_VIDEOS:
        return

    try:
        await msg.delete()
    except:
        pass

    status = await context.bot.send_message(msg.chat.id, "🎵 Extracting audio…")

    try:
        audio = await extract_mp3_from_video(SENT_VIDEOS[ref.message_id])
        if not audio:
            raise RuntimeError("mp3 failed")

        with open(audio, "rb") as f:
            await context.bot.send_audio(
                msg.chat.id,
                f,
                title="Audio",
                performer="Downloader",
            )

    except Exception:
        await status.edit_text("❌ Audio extraction failed.")
    finally:
        await asyncio.sleep(2)
        await status.delete()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("ℹ️ How it works", callback_data="help")]]
    await update.message.reply_text(
        "🎬 **Premium Video Downloader**\n\n"
        "• Paste a video link\n"
        "• Bot deletes it instantly\n"
        "• Downloads & sends video\n"
        "• Shorts & Reels = lightning fast\n\n"
        "_Reply `/mp3` to any video for audio_",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )

async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📌 Supported platforms:\n"
        "YouTube • Instagram • TikTok • X • Facebook\n\n"
        "• Groups: auto-pin\n"
        "• Private: adult supported\n"
        "• Fast • Clean • Reliable"
    )

# ───────────────── MAIN ─────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mp3", handle_mp3))
    app.add_handler(CallbackQueryHandler(help_cb, pattern="help"))
    app.add_handler(MessageHandler(filters.Regex(r"https?://"), handle_media))

    logger.info("BOT READY (polling)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
