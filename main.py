import os
import re
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- BASIC SETUP ----------------
logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app = Client(
    "nageshwar_v4",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1
)

YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"

download_lock = asyncio.Lock()

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "Send a YouTube link.\n\n"
        "• Groups → auto video\n"
        "• Private → choose audio/video"
    )

# ---------------- LINK HANDLER ----------------
@app.on_message(filters.text & (filters.private | filters.group))
async def link_handler(_, msg):
    if not re.match(YT_REGEX, msg.text):
        return

    # GROUP = AUTO VIDEO
    if msg.chat.type in ("group", "supergroup"):
        await process_download(msg, msg.text, mode="auto")
        return

    # PRIVATE = OPTIONS
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{msg.text}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"video|{msg.text}")
        ]
    ])
    await msg.reply("Choose format:", reply_markup=kb)

# ---------------- CALLBACKS ----------------
@app.on_callback_query()
async def callbacks(_, cq):
    action, url = cq.data.split("|", 1)

    if action == "audio":
        await cq.message.edit(
            "Select audio quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("128 kbps", callback_data=f"a128|{url}"),
                    InlineKeyboardButton("320 kbps", callback_data=f"a320|{url}")
                ]
            ])
        )
        return

    if action == "video":
        await cq.message.edit(
            "Select video quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("480p", callback_data=f"v480|{url}"),
                    InlineKeyboardButton("720p", callback_data=f"v720|{url}")
                ]
            ])
        )
        return

    await process_download(cq.message, url, action)

# ---------------- DOWNLOAD CORE ----------------
async def process_download(msg, url, mode):
    async with download_lock:
        status = await msg.reply("⬇️ Downloading…")

        try:
            if mode == "auto":
                output = "video.mp4"
                cmd = [
                    "yt-dlp",
                    "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
                    "--merge-output-format", "mp4",
                    "-o", output,
                    url
                ]

            elif mode.startswith("a"):
                output = "audio.mp3"
                cmd = [
                    "yt-dlp",
                    "-x",
                    "--audio-format", "mp3",
                    "--audio-quality", mode[1:],
                    "-o", output,
                    url
                ]

            else:
                res = {"v480": "480", "v720": "720"}[mode]
                output = "video.mp4"
                cmd = [
                    "yt-dlp",
                    "-f",
                    f"bestvideo[ext=mp4][height<={res}]+bestaudio[ext=m4a]",
                    "--merge-output-format", "mp4",
                    "-o", output,
                    url
                ]

            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()

            if not os.path.exists(output):
                await status.edit("❌ Download failed.")
                return

            if output.endswith(".mp4"):
                await app.send_video(msg.chat.id, output, supports_streaming=True)
            else:
                await app.send_audio(msg.chat.id, output)

            os.remove(output)
            await status.delete()

        except Exception as e:
            logging.exception(e)
            await status.edit("❌ Error occurred.")

# ---------------- RUN ----------------
app.run()
