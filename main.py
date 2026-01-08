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

# ---------------- EREN FONT (SERIF BOLD) ----------------
def eren(text: str) -> str:
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    eren_map = (
        "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙"
        "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"
        "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    )
    return text.translate(str.maketrans(normal, eren_map))

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
        eren(
            "Send a YouTube link.\n\n"
            "• Groups → auto 720p video\n"
            "• Private → audio or video"
        )
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
            InlineKeyboardButton(eren("🎵 Audio"), callback_data=f"a128|{msg.text}"),
            InlineKeyboardButton(eren("🎬 Video"), callback_data=f"video|{msg.text}")
        ]
    ])
    await msg.reply(eren("Choose format:"), reply_markup=kb)

# ---------------- CALLBACKS ----------------
@app.on_callback_query()
async def callbacks(_, cq):
    action, url = cq.data.split("|", 1)

    if action == "video":
        await cq.message.edit(
            eren("Select video quality:"),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(eren("480p"), callback_data=f"v480|{url}"),
                    InlineKeyboardButton(eren("720p"), callback_data=f"v720|{url}")
                ],
                [
                    InlineKeyboardButton(eren("1080p 60fps"), callback_data=f"v1080|{url}")
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

        status = await app.send_message(chat_id, eren("⬇️ Downloading…"))

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
                    await status.edit(eren("Download failed."))
                    return

                await safe_delete(chat_id, status.id)
                await app.send_audio(chat_id, output)
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
                await status.edit(eren("Invalid option."))
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
                await status.edit(eren("Download failed."))
                return

            await safe_delete(chat_id, status.id)

            # IMPORTANT FIX:
            # caption must be a NORMAL string (not stylized),
            # otherwise Telegram may silently drop it
            caption_text = "💓 @nagudownloaderbot" if chat_type in ("group", "supergroup") else None

            sent = await app.send_video(
                chat_id,
                output,
                supports_streaming=True,
                caption=caption_text
            )

            os.remove(output)

            if chat_type in ("group", "supergroup"):
                await asyncio.sleep(120)
                await safe_delete(chat_id, sent.id)

        except Exception:
            logging.exception("Download failed")
            await status.edit(eren("Error occurred."))

# ---------------- RUN ----------------
app.run()
