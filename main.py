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

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "Send a YouTube link.\n\n"
        "• Groups → auto 720p video\n"
        "• Private → audio or video"
    )

# ---------------- GROUP HANDLER ----------------
@app.on_message(filters.text & filters.group)
async def group_link_handler(_, msg):
    if not re.match(YT_REGEX, msg.text):
        return

    await safe_delete(msg.chat.id, msg.id)
    await process_download(msg, msg.text, "g720")

# ---------------- PRIVATE HANDLER ----------------
@app.on_message(filters.text & filters.private)
async def private_link_handler(_, msg):
    if not re.match(YT_REGEX, msg.text):
        return

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

        status = await app.send_message(chat_id, "⬇️ Downloading…")

        try:
            # -------- AUDIO --------
            if mode.startswith("a"):
                output = "audio.mp3"
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

                await safe_delete(chat_id, status.id)
                sent = await app.send_audio(chat_id, output)
                os.remove(output)
                return

            # -------- VIDEO --------
            if mode in ("g720", "v720"):
                fmt = "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]"
            elif mode == "v480":
                fmt = "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]"
            elif mode == "v1080":
                fmt = "bestvideo[ext=mp4][height<=1080][fps>30]+bestaudio[ext=m4a]"
            else:
                await status.edit("❌ Invalid option.")
                return

            output = "video.mp4"

            cmd = [
                "yt-dlp",
                "-f", fmt,
                "--merge-output-format", "mp4",
                "-o", output,
                url
            ]

            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()

            if not os.path.exists(output):
                await status.edit("❌ Download failed.")
                return

            await safe_delete(chat_id, status.id)

            sent = await app.send_video(
                chat_id,
                output,
                supports_streaming=True,
                caption="💓 @nagudownloaderbot" if chat_type in ("group", "supergroup") else None
            )

            os.remove(output)

            if chat_type in ("group", "supergroup"):
                await asyncio.sleep(120)
                await safe_delete(chat_id, sent.id)

        except Exception:
            logging.exception("Download failed")
            await status.edit("❌ Error occurred.")

# ---------------- RUN ----------------
app.run()
