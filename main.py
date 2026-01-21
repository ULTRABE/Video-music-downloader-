#!/usr/bin/env python3
import os
import re
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

import yt_dlp
import ffmpeg
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ───────────────── CONFIG ─────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not BOT_TOKEN or not OWNER_ID:
    raise RuntimeError("BOT_TOKEN and OWNER_ID are required")

TEMP = Path("temp")
TEMP.mkdir(exist_ok=True)

MAX_CONCURRENT = 2
SEM = asyncio.Semaphore(MAX_CONCURRENT)

AUTHORIZED_GROUPS = set()
VIDEO_STORE = {}  # msg_id -> file path

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

ADULT_TTL = 300  # seconds

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("premium-bot")

# ───────────────── HELPERS ─────────────────
def domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "").lower()

def is_short(url: str) -> bool:
    u = url.lower()
    return any(x in u for x in ["/shorts", "/reel", "tiktok.com"])

async def auto_delete(bot, chat_id, msg_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, msg_id)
    except:
        pass

# ───────────────── DOWNLOADERS ─────────────────
async def download_video(url: str, short: bool, adult: bool) -> Path | None:
    ts = int(datetime.now().timestamp())
    prefix = "adult" if adult else "pub"
    out = TEMP / f"{prefix}_{ts}.%(ext)s"

    if adult:
        fmt = "best"
    elif short:
        fmt = "best[ext=mp4][filesize<8M]/best"
    else:
        fmt = "bv*[height<=720][fps<=30]+ba/b"

    ydl_opts = {
        "format": fmt,
        "outtmpl": str(out),
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }

    async with SEM:
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])
            return next(TEMP.glob(f"{prefix}_{ts}.*"), None)
        except Exception as e:
            log.error(f"Download failed: {e}")
            return None

async def extract_mp3(video_path: Path) -> Path | None:
    mp3 = video_path.with_suffix(".mp3")
    try:
        (
            ffmpeg
            .input(str(video_path))
            .output(str(mp3), acodec="libmp3lame", ab="192k")
            .overwrite_output()
            .run(quiet=True)
        )
        return mp3 if mp3.exists() else None
    except Exception as e:
        log.error(f"MP3 failed: {e}")
        return None

# ───────────────── HANDLERS ─────────────────
async def handle_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    urls = re.findall(r"https?://\S+", msg.text)
    if not urls:
        return

    url = urls[0]
    d = domain(url)
    chat = msg.chat
    private = chat.type == "private"

    await msg.delete()

    is_adult = any(x in d for x in ADULT_DOMAINS)
    is_public = any(x in d for x in PUBLIC_DOMAINS)

    # Group authorization
    if chat.type in ("group", "supergroup") and chat.id not in AUTHORIZED_GROUPS:
        return

    # Adult in group → redirect
    if is_adult and not private:
        kb = [[InlineKeyboardButton("🔞 Continue in Private", url=f"https://t.me/{ctx.bot.username}")]]
        await ctx.bot.send_message(
            chat.id,
            "🔒 Adult content is only allowed in private chat.",
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if not is_public and not is_adult:
        return

    status = await ctx.bot.send_message(chat.id, "⏳ Processing…")

    try:
        await status.edit_text("⬇️ Downloading…")
        vid = await download_video(url, is_short(url), is_adult)
        if not vid:
            raise RuntimeError("download failed")

        with open(vid, "rb") as f:
            sent = await ctx.bot.send_video(
                chat.id,
                f,
                supports_streaming=True,
                caption="✅ Ready",
            )

        VIDEO_STORE[sent.message_id] = vid

        if chat.type in ("group", "supergroup"):
            try:
                await sent.pin()
            except:
                pass

        if is_adult:
            asyncio.create_task(auto_delete(ctx.bot, chat.id, sent.message_id, ADULT_TTL))

    except Exception:
        await status.edit_text("❌ Failed to process video.")
    finally:
        await asyncio.sleep(1)
        await status.delete()

async def handle_mp3(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message:
        return

    ref = msg.reply_to_message
    if ref.message_id not in VIDEO_STORE:
        return

    await msg.delete()
    wait = await ctx.bot.send_message(msg.chat.id, "🎵 Converting to MP3…")

    try:
        mp3 = await extract_mp3(VIDEO_STORE[ref.message_id])
        if not mp3:
            raise RuntimeError
        with open(mp3, "rb") as f:
            await ctx.bot.send_audio(msg.chat.id, f)
    except:
        await ctx.bot.send_message(msg.chat.id, "❌ MP3 failed.")
    finally:
        await wait.delete()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("ℹ️ How it works", callback_data="help")]]
    await update.message.reply_text(
        "🎬 **Premium Video Downloader**\n\n"
        "• Paste a link\n"
        "• Bot deletes it\n"
        "• Lightning-fast download\n\n"
        "_Shorts, Reels & Audio supported_",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )

async def help_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "• Groups must be authorized\n"
        "• Adult content → Private only\n"
        "• Reply /mp3 to get audio"
    )

async def auth(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        cid = int(ctx.args[0])
        AUTHORIZED_GROUPS.add(cid)
        await update.message.reply_text("✅ Group authorized")
    except:
        await update.message.reply_text("Usage: /auth <chat_id>")

# ───────────────── MAIN ─────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mp3", handle_mp3))
    app.add_handler(CommandHandler("auth", auth))
    app.add_handler(CallbackQueryHandler(help_cb, pattern="help"))
    app.add_handler(MessageHandler(filters.Regex(r"https?://"), handle_media))

    log.info("BOT READY (polling)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
