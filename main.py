import os
import re
import asyncio
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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

YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/\S+"

download_queue = asyncio.Queue()
active_processes = {}
active_users = set()
task_counter = 0


# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\n"
        "• Private: audio or video options\n"
        "• Group: paste link → auto fast video"
    )


# ---------------- LINK HANDLER (FIXED PROPERLY) ----------------
@app.on_message(filters.private | filters.group)
async def link_handler(_, msg):
    # Collect text from all possible places
    content = msg.text or msg.caption or ""

    # If still empty, try entities (group preview case)
    if not content and msg.entities:
        for ent in msg.entities:
            if ent.type in ("url", "text_link"):
                content = ent.url or msg.text or ""
                break

    if not content:
        return

    if not re.search(YT_REGEX, content):
        return

    user_id = msg.from_user.id

    if user_id in active_users:
        await msg.reply("⚠️ You already have an active download.")
        return

    # -------- GROUP AUTO VIDEO --------
    if msg.chat.type in ("group", "supergroup"):
        active_users.add(user_id)
        global task_counter
        task_counter += 1
        task_id = str(task_counter)

        status = await msg.reply("⬇️ Downloading best quality video…")
        await download_queue.put(
            (task_id, status, "auto_video", content, user_id)
        )
        return

    # -------- PRIVATE OPTIONS --------
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{content}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"video|{content}")
        ]
    ])
    await msg.reply("Choose format:", reply_markup=kb)


# ---------------- CALLBACKS ----------------
@app.on_callback_query()
async def callbacks(_, cq):
    global task_counter
    data = cq.data.split("|")
    user_id = cq.from_user.id

    if data[0] == "audio":
        await cq.message.edit(
            "Select audio quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("64 kbps", callback_data=f"a64|{data[1]}"),
                    InlineKeyboardButton("128 kbps", callback_data=f"a128|{data[1]}"),
                    InlineKeyboardButton("320 kbps", callback_data=f"a320|{data[1]}")
                ]
            ])
        )
        return

    if data[0] == "video":
        await cq.message.edit(
            "Select video quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("320p", callback_data=f"v320|{data[1]}"),
                    InlineKeyboardButton("480p", callback_data=f"v480|{data[1]}")
                ],
                [
                    InlineKeyboardButton("720p", callback_data=f"v720|{data[1]}"),
                    InlineKeyboardButton("1080p", callback_data=f"v1080|{data[1]}")
                ]
            ])
        )
        return

    if data[0] == "cancel":
        task_id, owner = data[1], int(data[2])
        if user_id != owner:
            await cq.answer("Not your download", show_alert=True)
            return

        proc = active_processes.get(task_id)
        if proc:
            proc.kill()
            active_processes.pop(task_id, None)

        active_users.discard(owner)
        await cq.message.edit("❌ Download cancelled.")
        return

    if user_id in active_users:
        await cq.answer("You already have an active download.", show_alert=True)
        return

    active_users.add(user_id)
    task_counter += 1
    task_id = str(task_counter)

    await cq.message.edit(
        "Queued…",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=f"cancel|{task_id}|{user_id}"
                )
            ]
        ])
    )

    await download_queue.put((task_id, cq.message, data[0], data[1], user_id))


# ---------------- WORKER (FAST) ----------------
async def worker():
    while True:
        task_id, msg_obj, mode, url, user_id = await download_queue.get()
        chat_id = msg_obj.chat.id

        try:
            if mode == "auto_video":
                output = "out.mp4"
                cmd = [
                    "yt-dlp",
                    "-f", "best[ext=mp4][fps<=30]/best[ext=mp4]/best",
                    "--concurrent-fragments", "4",
                    "--no-part",
                    "--no-post-overwrites",
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

            else:
                res = {"v320":"320","v480":"480","v720":"720","v1080":"1080"}[mode]
                fps = "fps<=30" if res != "1080" else "fps>30"
                output = "out.mp4"
                cmd = [
                    "yt-dlp",
                    "-f",
                    f"best[ext=mp4][height<={res}][{fps}]/best[ext=mp4]/best",
                    "--concurrent-fragments", "4",
                    "--no-part",
                    "--no-post-overwrites",
                    "--merge-output-format", "mp4",
                    "-o", output,
                    url
                ]

            proc = await asyncio.create_subprocess_exec(*cmd)
            active_processes[task_id] = proc
            await proc.wait()
            active_processes.pop(task_id, None)

            if os.path.exists(output):
                await app.send_video(chat_id, output, supports_streaming=True)
                os.remove(output)

        except Exception:
            logging.exception("Download failed")

        active_users.discard(user_id)
        download_queue.task_done()


# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
