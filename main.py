import os
import re
import asyncio
import logging
from dotenv import load_dotenv

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, ChatAdminRequired

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

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "⏤͟͞ 𝗡𝗔𝗚𝗘𝗦𝗛𝗪𝗔𝗥 ㍐\n\n"
        "• Paste link → auto download\n"
        "• /clean → remove deleted accounts\n"
        "• /promote /fullpromote /superpromote\n"
        "• /demote"
    )

# ---------------- CLEAN DELETED (FIXED) ----------------
@app.on_message(filters.command("clean") & filters.group)
async def clean_deleted(client, message):
    chat_id = message.chat.id

    try:
        me = await client.get_chat_member(chat_id, "me")
        if not me.privileges or not me.privileges.can_restrict_members:
            await message.reply_text("Bot needs ban permissions.")
            return
    except ChatAdminRequired:
        await message.reply_text("Make bot admin first.")
        return

    removed = 0

    async for member in client.get_chat_members(chat_id):
        user = member.user

        # STRICT SAFETY: only deleted accounts
        if user and user.is_deleted:
            try:
                await client.ban_chat_member(chat_id, user.id)
                await client.unban_chat_member(chat_id, user.id)
                removed += 1
                await asyncio.sleep(3)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                continue

    await message.reply_text(
        f"Cleanup complete. Removed {removed} deleted accounts."
    )

# ---------------- LINK HANDLER ----------------
@app.on_message(filters.group | filters.private)
async def link_handler(_, msg):
    if not msg.text or not re.search(r"https?://", msg.text):
        return

    user_id = msg.from_user.id
    if user_id in active_users:
        return

    url = msg.text.strip()

    try:
        await msg.delete()
    except Exception:
        pass

    active_users.add(user_id)
    await download_queue.put((msg.chat.id, url, user_id))

# ---------------- WORKER ----------------
async def worker():
    while True:
        chat_id, url, user_id = await download_queue.get()
        output = "out.mp4"

        try:
            cmd = [
                "yt-dlp",
                "-f", "best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", output,
                url
            ]

            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()

            if os.path.exists(output):
                await app.send_video(
                    chat_id,
                    output,
                    supports_streaming=True
                )
                os.remove(output)

        except Exception as e:
            logging.exception(e)

        finally:
            active_users.discard(user_id)
            download_queue.task_done()

# ---------------- ADMIN HELPERS ----------------
def reply_admin():
    return filters.group & filters.reply

# ---------------- PROMOTE ----------------
@app.on_message(filters.command("promote") & reply_admin())
async def promote(client, msg):
    await client.promote_chat_member(
        msg.chat.id,
        msg.reply_to_message.from_user.id,
        can_delete_messages=True,
        can_invite_users=True,
        can_pin_messages=False,
        can_restrict_members=False,
        can_promote_members=False
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
        can_restrict_members=True,
        can_promote_members=False
    )

@app.on_message(filters.command("superpromote") & reply_admin())
async def superpromote(client, msg):
    user_id = msg.reply_to_message.from_user.id
    await client.promote_chat_member(
        msg.chat.id,
        user_id,
        can_change_info=True,
        can_delete_messages=True,
        can_invite_users=True,
        can_pin_messages=True,
        can_restrict_members=True,
        can_promote_members=True
    )
    await client.set_administrator_title(
        msg.chat.id,
        user_id,
        "𝐁𝐎𝐒𝐒"
    )

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

# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
