import os
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

download_queue = asyncio.Queue()
active_users = set()

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\n"
        "• Private: audio / video options\n"
        "• Group: paste link → auto video"
    )

# =========================================================
# ====================== GROUP MODE =======================
# =========================================================
@app.on_message(filters.group)
async def group_auto(_, msg):
    # Allow only real group types
    if msg.chat.type not in ("group", "supergroup"):
        return

    if not msg.entities:
        return

    url = None
    for e in msg.entities:
        if e.type == "url":
            url = msg.text[e.offset : e.offset + e.length]
            break

    if not url:
        return

    user_id = msg.from_user.id
    if user_id in active_users:
        return

    active_users.add(user_id)

    # delete user message immediately
    try:
        await msg.delete()
    except:
        pass

    await download_queue.put((msg.chat.id, url, user_id))

# =========================================================
# ===================== PRIVATE MODE ======================
# =========================================================
@app.on_message(filters.private & filters.text)
async def private_links(_, msg):
    if not msg.entities:
        return

    url = None
    for e in msg.entities:
        if e.type == "url":
            url = msg.text[e.offset : e.offset + e.length]
            break

    if not url:
        return

    user_id = msg.from_user.id
    if user_id in active_users:
        await msg.reply("⚠️ You already have an active download.")
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{url}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"video|{url}")
        ]
    ])
    await msg.reply("Choose format:", reply_markup=kb)

# ---------------- CALLBACKS (PRIVATE) ----------------
@app.on_callback_query()
async def callbacks(_, cq):
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
    await cq.message.edit("Queued…")
    await download_queue.put((cq.message.chat.id, url, user_id))

# =========================================================
# ======================== WORKER =========================
# =========================================================
async def worker():
    while True:
        chat_id, url, user_id = await download_queue.get()

        try:
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

            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()

            if os.path.exists(output):
                await app.send_video(chat_id, output, supports_streaming=True)
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
