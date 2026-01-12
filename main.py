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

# ---------------- STARTUP ----------------
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
    try:
        me = await client.get_chat_member(message.chat.id, "me")
        if not me.privileges or not me.privileges.can_restrict_members:
            return await message.reply_text("I need ban permission.")
    except ChatAdminRequired:
        return await message.reply_text("Make me admin first.")

    removed = 0
    await message.reply_text("Scanning deleted accounts…")

    async for member in client.get_chat_members(message.chat.id):
        user = member.user
        if user and user.is_deleted:
            try:
                await client.ban_chat_member(message.chat.id, user.id)
                await client.unban_chat_member(message.chat.id, user.id)
                removed += 1
                await asyncio.sleep(2)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass

    await message.reply_text(f"Cleanup done. Removed: {removed}")

# ---------------- ADMIN HELPERS ----------------
def require_reply(msg):
    if not msg.reply_to_message:
        raise ValueError("Reply required")

# ---------------- PROMOTIONS ----------------
@app.on_message(filters.command("promote") & filters.group)
async def promote(client, msg):
    try:
        require_reply(msg)
        await client.promote_chat_member(
            msg.chat.id,
            msg.reply_to_message.from_user.id,
            can_delete_messages=True,
            can_invite_users=True
        )
    except Exception:
        await msg.reply_text("Reply to a user.")

@app.on_message(filters.command("fullpromote") & filters.group)
async def fullpromote(client, msg):
    try:
        require_reply(msg)
        await client.promote_chat_member(
            msg.chat.id,
            msg.reply_to_message.from_user.id,
            can_change_info=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_restrict_members=True
        )
    except Exception:
        await msg.reply_text("Reply to a user.")

@app.on_message(filters.command("superpromote") & filters.group)
async def superpromote(client, msg):
    try:
        require_reply(msg)
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
    except Exception:
        await msg.reply_text("Reply to a user.")

@app.on_message(filters.command("demote") & filters.group)
async def demote(client, msg):
    try:
        require_reply(msg)
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
    except Exception:
        await msg.reply_text("Reply to a user.")

# ---------------- TAG ALL ----------------
@app.on_message(filters.command("tagall") & filters.group)
async def tag_all(client, message):
    if TAG_RUNNING.get(message.chat.id):
        return

    TAG_RUNNING[message.chat.id] = True
    text = ""

    async for m in client.get_chat_members(message.chat.id):
        if not TAG_RUNNING.get(message.chat.id):
            break
        u = m.user
        if not u or u.is_bot or not u.first_name:
            continue

        mention = f'<a href="tg://user?id={u.id}">{u.first_name}</a>\n'
        if len(text) + len(mention) > 350:
            await message.reply_text(text, parse_mode="html")
            text = ""
            await asyncio.sleep(2)
        text += mention

    if text:
        await message.reply_text(text, parse_mode="html")

    TAG_RUNNING.pop(message.chat.id, None)

@app.on_message(filters.command("endtag") & filters.group)
async def end_tag(_, msg):
    TAG_RUNNING.pop(msg.chat.id, None)
    await msg.reply_text("Tagging stopped.")

# ---------------- PURGE / DELETE ----------------
@app.on_message(filters.command("purge") & filters.group & filters.reply)
async def purge(client, msg):
    for i in range(msg.reply_to_message.id, msg.id):
        try:
            await client.delete_messages(msg.chat.id, i)
        except Exception:
            pass
    await msg.delete()

@app.on_message(filters.command("del") & filters.group & filters.reply)
async def delete(_, msg):
    await msg.reply_to_message.delete()
    await msg.delete()

# ---------------- LOCK / UNLOCK ----------------
@app.on_message(filters.command("lock") & filters.group)
async def lock(client, msg):
    await client.set_chat_permissions(msg.chat.id, ChatPermissions())
    await msg.reply_text("Chat locked.")

@app.on_message(filters.command("unlock") & filters.group)
async def unlock(client, msg):
    await client.set_chat_permissions(
        msg.chat.id,
        ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    await msg.reply_text("Chat unlocked.")

# ---------------- SLOWMODE ----------------
@app.on_message(filters.command("slowmode") & filters.group)
async def slowmode(client, msg):
    if len(msg.command) < 2:
        return await msg.reply_text("Usage: /slowmode <sec|off>")
    arg = msg.command[1].lower()
    seconds = 0 if arg == "off" else int(arg) if arg.isdigit() else None
    if seconds is None:
        return await msg.reply_text("Invalid value.")
    await client.set_slow_mode_delay(msg.chat.id, seconds)
    await msg.reply_text(f"Slow mode set to {seconds}s")

# ---------------- INFO (NON-BLOCKING) ----------------
@app.on_message(filters.command("info"))
async def info(_, msg):
    if len(msg.command) < 2:
        return await msg.reply_text("Usage: /info <link>")

    def run():
        return subprocess.run(
            ["yt-dlp", "--dump-json", msg.command[1]],
            capture_output=True, text=True
        )

    result = await asyncio.to_thread(run)
    data = json.loads(result.stdout)
    await msg.reply_text(
        f"Title: {data.get('title')}\n"
        f"Duration: {data.get('duration')}s\n"
        f"Uploader: {data.get('uploader')}"
    )

# ---------------- STATS ----------------
@app.on_message(filters.command("stats") & filters.group)
async def stats(client, msg):
    total = await client.get_chat_members_count(msg.chat.id)
    deleted = 0
    async for m in client.get_chat_members(msg.chat.id):
        if m.user and m.user.is_deleted:
            deleted += 1
    await msg.reply_text(f"Members: {total}\nDeleted: {deleted}")

# ---------------- ADMINS ----------------
@app.on_message(filters.command("admins") & filters.group)
async def admins(client, msg):
    names = []
    async for m in client.get_chat_members(msg.chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
        if m.user:
            names.append(m.user.first_name or "Deleted")
    await msg.reply_text("Admins:\n" + "\n".join(names))

# ---------------- MISC ----------------
@app.on_message(filters.command("ping"))
async def ping(_, msg):
    t = time.time()
    m = await msg.reply_text("Pinging…")
    await m.edit_text(f"Pong `{int((time.time()-t)*1000)}ms`")

@app.on_message(filters.command("id"))
async def ids(_, msg):
    txt = f"Chat ID: `{msg.chat.id}`\nYour ID: `{msg.from_user.id}`"
    if msg.reply_to_message:
        txt += f"\nUser ID: `{msg.reply_to_message.from_user.id}`"
    await msg.reply_text(txt)

@app.on_message(filters.command("mentionme"))
async def mentionme(_, msg):
    u = msg.from_user
    await msg.reply_text(f'<a href="tg://user?id={u.id}">{u.first_name}</a>', parse_mode="html")

@app.on_message(filters.command("flip"))
async def flip(_, msg):
    await msg.reply_text(random.choice(["Heads", "Tails"]))

@app.on_message(filters.command("roll"))
async def roll(_, msg):
    low, high = (1, 100)
    if len(msg.command) == 3:
        low, high = map(int, msg.command[1:])
    await msg.reply_text(str(random.randint(low, high)))

@app.on_message(filters.command("8ball"))
async def eightball(_, msg):
    await msg.reply_text(random.choice(
        ["Yes", "No", "Maybe", "Definitely", "Ask again later"]
    ))

# ---------------- INLINE HELP ----------------
HELP_TEXT = {
    "main": "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\nSelect a category",
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
    try:
        key = q.data.replace("help_", "")
        await q.message.edit_text(HELP_TEXT.get(key, HELP_TEXT["main"]), reply_markup=help_kb())
    except Exception:
        pass
    await q.answer()

# ---------------- DOWNLOAD HANDLER (LAST) ----------------
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
        try:
            chat_id, url, uid = await download_queue.get()
            out = "out.mp4"
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
    print("BOT STARTING")
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
