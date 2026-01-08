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
    "all_in_one_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1
)

# -------- REGEX --------
YT = r"(youtube\.com|youtu\.be)"
INSTA = r"(instagram\.com|instagr\.am)"
FB = r"(facebook\.com|fb\.watch)"
THREADS = r"(threads\.net)"
SNAP = r"(snapchat\.com)"

download_lock = asyncio.Lock()

# -------- FONT --------
def eren(text: str) -> str:
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    styled = (
        "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙"
        "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"
        "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    )
    return text.translate(str.maketrans(normal, styled))

# -------- SAFE DELETE --------
async def safe_delete(chat_id, message_id):
    try:
        await app.delete_messages(chat_id, message_id)
    except:
        pass

# -------- DETECT PLATFORM --------
def detect(url: str):
    if re.search(YT, url): return "yt"
    if re.search(INSTA, url): return "insta"
    if re.search(FB, url): return "fb"
    if re.search(THREADS, url): return "threads"
    if re.search(SNAP, url): return "snap"
    return None

# -------- START --------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        eren(
            "Send a link.\n\n"
            "YouTube → audio + video\n"
            "Instagram / Facebook / Threads / Snapchat → video only"
        )
    )

# -------- GROUP HANDLER --------
@app.on_message(filters.text & filters.group)
async def group_handler(_, msg):
    src = detect(msg.text)
    if not src:
        return

    await safe_delete(msg.chat.id, msg.id)

    # group = auto 720p
    await process_download(msg, msg.text, src, "g720")

# -------- PRIVATE HANDLER --------
@app.on_message(filters.text & filters.private)
async def private_handler(_, msg):
    src = detect(msg.text)
    if not src:
        return

    if src == "yt":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(eren("🎵 Audio"), callback_data=f"yt|a128|{msg.text}"),
                InlineKeyboardButton(eren("🎬 Video"), callback_data=f"yt|video|{msg.text}")
            ]
        ])
        await msg.reply(eren("Choose format:"), reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(eren("480p"), callback_data=f"{src}|v480|{msg.text}"),
                InlineKeyboardButton(eren("720p"), callback_data=f"{src}|v720|{msg.text}")
            ],
            [
                InlineKeyboardButton(eren("Best"), callback_data=f"{src}|vbest|{msg.text}")
            ]
        ])
        await msg.reply(eren("Select video quality:"), reply_markup=kb)

# -------- CALLBACKS --------
@app.on_callback_query()
async def callbacks(_, cq):
    src, action, url = cq.data.split("|", 2)

    if src == "yt" and action == "video":
        await cq.message.edit(
            eren("Select video quality:"),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(eren("480p"), callback_data=f"yt|v480|{url}"),
                    InlineKeyboardButton(eren("720p"), callback_data=f"yt|v720|{url}")
                ],
                [
                    InlineKeyboardButton(eren("1080p 60fps"), callback_data=f"yt|v1080|{url}")
                ]
            ])
        )
        return

    await process_download(cq.message, url, src, action)

# -------- DOWNLOAD CORE --------
async def process_download(msg, url, src, mode):
    async with download_lock:
        chat_id = msg.chat.id
        status = await app.send_message(chat_id, eren("⬇️ Downloading…"))

        try:
            # -------- AUDIO (YT ONLY) --------
            if src == "yt" and mode.startswith("a"):
                out = "audio.mp3"
                cmd = [
                    "yt-dlp",
                    "-x",
                    "--audio-format", "mp3",
                    "--audio-quality", mode[1:],
                    "-o", out,
                    url
                ]
                p = await asyncio.create_subprocess_exec(*cmd)
                await p.wait()

                await safe_delete(chat_id, status.id)
                await app.send_audio(chat_id, out)
                os.remove(out)
                return

            # -------- VIDEO FORMAT --------
            if src == "yt":
                if mode in ("g720", "v720"):
                    fmt = "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]"
                elif mode == "v480":
                    fmt = "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]"
                elif mode == "v1080":
                    fmt = "bestvideo[ext=mp4][height<=1080][fps>30]+bestaudio[ext=m4a]"
                else:
                    fmt = "bv*+ba/b"
            else:
                if mode in ("g720", "v720"):
                    fmt = "bestvideo[height<=720]+bestaudio/best"
                elif mode == "v480":
                    fmt = "bestvideo[height<=480]+bestaudio/best"
                else:
                    fmt = "bv*+ba/b"

            out = "video.mp4"
            cmd = [
                "yt-dlp",
                "-f", fmt,
                "--merge-output-format", "mp4",
                "-o", out,
                url
            ]
            p = await asyncio.create_subprocess_exec(*cmd)
            await p.wait()

            await safe_delete(chat_id, status.id)
            await app.send_video(chat_id, out, supports_streaming=True)
            os.remove(out)

        except Exception:
            logging.exception("Download failed")
            await status.edit(eren("Error occurred."))

# -------- RUN --------
app.run()
