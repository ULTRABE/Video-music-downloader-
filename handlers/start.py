from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.utils.chat_action import ChatActionSender
import asyncio

start_router = Router()

# ── Localized text (extend later) ───────────────────
TEXT = {
    "en": {
        "title": "✨ 𝐔𝐋𝐓𝐑𝐀𝐁𝐄 ✨",
        "subtitle": "Fast • Clean • Smart Media Downloader",
        "body": (
            "Hey {name},\n\n"
            "I can download videos from:\n"
            "• YouTube (videos & shorts)\n"
            "• Instagram (posts & reels)\n"
            "• TikTok\n"
            "• X / Twitter\n"
            "• Facebook\n\n"
            "Just send a link and chill.\n"
            "I’ll handle the rest."
        ),
        "footer": (
            "\n\n⚡ <i>Tip:</i> Large files may take a bit.\n"
            "📌 Groups supported.\n"
            "🔒 Private chats supported."
        )
    }
}

def get_lang(message: Message) -> str:
    code = (message.from_user.language_code or "en").lower()
    return "en" if code not in TEXT else code


@start_router.message(lambda m: m.text == "/start")
async def start_handler(message: Message):
    lang = get_lang(message)
    data = TEXT[lang]

    name = message.from_user.first_name or "there"

    text = (
        f"<b>{data['title']}</b>\n"
        f"<i>{data['subtitle']}</i>\n\n"
        f"{data['body'].format(name=name)}"
        f"{data['footer']}"
    )

    # ── Fake typing effect ───────────────────────────
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        await asyncio.sleep(1.4)

    await message.answer(
        text,
        disable_web_page_preview=True
    )
