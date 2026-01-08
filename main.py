import os
import re
import json
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
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
active_tasks = {}  # task_id -> process
task_counter = 0

# ================= AUTH =================
def load_auth():
    if not os.path.exists(AUTH_FILE):
        return []
    with open(AUTH_FILE, "r") as f:
        return json.load(f)

def save_auth(data):
    with open(AUTH_FILE, "w") as f:
        json.dump(data, f)

def chat_allowed(chat):
    if chat.type == "private":
        return True
    return chat.id in load_auth()

# ================= START =================
@app.on_message(filters.command("start"))
async def start(_, msg):
    if not chat_allowed(msg.chat):
        return
    await msg.reply(
        "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\nSend a YouTube link."
    )

# ================= AUTH CMD =================
@app.on_message(filters.command("auth"))
async def auth(_, msg):
    if msg.from_user.id != OWNER_ID:
        return
    try:
        chat_id = int(msg.text.split()[1])
    except:
        await msg.reply("Usage: /auth <chat_id>")
        return

    data = load_auth()
    if chat_id not in data:
        data.append(chat_id)
        save_auth(data)

    await msg.reply(f"Authorized: `{chat_id}`")

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
    if not chat_allowed(cq.message.chat):
        return

    data = cq.data.split("|")

    if data[0] == "audio":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("64 kbps", callback_data=f"a64|{data[1]}"),
                InlineKeyboardButton("128 kbps", callback_data=f"a128|{data[1]}"),
                InlineKeyboardButton("320 kbps", callback_data=f"a320|{data[1]}")
            ]
        ])
        await cq.message.edit("Select audio quality:", reply_markup=kb)
        return

    if data[0] == "video":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("320p", callback_data=f"v320|{data[1]}"),
                InlineKeyboardButton("480p", callback_data=f"v480|{data[1]}")
            ],
            [
                InlineKeyboardButton("720p", callback_data=f"v720|{data[1]}"),
                InlineKeyboardButton("1080p (60fps)", callback_data=f"v1080|{data[1]}")
            ]
        ])
        await cq.message.edit("Select video quality:", reply_markup=kb)
        return

    if data[0] == "cancel":
        task_id = data[1]
        owner_id = int(data[2])

        if cq.from_user.id != owner_id:
            await cq.answer("Not your download.", show_alert=True)
            return

        process = active_tasks.get(task_id)
        if process:
            process.kill()
            active_tasks.pop(task_id, None)
            await cq.message.edit("❌ Download cancelled.")
        return

    # enqueue
    global task_counter
    task_counter += 1
    task_id = str(task_counter)

    cancel_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{task_id}|{cq.from_user.id}")]
    ])

    await cq.message.edit("Queued…", reply_markup=cancel_kb)
    await download_queue.put((task_id, cq, data[0], data[1], cq.from_user.id))

# ================= AUTO DELETE =================
async def auto_delete(chat_id, msg_id):
    await asyncio.sleep(300)
    try:
        await app.delete_messages(chat_id, msg_id)
    except:
        pass

# ================= YT-DLP RUNNER =================
async def run_yt_dlp(cmd, progress_msg, task_id):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    active_tasks[task_id] = process
    last = 0

    async for line in process.stdout:
        text = line.decode(errors="ignore")
        if "%" in text:
            now = asyncio.get_event_loop().time()
            if now - last > 1.2:
                try:
                    await progress_msg.edit(f"⏳ {text.strip()[:120]}")
                except:
                    pass
                last = now

    await process.wait()
    active_tasks.pop(task_id, None)

# ================= WORKER =================
async def worker():
    while True:
        task_id, cq, mode, url, owner_id = await download_queue.get()
        chat_id = cq.message.chat.id
        progress = cq.message

        if mode.startswith("a"):
            output = "output.mp3"
            cmd = [
                "yt-dlp",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", mode.replace("a", ""),
                "-o", output,
                url
            ]
        else:
            res = {"v320":"320","v480":"480","v720":"720","v1080":"1080"}[mode]
            fps = "fps<=30" if res != "1080" else "fps>30"

            output = "output.mp4"
            cmd = [
                "yt-dlp",
                "-f",
                f"bestvideo[ext=mp4][height<={res}][{fps}]+bestaudio[ext=m4a]",
                "--merge-output-format", "mp4",
                "-o", output,
                url
            ]

        await run_yt_dlp(cmd, progress, task_id)

        if os.path.exists(output):
            if output.endswith(".mp4"):
                sent = await app.send_video(chat_id, output, supports_streaming=True)
            else:
                sent = await app.send_audio(chat_id, output)

            os.remove(output)
            asyncio.create_task(auto_delete(chat_id, sent.id))

        try:
            await progress.delete()
        except:
            pass

        download_queue.task_done()

# ================= START =================
asyncio.get_event_loop().create_task(worker())
app.run()
