import os
import re
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app = Client(
    "nageshwar_final",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1
)

YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
download_lock = asyncio.Lock()

# ---------------- SAFE DELETE ----------------
async def safe_delete(chat_id, message_id):
    try:
        await app.delete_messages(chat_id, message_id)
    except:
        pass

# ---------------- COUNTDOWN ----------------
async def countdown_and_cleanup(chat_id, media_msg_id, seconds=120):
    msg = await app.send_message(chat_id, f"⏳ Self-destruct in {seconds}s")

    step = 5
    for remaining in range(seconds, 0, -step):
        try:
            await msg.edit_text(f"⏳ Self-destruct in {remaining}s")
        except:
            pass
        await asyncio.sleep(step)

    try:
        await msg.edit_text("💥 BOOM")
    except:
        pass

    await asyncio.sleep(1)
    await safe_delete(chat_id, media_msg_id)
    await safe_delete(chat_id, msg.id)

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "Send a YouTube link.\n\n"
        "• Groups → auto 720p video\n"
        "• Private → audio or video"
    )

# ---------------- LINK HANDLER ----------------
@app.on_message(filters.text & (filters.private | filters.group))
async def link_handler(_, msg):
    if not re.match(YT_REGEX, msg.text):
        return

    # GROUP → AUTO VIDEO
    if msg.chat.type in ("group", "supergroup"):
        await process_download(msg, msg.text, "g720")
        return

    # PRIVATE → OPTIONS
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"a128|{msg.text}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"video|{msg.text}")
        ]
    ])
    await msg.reply("Choose format:", reply_markup=kb)

# ---------------- CALLBACKS ----------------
@app.on_callback_query()
async def callbacks(_, cq):
    # BLOCK callbacks in groups
    if cq.message.chat.type != "private":
        await cq.answer("Use this in private chat.", show_alert=True)
        return

    action, url = cq.data.split("|", 1)

    if action == "video":
        await cq.message.edit(
            "Select video quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("480p", callback_data=f"v480|{url}"),
                    InlineKeyboardButton("720p", callback_data=f"v720|{url}")
                ],
                [
                    InlineKeyboardButton("1080p 60fps", callback_data=f"v1080|{url}")
                ]
            ])
        )
        return

    await process_download(cq.message, url, action)

# ---------------- DOWNLOAD CORE ----------------
async def process_download(msg, url, mode):
    async with download_lock:
        chat_id = msg.chat.id
        chat_type = msg.chat.type
        original_msg_id = msg.id

        # DELETE USER LINK IMMEDIATELY (GROUP ONLY)
        if chat_type in ("group", "supergroup"):
            await safe_delete(chat_id, original_msg_id)

        status = await app.send_message(chat_id, "⬇️ Downloading…")

        try:
            if mode == "g720":
                output = "video.mp4"
                fmt = "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]"

            elif mode.startswith("v"):
                output = "video.mp4"
                if mode == "v480":
                    fmt = "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]"
                elif mode == "v720":
                    fmt = "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]"
                else:
                    fmt = "bestvideo[ext=mp4][height<=1080][fps>30]+bestaudio[ext=m4a]"

            elif mode.startswith("a"):
                output = "audio.mp3"
                fmt = None

            else:
                await status.edit("❌ Invalid option.")
                return

            if fmt:
                cmd = [
                    "yt-dlp",
                    "-f", fmt,
                    "--merge-output-format", "mp4",
                    "-o", output,
                    url
                ]
            else:
                cmd = [
                    "yt-dlp",
                    "-x",
                    "--audio-format", "mp3",
                    "--audio-quality", mode[1:],
                    "-o", output,
                    url
                ]

            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()

            if not os.path.exists(output):
                await status.edit("❌ Download failed.")
                return

            if output.endswith(".mp4"):
                sent = await app.send_video(chat_id, output, supports_streaming=True)
            else:
                sent = await app.send_audio(chat_id, output)

            if chat_type in ("group", "supergroup"):
                await safe_delete(chat_id, status.id)
                asyncio.create_task(
                    countdown_and_cleanup(chat_id, sent.id, 120)
                )

            os.remove(output)

        except Exception as e:
            logging.exception(e)
            await status.edit("❌ Error occurred.")

# ---------------- RUN ----------------
app.run()
