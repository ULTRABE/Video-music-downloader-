import os
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

download_lock = asyncio.Lock()

# ---------------- FONT ----------------
def eren(text: str) -> str:
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    styled = (
        "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙"
        "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"
        "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    )
    return text.translate(str.maketrans(normal, styled))

# ---------------- SAFE DELETE ----------------
async def safe_delete(chat_id, message_id):
    try:
        await app.delete_messages(chat_id, message_id)
    except:
        pass

# ---------------- URL CLEAN + DETECT ----------------
def clean_url(text: str) -> str:
    return text.strip().split()[0]

def detect_platform(text: str):
    url = clean_url(text)

    if "youtu.be" in url or "youtube.com" in url:
        return "yt", url
    if "instagram.com" in url:
        return "insta", url
    if "facebook.com" in url or "fb.watch" in url:
        return "fb", url
    if "threads.net" in url:
        return "threads", url
    if "snapchat.com" in url:
        return "snap", url

    return None, None

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        eren(
            "Send a link.\n\n"
            "• YouTube → audio + video\n"
            "• Instagram / Facebook / Threads / Snapchat → video only"
        )
    )

# ================= GROUP HANDLER =================
@app.on_message(filters.text & filters.group)
async def group_handler(_, msg):
    platform, url = detect_platform(msg.text)
    if not platform:
        return

    await safe_delete(msg.chat.id, msg.id)

    # groups always auto 720p
    await process_download(msg, url, platform, "g720")

# ================= PRIVATE HANDLER =================
@app.on_message(filters.text & filters.private)
async def private_handler(_, msg):
    platform, url = detect_platform(msg.text)
    if not platform:
        return

    if platform == "yt":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(eren("🎵 Audio"), callback_data=f"yt|a128|{url}"),
                InlineKeyboardButton(eren("🎬 Video"), callback_data=f"yt|video|{url}")
            ]
        ])
        await msg.reply(eren("Choose format:"), reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(eren("480p"), callback_data=f"{platform}|v480|{url}"),
                InlineKeyboardButton(eren("720p"), callback_data=f"{platform}|v720|{url}")
            ],
            [
                InlineKeyboardButton(eren("Best"), callback_data=f"{platform}|vbest|{url}")
            ]
        ])
        await msg.reply(eren("Select video quality:"), reply_markup=kb)

# ================= CALLBACKS =================
@app.on_callback_query()
async def callbacks(_, cq):
    platform, action, url = cq.data.split("|", 2)

    if platform == "yt" and action == "video":
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

    await process_download(cq.message, url, platform, action)

# ================= DOWNLOAD CORE =================
async def process_download(msg, url, platform, mode):
    async with download_lock:
        chat_id = msg.chat.id
        status = await app.send_message(chat_id, eren("⬇️ Downloading…"))

        try:
            # -------- AUDIO (YT ONLY) --------
            if platform == "yt" and mode.startswith("a"):
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

                await safe_delete(chat_id, status.id)
                await app.send_audio(chat_id, output)
                os.remove(output)
                return

            # -------- VIDEO FORMAT --------
            if platform == "yt":
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

            await safe_delete(chat_id, status.id)
            await app.send_video(chat_id, output, supports_streaming=True)
            os.remove(output)

        except Exception:
            logging.exception("Download failed")
            await status.edit(eren("Error occurred."))

# ================= RUN =================
app.run()
