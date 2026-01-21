from aiogram import Router
from aiogram.types import Message
from config import OWNER_ID
from utils.state import set_premium

admin_router = Router()

@admin_router.message(lambda m: m.from_user.id == OWNER_ID)
async def admin(msg: Message):
    if msg.text == "/chatid":
        await msg.reply(f"📱 Chat ID: <code>{msg.chat.id}</code>", parse_mode="HTML")
    
    elif msg.text.startswith("/premium"):
        try:
            _, chat_id = msg.text.split(maxsplit=1)
            set_premium(chat_id)
            await msg.reply(f"✅ Premium mode enabled for chat <code>{chat_id}</code>", parse_mode="HTML")
        except ValueError:
            await msg.reply("❌ Usage: /premium <chat_id>")
