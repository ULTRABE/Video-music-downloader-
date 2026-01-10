import os
import re
import asyncio
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO)

# ---------------- ENV ----------------
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---------------- BOT ----------------
app = Client(
    "nageshwar",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workers=1
)

YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
SHORTS_REGEX = r"(https?://)?(www\.)?youtube\.com/shorts/"

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
        "• Group: paste link → auto video download"
    )

# ---------------- LINK HANDLER ----------------
@app.on_message(filters.private | filters.group)
async def link_handler(_, msg):
    if not msg.text:
        return
    if not re.match(YT_REGEX, msg.text):
        return

    user_id = msg.from_user.id

    if user_id in active_users:
        await msg.reply("⚠️ You already have an active download. Please wait.")
        return

    # -------- GROUP CHAT --------
    if msg.chat.type in ("group", "supergroup"):
        await start_auto_video(msg, msg.text)
        return

    # -------- PRIVATE CHAT (UNCHANGED LOGIC) --------
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{msg.text}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"video|{msg.text}")
        ]
    ])
    await msg.reply("Choose format:", reply_markup=kb)

# ---------------- GROUP AUTO VIDEO ----------------
async def start_auto_video(msg, url):
    global task_counter
    user_id = msg.from_user.id

    active_users.add(user_id)
    task_counter += 1
    task_id = str(task_counter)

    status = await msg.reply("⬇️ Downloading best quality video…")

    await download_queue.put(
        (task_id, status, "auto_video", url, user_id)
    )

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

    # -------- START PRIVATE DOWNLOAD --------
    if user_id in active_users:
        await cq.answer("You already have an active download.", show_alert=True)
        return

    active_users.add(user_id)
    task_counter += 1
    task_id = str(task_counter)

    await cq.message.edit("Queued…")
    await download_queue.put(
        (task_id, cq.message, data[0], data[1], user_id)
    )

# ---------------- WORKER ----------------
async def worker():
    while True:
        task_id, msg_obj, mode, url, user_id = await download_queue.get()
        chat_id = msg_obj.chat.id

        try:
            is_shorts = re.search(SHORTS_REGEX, url)

            # -------- GROUP AUTO VIDEO --------
            if mode == "auto_video":
                output = "out.mp4"

                if is_shorts:
                    cmd = [
                        "yt-dlp",
                        "-f", "best[ext=mp4][height<=1080][fps<=30]/best",
                        "--merge-output-format", "mp4",
                        "-o", output,
                        url
                    ]
                else:
                    cmd = [
                        "yt-dlp",
                        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
                        "--merge-output-format", "mp4",
                        "-o", output,
                        url
                    ]

            # -------- AUDIO --------
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

            # -------- PRIVATE VIDEO --------
            else:
                res = {"v320":"320","v480":"480","v720":"720","v1080":"1080"}[mode]
                fps = "fps<=30" if res != "1080" else "fps>30"
                output = "out.mp4"

                if is_shorts:
                    cmd = [
                        "yt-dlp",
                        "-f", f"best[ext=mp4][height<={res}][fps<=30]/best",
                        "--merge-output-format", "mp4",
                        "-o", output,
                        url
                    ]
                else:
                    cmd = [
                        "yt-dlp",
                        "-f", f"bestvideo[ext=mp4][height<={res}][{fps}]+bestaudio[ext=m4a]",
                        "--merge-output-format", "mp4",
                        "-o", output,
                        url
                    ]

            proc = await asyncio.create_subprocess_exec(*cmd)
            active_processes[task_id] = proc
            await proc.wait()
            active_processes.pop(task_id, None)

            if os.path.exists(output):
                if output.endswith(".mp4"):
                    await app.send_video(chat_id, output, supports_streaming=True)
                else:
                    await app.send_audio(chat_id, output)
                os.remove(output)

        except Exception as e:
            logging.exception(e)

        active_users.discard(user_id)
        download_queue.task_done()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
