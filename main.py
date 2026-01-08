import os
import re
import subprocess
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "nageshwar",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

YT_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"

@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\nSend a YouTube link."
    )

@app.on_message(filters.text & filters.private)
async def handle_link(_, msg):
    if not re.match(YT_REGEX, msg.text):
        return

    buttons = [
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"audio|{msg.text}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"video|{msg.text}")
        ]
    ]

    await msg.reply(
        "Choose format:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query()
async def callbacks(_, cq):
    data = cq.data.split("|")
    mode = data[0]
    url = data[1]

    if mode == "audio":
        buttons = [
            [
                InlineKeyboardButton("64 kbps", callback_data=f"a64|{url}"),
                InlineKeyboardButton("128 kbps", callback_data=f"a128|{url}"),
                InlineKeyboardButton("320 kbps", callback_data=f"a320|{url}")
            ]
        ]
        await cq.message.edit("Select audio quality:", reply_markup=InlineKeyboardMarkup(buttons))

    elif mode == "video":
        buttons = [
            [
                InlineKeyboardButton("320p", callback_data=f"v320|{url}"),
                InlineKeyboardButton("480p", callback_data=f"v480|{url}")
            ],
            [
                InlineKeyboardButton("720p", callback_data=f"v720|{url}"),
                InlineKeyboardButton("1080p (60fps)", callback_data=f"v1080|{url}")
            ],
            [
                InlineKeyboardButton("4K (60fps)", callback_data=f"v4k|{url}")
            ]
        ]
        await cq.message.edit("Select video quality:", reply_markup=InlineKeyboardMarkup(buttons))

    else:
        await cq.message.edit("Downloading…")
        await download_and_send(cq, mode, url)

async def download_and_send(cq, mode, url):
    chat_id = cq.message.chat.id
    out = "output.%(ext)s"

    if mode.startswith("a"):
        bitrate = mode.replace("a", "")
        cmd = [
            "yt-dlp", "-x",
            "--audio-format", "mp3",
            "--audio-quality", bitrate,
            "-o", out,
            url
        ]
    else:
        if mode == "v1080" or mode == "v4k":
            format_sel = "bv*[fps>30]+ba/b"
        else:
            format_sel = "bv*[fps<=30]+ba/b"

        res = {
            "v320": "320",
            "v480": "480",
            "v720": "720",
            "v1080": "1080",
            "v4k": "2160"
        }[mode]

        cmd = [
            "yt-dlp",
            "-f", f"{format_sel}[height<={res}]",
            "-o", out,
            url
        ]

    subprocess.run(cmd)

    file = next((f for f in os.listdir() if f.startswith("output")), None)
    if file:
        await app.send_document(chat_id, file)
        os.remove(file)

    await cq.message.delete()

app.run()
