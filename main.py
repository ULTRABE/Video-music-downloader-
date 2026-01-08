import os
import re
import json
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= ENV =================
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# ================= BOT =================
app = Client(
    "nageshwar",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
AUTH_FILE = "authorized_chats.json"

download_queue = asyncio.Queue()
active_tasks = {}
task_counter = 0

# ================= AUTH =================
def load_auth():
    if not os.path.exists(AUTH_FILE):
        return []
    with open(AUTH_FILE) as f:
        return json.load(f)

def chat_allowed(chat):
    return chat.type == "private" or chat.id in load_auth()

# ================= COMMANDS =================
@app.on_message(filters.command("start"))
async def start(_, msg):
    if chat_allowed(msg.chat):
        await msg.reply("⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\nSend a YouTube link.")

@app.on_message(filters.command("auth"))
async def auth(_, msg):
    if msg.from_user.id != OWNER_ID:
        return
    try:
        cid = int(msg.text.split()[1])
    except:
        await msg.reply("Usage: /auth <chat_id>")
        return

    data = load_auth()
    if cid not in data:
        data.append(cid)
        with open(AUTH_FILE, "w") as f:
            json.dump(data, f)

    await msg.reply(f"Authorized `{cid}`")

# ================= LINK HANDLER =================
@app.on_message(filters.text & (filters.private | filters.group))
async def link_handler(_, msg):
    if not chat_allowed(msg.chat):
        return
    if not re.match(YT_REGEX, msg.text):
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{msg.text}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"video|{msg.text}")
        ]
    ])
    await msg.reply("Choose format:", reply_markup=kb)

# ================= CALLBACKS =================
@app.on_callback_query()
async def callbacks(_, cq):
    global task_counter

    if not chat_allowed(cq.message.chat):
        return

    data = cq.data.split("|")

    if data[0] == "audio":
        await cq.message.edit(
            "Audio quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("64", callback_data=f"a64|{data[1]}"),
                    InlineKeyboardButton("128", callback_data=f"a128|{data[1]}"),
                    InlineKeyboardButton("320", callback_data=f"a320|{data[1]}")
                ]
            ])
        )
        return

    if data[0] == "video":
        await cq.message.edit(
            "Video quality:",
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
        task_id, owner_id = data[1], int(data[2])
        if cq.from_user.id != owner_id:
            await cq.answer("Not your download", show_alert=True)
            return

        proc = active_tasks.get(task_id)
        if proc:
            proc.kill()
        await cq.message.edit("❌ Download cancelled.")
        return

    # enqueue task
    task_counter += 1
    task_id = str(task_counter)

    await cq.message.edit(
        "Queued…",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=f"cancel|{task_id}|{cq.from_user.id}"
                )
            ]
        ])
    )

    await download_queue.put((task_id, cq, data[0], data[1], cq.from_user.id))

# ================= WORKER =================
async def worker():
    while True:
        task_id, cq, mode, url, owner = await download_queue.get()
        chat_id = cq.message.chat.id

        if mode.startswith("a"):
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
                "-f", f"bestvideo[ext=mp4][height<={res}][{fps}]+bestaudio[ext=m4a]",
                "--merge-output-format", "mp4",
                "-o", output,
                url
            ]

        proc = await asyncio.create_subprocess_exec(*cmd)
        active_tasks[task_id] = proc
        await proc.wait()
        active_tasks.pop(task_id, None)

        if os.path.exists(output):
            if output.endswith(".mp4"):
                await app.send_video(chat_id, output, supports_streaming=True)
            else:
                await app.send_audio(chat_id, output)
            os.remove(output)

        download_queue.task_done()

# ================= MAIN (FIXED) =================
async def main():
    await app.start()
    asyncio.create_task(worker())
    await idle()        # keeps Railway container alive
    await app.stop()

asyncio.run(main())
