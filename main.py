import os
import re
import json
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

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
task_id_counter = 0

# ---------------- AUTH ----------------
def load_auth():
    if not os.path.exists(AUTH_FILE):
        return []
    with open(AUTH_FILE) as f:
        return json.load(f)

def chat_allowed(chat):
    return chat.type == "private" or chat.id in load_auth()

# ---------------- COMMANDS ----------------
@app.on_message(filters.command("start"))
async def start(_, m):
    if chat_allowed(m.chat):
        await m.reply("⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\nSend a YouTube link.")

@app.on_message(filters.command("auth"))
async def auth(_, m):
    if m.from_user.id != OWNER_ID:
        return
    try:
        cid = int(m.text.split()[1])
    except:
        await m.reply("Usage: /auth <chat_id>")
        return

    data = load_auth()
    if cid not in data:
        data.append(cid)
        with open(AUTH_FILE, "w") as f:
            json.dump(data, f)

    await m.reply(f"Authorized `{cid}`")

# ---------------- LINK ----------------
@app.on_message(filters.text & (filters.private | filters.group))
async def link(_, m):
    if not chat_allowed(m.chat):
        return
    if not re.match(YT_REGEX, m.text):
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{m.text}"),
         InlineKeyboardButton("🎬 Video", callback_data=f"video|{m.text}")]
    ])
    await m.reply("Choose:", reply_markup=kb)

# ---------------- CALLBACK ----------------
@app.on_callback_query()
async def cb(_, cq):
    global task_id_counter
    if not chat_allowed(cq.message.chat):
        return

    d = cq.data.split("|")

    if d[0] == "audio":
        await cq.message.edit(
            "Audio quality:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("64", callback_data=f"a64|{d[1]}"),
                 InlineKeyboardButton("128", callback_data=f"a128|{d[1]}"),
                 InlineKeyboardButton("320", callback_data=f"a320|{d[1]}")]
            ])
        )
        return

    if d[0] == "video":
        await cq.message.edit(
            "Video quality:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("320p", callback_data=f"v320|{d[1]}"),
                 InlineKeyboardButton("480p", callback_data=f"v480|{d[1]}")],
                [InlineKeyboardButton("720p", callback_data=f"v720|{d[1]}"),
                 InlineKeyboardButton("1080p", callback_data=f"v1080|{d[1]}")]
            ])
        )
        return

    if d[0] == "cancel":
        tid, owner = d[1], int(d[2])
        if cq.from_user.id != owner:
            await cq.answer("Not yours", show_alert=True)
            return
        p = active_tasks.get(tid)
        if p:
            p.kill()
        await cq.message.edit("❌ Cancelled")
        return

    task_id_counter += 1
    tid = str(task_id_counter)

    await cq.message.edit(
        "Queued…",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{tid}|{cq.from_user.id}")]
        ])
    )

    await download_queue.put((tid, cq, d[0], d[1], cq.from_user.id))

# ---------------- WORKER ----------------
async def worker():
    while True:
        tid, cq, mode, url, owner = await download_queue.get()
        chat = cq.message.chat.id

        if mode.startswith("a"):
            cmd = [
                "yt-dlp", "-x",
                "--audio-format", "mp3",
                "--audio-quality", mode[1:],
                "-o", "out.mp3", url
            ]
            out = "out.mp3"
        else:
            res = {"v320":"320","v480":"480","v720":"720","v1080":"1080"}[mode]
            fps = "fps<=30" if res != "1080" else "fps>30"
            cmd = [
                "yt-dlp",
                "-f", f"bestvideo[ext=mp4][height<={res}][{fps}]+bestaudio[ext=m4a]",
                "--merge-output-format", "mp4",
                "-o", "out.mp4", url
            ]
            out = "out.mp4"

        p = await asyncio.create_subprocess_exec(*cmd)
        active_tasks[tid] = p
        await p.wait()
        active_tasks.pop(tid, None)

        if os.path.exists(out):
            if out.endswith(".mp4"):
                await app.send_video(chat, out, supports_streaming=True)
            else:
                await app.send_audio(chat, out)
            os.remove(out)

        download_queue.task_done()

# ---------------- START SAFE ----------------
@app.on_startup()
async def startup():
    asyncio.create_task(worker())

app.run()
