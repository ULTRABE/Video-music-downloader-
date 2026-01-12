import os
import re
import asyncio
import logging
import time
import random
import json
import subprocess
from dotenv import load_dotenv

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.enums import ChatMembersFilter
from pyrogram.types import (
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

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

# ---------------- STATE ----------------
download_queue = asyncio.Queue()
active_users = set()
TAG_RUNNING = {}

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply_text(
        "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\n"
        "• Send link → auto download\n"
        "• /help → commands\n"
        "• /clean → remove deleted accounts"
    )

# ---------------- CLEAN ----------------
@app.on_message(filters.command("clean") & filters.group)
async def clean_deleted_accounts(client, message):
    chat_id = message.chat.id
    try:
        me = await client.get_chat_member(chat_id, "me")
        if not me.privileges or not me.privileges.can_restrict_members:
            return await message.reply_text("I need ban permission.")
    except ChatAdminRequired:
        return await message.reply_text("Make me admin first.")

    removed = 0
    await message.reply_text("Scanning deleted accounts…")

    async for member in client.get_chat_members(chat_id):
        user = member.user
        if user and user.is_deleted:
            try:
                await client.ban_chat_member(chat_id, user.id)
                await client.unban_chat_member(chat_id, user.id)
                removed += 1
                await asyncio.sleep(2)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass

    await message.reply_text(f"Cleanup done. Removed: {removed}")

# ---------------- LINK HANDLER (FIXED) ----------------
@app.on_message(
    (filters.group | filters.private)
    & filters.text
    & filters.regex(r"https?://")
    & ~filters.regex(r"^/")
)
async def link_handler(_, msg):
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
        out = "out.mp4"
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

# ---------------- HELPERS ----------------
def reply_admin():
    return filters.group & filters.reply

# ---------------- PROMOTIONS ----------------
@app.on_message(filters.command("promote") & reply_admin())
async def promote(client, msg):
    await client.promote_chat_member(
        msg.chat.id,
        msg.reply_to_message.from_user.id,
        can_delete_messages=True,
        can_invite_users=True
    )

@app.on_message(filters.command("fullpromote") & reply_admin())
async def fullpromote(client, msg):
    await client.promote_chat_member(
        msg.chat.id,
        msg.reply_to_message.from_user.id,
        can_change_info=True,
        can_delete_messages=True,
        can_invite_users=True,
        can_pin_messages=True,
        can_restrict_members=True
    )

@app.on_message(filters.command("superpromote") & reply_admin())
async def superpromote(client, msg):
    uid = msg.reply_to_message.from_user.id
    await client.promote_chat_member(
        msg.chat.id,
        uid,
        can_change_info=True,
        can_delete_messages=True,
        can_invite_users=True,
        can_pin_messages=True,
        can_restrict_members=True,
        can_promote_members=True
    )
    await client.set_administrator_title(msg.chat.id, uid, "𝐁𝐎𝐒𝐒")

@app.on_message(filters.command("demote") & reply_admin())
async def demote(client, msg):
    await client.promote_chat_member(
        msg.chat.id,
        msg.reply_to_message.from_user.id,
        can_change_info=False,
        can_delete_messages=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_restrict_members=False,
        can_promote_members=False
    )

# ---------------- TAG ALL ----------------
@app.on_message(filters.command("tagall") & filters.group)
async def tag_all(client, message):
    cid = message.chat.id
    if TAG_RUNNING.get(cid):
        return

    TAG_RUNNING[cid] = True
    chunk = ""
    MAX = 350

    async for m in client.get_chat_members(cid):
        if not TAG_RUNNING.get(cid):
            break
        u = m.user
        if not u or u.is_bot or not u.first_name:
            continue

        mention = f'<a href="tg://user?id={u.id}">{u.first_name}</a>\n'
        if len(chunk) + len(mention) > MAX:
            await message.reply_text(chunk, parse_mode="html")
            await asyncio.sleep(2)
            chunk = ""
        chunk += mention

    if chunk and TAG_RUNNING.get(cid):
        await message.reply_text(chunk, parse_mode="html")

    TAG_RUNNING.pop(cid, None)

@app.on_message(filters.command("endtag") & filters.group)
async def end_tag(_, msg):
    TAG_RUNNING.pop(msg.chat.id, None)
    await msg.reply_text("Tagging stopped.")

# ---------------- INLINE HELP ----------------
HELP_TEXT = {
    "main": "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\nSelect a category below.",
    "moderation": "/clean\n/purge\n/del\n/lock\n/unlock\n/slowmode",
    "admin": "/promote\n/fullpromote\n/superpromote\n/demote\n/admins",
    "utils": "/tagall\n/endtag\n/stats\n/id\n/ping\n/mentionme",
    "fun": "/roll\n/flip\n/8ball"
}

def help_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡 Moderation", callback_data="help_moderation"),
         InlineKeyboardButton("👮 Admin", callback_data="help_admin")],
        [InlineKeyboardButton("🧰 Utilities", callback_data="help_utils"),
         InlineKeyboardButton("🎲 Fun", callback_data="help_fun")],
        [InlineKeyboardButton("⬅ Back", callback_data="help_main")]
    ])

@app.on_message(filters.command("help") & filters.group)
async def help_cmd(_, msg):
    await msg.reply_text(HELP_TEXT["main"], reply_markup=help_kb())

@app.on_callback_query(filters.regex("^help_"))
async def help_cb(_, q):
    key = q.data.replace("help_", "")
    await q.message.edit_text(HELP_TEXT.get(key, HELP_TEXT["main"]), reply_markup=help_kb())
    await q.answer()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
