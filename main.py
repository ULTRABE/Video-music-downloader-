import os
import re
import asyncio
import logging
from dotenv import load_dotenv

from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

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

# ---------------- REGEX ----------------
URL_REGEX = r"https?://\S+"
YT_SHORTS_REGEX = r"(https?://)?(www\.)?youtube\.com/shorts/"
INSTA_REEL_REGEX = r"(https?://)?(www\.)?instagram\.com/(reel|reels)/"
FB_REEL_REGEX = r"(https?://)?(www\.)?(facebook\.com/reel|fb\.watch)/"

# ---------------- STATE ----------------
download_queue = asyncio.Queue()
active_users = set()
active_processes = {}
task_counter = 0

# tagall per-chat state
TAG_RUNNING = {}

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\n"
        "• Paste link → auto video (GC & PVT)\n"
        "• Private: /options <link>\n"
        "• /tagall → tag members\n"
        "• /endtag → stop tagging"
    )

# ---------------- TAG ALL (FLOOD SAFE) ----------------
@app.on_message(filters.command("tagall") & filters.group)
async def tag_all(client, message):
    chat_id = message.chat.id

    if TAG_RUNNING.get(chat_id):
        return

    TAG_RUNNING[chat_id] = True
    chunk = ""
    MAX_LEN = 840

    try:
        async for member in client.get_chat_members(chat_id):
            if not TAG_RUNNING.get(chat_id):
                break

            user = member.user
            if user.is_bot or not user.first_name:
                continue

            mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>\n'

            if len(chunk) + len(mention) > MAX_LEN:
                try:
                    await message.reply_text(chunk, disable_web_page_preview=True)
                    await asyncio.sleep(2.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value + 2)

                chunk = ""

            chunk += mention

        if chunk and TAG_RUNNING.get(chat_id):
            try:
                await message.reply_text(chunk, disable_web_page_preview=True)
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)

    finally:
        TAG_RUNNING.pop(chat_id, None)


@app.on_message(filters.command("endtag") & filters.group)
async def end_tag(_, message):
    TAG_RUNNING.pop(message.chat.id, None)
    await message.reply_text("Tagging stopped.")

# ---------------- LINK HANDLER ----------------
@app.on_message(filters.private | filters.group)
async def link_handler(_, msg):
    if not msg.text or not re.search(URL_REGEX, msg.text):
        return

    user_id = msg.from_user.id

    if user_id in active_users:
        if msg.chat.type == "private":
            await msg.reply("Already downloading.")
        return

    await start_auto_video(msg, msg.text)

# ---------------- OPTIONS (PRIVATE ONLY) ----------------
@app.on_message(filters.private & filters.command("options"))
async def options(_, msg):
    if len(msg.command) < 2:
        await msg.reply("/options <video_link>")
        return

    url = msg.command[1]

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Audio", callback_data=f"audio|{url}"),
            InlineKeyboardButton("Video", callback_data=f"video|{url}")
        ]
    ])
    await msg.reply("Choose format:", reply_markup=kb)

# ---------------- AUTO VIDEO ----------------
async def start_auto_video(msg, url):
    global task_counter
    user_id = msg.from_user.id

    active_users.add(user_id)
    task_counter += 1
    task_id = str(task_counter)

    status = await msg.reply("Downloading…")
    await download_queue.put(
        (task_id, status, "auto_video", url, user_id)
    )

# ---------------- CALLBACKS ----------------
@app.on_callback_query()
async def callbacks(_, cq):
    global task_counter
    data = cq.data.split("|")
    user_id = cq.from_user.id
    url = data[1]

    if data[0] == "audio":
        await cq.message.edit(
            "Audio quality:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("64", callback_data=f"a64|{url}"),
                    InlineKeyboardButton("128", callback_data=f"a128|{url}"),
                    InlineKeyboardButton("320", callback_data=f"a320|{url}")
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
                    InlineKeyboardButton("720p", callback_data=f"v720|{url}"),
                    InlineKeyboardButton("1080p", callback_data=f"v1080|{url}")
                ]
            ])
        )
        return

    if user_id in active_users:
        await cq.answer("Already downloading", show_alert=True)
        return

    active_users.add(user_id)
    task_counter += 1
    task_id = str(task_counter)

    await cq.message.edit("Queued…")
    await download_queue.put(
        (task_id, cq.message, data[0], url, user_id)
    )

# ---------------- WORKER ----------------
async def worker():
    while True:
        task_id, msg_obj, mode, url, user_id = await download_queue.get()
        chat_id = msg_obj.chat.id

        try:
            is_reel = (
                re.search(YT_SHORTS_REGEX, url)
                or re.search(INSTA_REEL_REGEX, url)
                or re.search(FB_REEL_REGEX, url)
            )

            if mode == "auto_video":
                output = "out.mp4"
                cmd = [
                    "yt-dlp",
                    "-f", "best[ext=mp4][height<=1080][fps<=30]/best",
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
                res = {"v480": "480", "v720": "720", "v1080": "1080"}[mode]
                output = "out.mp4"
                cmd = [
                    "yt-dlp",
                    "-f", f"best[ext=mp4][height<={res}][fps<=30]/best",
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

        finally:
            active_users.discard(user_id)
            download_queue.task_done()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
