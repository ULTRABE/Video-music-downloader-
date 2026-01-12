import os
import re
import asyncio
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters, idle

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO)
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "nageshwar_downloader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workers=1
)

download_queue = asyncio.Queue()
active_users = set()

# ---------------- PRIVATE BLOCK ----------------
@app.on_message(filters.private)
async def block_private(_, msg):
    await msg.reply_text(
        "This bot cannot be used in private.\n"
        "Use it inside a group only."
    )

# ---------------- GROUP LINK HANDLER ----------------
@app.on_message(
    filters.group
    & filters.text
    & filters.regex(r"https?://")
    & ~filters.regex(r"^/")
)
async def handle_link(_, msg):
    uid = msg.from_user.id
    if uid in active_users:
        return

    try:
        await msg.delete()
    except Exception:
        pass

    active_users.add(uid)
    await download_queue.put((msg.chat.id, msg.text.strip(), uid))

# ---------------- DOWNLOAD WORKER ----------------
async def worker():
    while True:
        chat_id, url, uid = await download_queue.get()
        out = "video.mp4"

        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "-f", "best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", out,
                url
            )
            await proc.wait()

            if os.path.exists(out):
                await app.send_video(chat_id, out, supports_streaming=True)
                os.remove(out)

        except Exception as e:
            logging.exception(e)
        finally:
            active_users.discard(uid)
            download_queue.task_done()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
