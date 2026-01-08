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
    "nageshwar_main",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1
)

# -------- REGEX --------
YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
INSTA_REGEX = r"(instagram\.com|instagr\.am)/.+"
FB_REGEX = r"(facebook\.com|fb\.watch)/.+"
THREADS_REGEX = r"(threads\.net)/.+"
SNAP_REGEX = r"(snapchat\.com)/.+"

download_lock = asyncio.Lock()

# -------- FONT --------
def eren(text: str) -> str:
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    eren_map = (
        "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙"
        "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"
        "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    )
    return text.translate(str.maketrans(normal, eren_map))

# -------- SAFE DELETE --------
async def safe_delete(chat_id, message_id):
    try:
        await app.delete_messages(chat_id, message_id)
    except:
        pass

# -------- LINK DETECTOR --------
def detect_link(url: str):
    if re.match(YT_REGEX, url):
        return "yt"
    if re.match(INSTA_REGEX, url):
        return "insta"
    if re.match(FB_REGEX, url):
        return "fb"
    if re.match(THREADS_REGEX, url):
        return "threads"
    if re.match(SNAP_REGEX, url):
        return "snap"
    return None

# -------- START --------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        eren(
            "Send a link.\n\n"
            "• YouTube → full options\n"
            "• Insta / FB / Threads / Snap → auto best video"
        )
    )

# -------- GROUP HANDLER --------
@app.on_message(filters.text & filters.group)
async def group_handler(_, msg):
    source = detect_link(msg.text)
    if not source:
        return

    await safe_delete(msg.chat.id, msg.id)

    if source == "yt":
        await process_yt(msg, msg.text, "g720")
    else:
        await process_generic(msg, msg.text)

# -------- PRIVATE HANDLER --------
@app.on_message(filters.text & filters.private)
async def private_handler(_, msg):
    source = detect_link(msg.text)
    if not source:
        return

    if source == "yt":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(eren("🎵 Audio"), callback_data=f"a128|{msg.text}"),
                InlineKeyboardButton(eren("🎬 Video"), callback_data=f"video|{msg.text}")
            ]
        ])
        await msg.reply(eren("Choose format:"), reply_markup=kb)
    else:
        await safe_delete(msg.chat.id, msg.id)
        await process_generic(msg, msg.text)

# -------- CALLBACKS (YT ONLY) --------
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

    await process_yt(cq.message, url, action)

# =========================
# YOUTUBE CORE (UNCHANGED)
# =========================
async def process_yt(msg, url, mode):
    async with download_lock:
        chat_id = msg.chat.id
        status = await app.send_message(chat_id, eren("⬇️ Downloading…"))

        try:
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
                p = await asyncio.create_subprocess_exec(*cmd)
                await p.wait()

                await safe_delete(chat_id, status.id)
                await app.send_audio(chat_id, output)
                os.remove(output)
                return

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
            p = await asyncio.create_subprocess_exec(*cmd)
            await p.wait()

            await safe_delete(chat_id, status.id)
            await app.send_video(chat_id, output, supports_streaming=True)
            os.remove(output)

        except Exception:
            logging.exception("YT failed")
            await status.edit(eren("Error occurred."))

# ======================================
# GENERIC (INSTA / FB / THREADS / SNAP)
# ======================================
async def process_generic(msg, url):
    async with download_lock:
        chat_id = msg.chat.id
        status = await app.send_message(chat_id, eren("⬇️ Downloading…"))

        try:
            output = "video.mp4"
            cmd = [
                "yt-dlp",
                "-f", "bv*+ba/b",
                "--merge-output-format", "mp4",
                "-o", output,
                url
            ]
            p = await asyncio.create_subprocess_exec(*cmd)
            await p.wait()

            await safe_delete(chat_id, status.id)
            await app.send_video(chat_id, output, supports_streaming=True)
            os.remove(output)

        except Exception:
            logging.exception("Generic failed")
            await status.edit(eren("Error occurred."))

# -------- RUN --------
app.run()
