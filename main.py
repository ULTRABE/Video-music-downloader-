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
        "• Send link → auto download\n"
        "• /clean → remove deleted accounts\n"
        "• /promote /fullpromote /superpromote\n"
        "• /demote"
    )

# ---------------- CLEAN (ORIGINAL LOGIC) ----------------
@app.on_message(filters.command("clean") & filters.group)
async def clean_deleted_accounts(client, message):
    chat_id = message.chat.id

    try:
        bot_member = await client.get_chat_member(chat_id, "me")
        if not bot_member.privileges or not bot_member.privileges.can_restrict_members:
            await message.reply_text("Bot needs ban permission.")
            return
    except ChatAdminRequired:
        await message.reply_text("Make the bot admin first.")
        return

    removed = 0
    await message.reply_text("Scanning for deleted accounts…")

    async for member in client.get_chat_members(chat_id):
        user = member.user

        # 🔒 SAFETY: ONLY deleted accounts
        if user and user.is_deleted:
            try:
                await client.send_message(
                    chat_id,
                    "User deleted their account — removed."
                )

                await client.ban_chat_member(chat_id, user.id)
                await client.unban_chat_member(chat_id, user.id)

                removed += 1
                await asyncio.sleep(3)

            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                continue

    await message.reply_text(
        f"Cleanup done. Deleted accounts removed: {removed}"
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

# ---------------- DOWNLOAD WORKER ----------------
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
# ---------------- TAG ALL ----------------
TAG_RUNNING = {}

@app.on_message(filters.command("tagall") & filters.group)
async def tag_all(client, message):
    chat_id = message.chat.id

    if TAG_RUNNING.get(chat_id):
        return

    TAG_RUNNING[chat_id] = True
    text_chunk = ""
    MAX_LEN = 350  # safe size

    try:
        async for member in client.get_chat_members(chat_id):
            if not TAG_RUNNING.get(chat_id):
                break

            user = member.user
            if not user or user.is_bot or not user.first_name:
                continue

            mention = f'<a href="tg://user?id={user.id}">{user.first_name}</a>\n'

            if len(text_chunk) + len(mention) > MAX_LEN:
                await message.reply_text(text_chunk, disable_web_page_preview=True)
                await asyncio.sleep(2)
                text_chunk = ""

            text_chunk += mention

        if text_chunk and TAG_RUNNING.get(chat_id):
            await message.reply_text(text_chunk, disable_web_page_preview=True)

    finally:
        TAG_RUNNING.pop(chat_id, None)


@app.on_message(filters.command("endtag") & filters.group)
async def end_tag(_, message):
    TAG_RUNNING.pop(message.chat.id, None)
    await message.reply_text("Tagging stopped.")

@app.on_message(filters.command("purge") & filters.group & filters.reply)
async def purge_messages(client, message):
    chat_id = message.chat.id
    from_id = message.reply_to_message.id
    to_id = message.id

    try:
        for msg_id in range(from_id, to_id):
            try:
                await client.delete_messages(chat_id, msg_id)
            except Exception:
                pass
        await message.delete()
    except Exception:
        pass



@app.on_message(filters.command("del") & filters.group & filters.reply)
async def delete_message(_, message):
    try:
        await message.reply_to_message.delete()
        await message.delete()
    except Exception:
        pass


from pyrogram.types import ChatPermissions

@app.on_message(filters.command("lock") & filters.group)
async def lock_chat(client, message):
    await client.set_chat_permissions(
        message.chat.id,
        ChatPermissions()
    )
    await message.reply_text("Chat locked.")




@app.on_message(filters.command("unlock") & filters.group)
async def unlock_chat(client, message):
    await client.set_chat_permissions(
        message.chat.id,
        ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    await message.reply_text("Chat unlocked.")







@app.on_message(filters.command("slowmode") & filters.group)
async def slowmode(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /slowmode <seconds|off>")
        return

    arg = message.command[1]
    seconds = 0 if arg == "off" else int(arg)

    await client.set_slow_mode_delay(
        message.chat.id,
        seconds
    )
    await message.reply_text(f"Slow mode set to {seconds}s")









@app.on_message(filters.command("id"))
async def get_ids(_, message):
    text = f"Chat ID: `{message.chat.id}`\nYour ID: `{message.from_user.id}`"
    if message.reply_to_message:
        text += f"\nReplied User ID: `{message.reply_to_message.from_user.id}`"
    await message.reply_text(text)




@app.on_message(filters.command("admins") & filters.group)
async def list_admins(client, message):
    admins = []
    async for member in client.get_chat_members(message.chat.id, filter="administrators"):
        admins.append(member.user.first_name)

    await message.reply_text("Admins:\n" + "\n".join(admins))




import time

@app.on_message(filters.command("ping"))
async def ping(_, message):
    start = time.time()
    m = await message.reply_text("Pinging...")
    end = time.time()
    await m.edit_text(f"Pong! `{int((end-start)*1000)}ms`")







@app.on_message(filters.command("stats") & filters.group)
async def stats(client, message):
    members = await client.get_chat_members_count(message.chat.id)
    deleted = 0

    async for m in client.get_chat_members(message.chat.id):
        if m.user and m.user.is_deleted:
            deleted += 1

    await message.reply_text(
        f"Members: {members}\nDeleted accounts: {deleted}"
    )





@app.on_message(filters.command("mentionme"))
async def mention_me(_, message):
    user = message.from_user
    await message.reply_text(f'<a href="tg://user?id={user.id}">{user.first_name}</a>', parse_mode="html")





import random

@app.on_message(filters.command("roll"))
async def roll(_, message):
    args = message.command
    if len(args) == 3:
        low, high = int(args[1]), int(args[2])
    else:
        low, high = 1, 100
    await message.reply_text(f"🎲 {random.randint(low, high)}")


import json
import subprocess

@app.on_message(filters.command("info"))
async def video_info(_, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /info <link>")
        return

    url = message.command[1]
    result = subprocess.run(
        ["yt-dlp", "--dump-json", url],
        capture_output=True, text=True
    )

    data = json.loads(result.stdout)
    await message.reply_text(
        f"Title: {data.get('title')}\n"
        f"Duration: {data.get('duration')}s\n"
        f"Uploader: {data.get('uploader')}"
    )

@app.on_message(filters.command("flip"))
async def flip(_, message):
    await message.reply_text("Heads" if random.choice([True, False]) else "Tails")

answers = [
    "Yes", "No", "Maybe", "Definitely", "Ask again later"
]

@app.on_message(filters.command("8ball"))
async def eight_ball(_, message):
    await message.reply_text(random.choice(answers))

# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.start()
    app.loop.create_task(worker())
    idle()
    app.stop()
