import os
import re
import asyncio
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- SETUP ----------------
logging.basicConfig(level=logging.INFO)
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "nageshwar",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workers=1
)

URL_REGEX = r"https?://\S+"

download_queue = asyncio.Queue()
active_users = set()
task_counter = 0

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\n"
        "Private: audio / video options\n"
        "Group: paste link → auto fast video"
    )

# =========================================================
# ====================== GROUP MODE =======================
# =========================================================
@app.on_message(filters.group)
async def group_auto(_, msg):
    # Explicitly allow both group & supergroup
    if msg.chat.type not in ("group", "supergroup"):
        return

    content = msg.text or msg.caption or ""
    if not content or not re.search(URL_REGEX, content):
        return

    user_id = msg.from_user.id
    if user_id in active_users:
        return

    active_users.add(user_id)

    # delete user message ASAP
    try:
        await msg.delete()
    except:
        pass

    global task_counter
    task_counter += 1

    await download_queue.put(
        (msg.chat.id, "auto_video", content, user_id)
    )

# =========================================================
# ===================== PRIVATE MODE ======================
# =========================================================
@app.on_message(filters.private)
async def private_links(_, msg):
    content = msg.text or msg.caption or ""
    if not content:
        return

    # extract URL from entities if needed
    if not re.search(URL_REGEX, content) and msg.entities:
        for e in msg.entities:
            if e.type in ("url", "text_link"):
                content = e.url or content
                break

    if not re.search(URL_REGEX, content):
        return

    user_id = msg.from_user.id
    if user_id in active_users:
        await msg.reply("⚠️ You already have an active download.")
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{content}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"video|{content}")
        ]
    ])
    await msg.reply("Choose format:", reply_markup=kb)

# ---------------- CALLBACKS (PRIVATE ONLY) ----------------
@app.on_callback_query()
async def callbacks(_, cq):
    global task_counter
    data = cq.data.split("|")
    user_id = cq.from_user.id
    url = data[1]

    if user_id in active_users:
        await cq.answer("Already downloading", show_alert=True)
        return

    if data[0] == "audio":
        await cq.message.edit(
            "Audio quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("64 kbps", callback_data=f"a64|{url}"),
                    InlineKeyboardButton("128 kbps", callback_data=f"a128|{url}"),
                    InlineKeyboardButton("320 kbps", callback_data=f"a320|{url}")
                ]
            ])
        )
        return

    if data[0] == "video":
        await cq.message.edit(
            "Video quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("480p", callback_data=f"v480|{url}"),
                    InlineKeyboardButton("720p", callback_data=f"v720|{url}")
                ],
                [
                    InlineKeyboardButton("1080p", callback_data=f"v1080|{url}")
                ]
            ])
        )
        return

    active_users.add(user_id)
    task_counter += 1

    await cq.message.edit("Queued…")
    await download_queue.put(
        (cq.message.chat.id, data[0], url, user_id)
    )

# =========================================================
# ======================== WORKER =========================
# =========================================================
async def worker():
    while True:
        chat_id, mode, url, user_id = await download_queue.get()

        try:
            if mode == "auto_video":
                output = "out.mp4"
                cmd = [
                    "yt-dlp",
                    "-f", "best[ext=mp4][fps<=30]/best[ext=mp4]/best",
                    "--concurrent-fragments", "4",
                    "--no-part",
                    "--merge-output-format", "mp4",
                    "-o", output,
                    url
                ]

            elif mode.startswith("a"):
                output = "out.mp3"
                cmd = [
                    "yt-dlp",
                    "-x",
                    "--audio-format", "mp3",
                    "--audio-quality", mode[1:],
                    "-o", output,
                    url
                ]

            else:  # private video
                res = {"v480":"480","v720":"720","v1080":"1080"}[mode]
                output = "out.mp4"
                cmd = [
                    "yt-dlp",
                    "-f",
                    f"best[ext=mp4][height<={res}][fps<=30]/best",
                    "--concurrent-fragments", "4",
                    "--merge-output-format", "mp4",
                    "-o", output,
                    url
                ]

            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()

            if os.path.exists(output):
                if output.endswith(".mp4"):
                    await app.send_video(chat_id, output, supports_streaming=True)
                else:
                    await app.send_audio(chat_id, output)
                os.remove(output)

        except Exception:
            logging.exception("Download failed")

        finally:
            active_users.discard(user_id)
            download_queue.task_done()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
