from aiogram import Router
from aiogram.types import Message
from config import OWNER_ID
from utils.state import set_premium_group

admin_router = Router()

@admin_router.message()
async def admin_commands(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    if message.text.startswith("/chatid"):
        await message.reply(
            f"User ID: {message.from_user.id}\n"
            f"Chat ID: {message.chat.id}"
        )

    if message.text.startswith("/premium"):
        parts = message.text.split()
        if len(parts) != 2:
            await message.reply("Usage: /premium <chat_id>")
            return

        set_premium_group(parts[1])
        await message.reply("Premium mode enabled for this group.")
