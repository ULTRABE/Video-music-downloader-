from aiogram import Router
from aiogram.types import Message
from config import OWNER_ID
from utils.state import set_premium

admin_router = Router()

@admin_router.message()
async def admin_commands(message: Message):
    # Owner-only
    if message.from_user.id != OWNER_ID:
        return

    text = message.text.strip()

    # ── /chatid ─────────────────────────────
    if text == "/chatid":
        await message.reply(
            f"User ID: {message.from_user.id}\n"
            f"Chat ID: {message.chat.id}"
        )
        return

    # ── /premium <chat_id> ──────────────────
    if text.startswith("/premium"):
        parts = text.split()

        if len(parts) != 2:
            await message.reply("Usage: /premium <chat_id>")
            return

        chat_id = parts[1]

        set_premium(chat_id)
        await message.reply(
            "Premium mode enabled.\n"
            "This group is now adult-only."
        )
