import asyncio
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ChatAction

router = Router()

# ── Localized text pack ─────────────────────────────
TEXT = {
    "en": (
        "𝐕𝐢𝐝𝐞𝐨 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐞𝐫 𝐁𝐨𝐭\n\n"
        "𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝗲𝗱 𝗣𝗹𝗮𝘁𝗳𝗼𝗿𝗺𝘀\n"
        "• YouTube (Videos & Shorts)\n"
        "• Instagram (Posts & Reels)\n"
        "• TikTok\n"
        "• Twitter / X\n"
        "• Facebook (Videos & Reels)\n\n"
        "𝗛𝗼𝘄 𝗶𝘁 𝘄𝗼𝗿𝗸𝘀\n"
        "• Send a supported video link\n"
        "• Download starts automatically\n"
        "• Live progress with cancel option\n"
        "• Optimized for fast delivery\n\n"
        "𝗡𝗼𝘁𝗲\n"
        "Some videos may be unavailable due to platform restrictions."
    ),
    "hi": (
        "𝐕𝐢𝐝𝐞𝐨 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐞𝐫 𝐁𝐨𝐭\n\n"
        "𝗦𝗮𝗺𝗮𝗿𝘁𝗵𝗶𝘁 𝗣𝗹𝗮𝘁𝗳𝗼𝗿𝗺\n"
        "• YouTube (Videos & Shorts)\n"
        "• Instagram (Posts & Reels)\n"
        "• TikTok\n"
        "• Twitter / X\n"
        "• Facebook (Videos & Reels)\n\n"
        "𝗞𝗮𝗶𝘀𝗲 𝗸𝗮𝗮𝗺 𝗸𝗮𝗿𝘁𝗮 𝗵𝗮𝗶\n"
        "• Video link bhejein\n"
        "• Download apne aap start ho jaata hai\n"
        "• Live progress aur cancel option\n\n"
        "𝗡𝗼𝘁𝗲\n"
        "Kuch videos platform rules ki wajah se available nahi ho sakte."
    )
}

# ── Start handler ───────────────────────────────────
@router.message()
async def start(msg: Message):
    if msg.text != "/start":
        return

    # Dynamic username / name
    name = msg.from_user.first_name or "there"

    # Language detection (fallback to English)
    lang = (msg.from_user.language_code or "en")[:2]
    text = TEXT.get(lang, TEXT["en"])

    # Fake typing animation
    await msg.bot.send_chat_action(
        chat_id=msg.chat.id,
        action=ChatAction.TYPING
    )
    await asyncio.sleep(1.2)

    await msg.reply(
        f"Hey {name},\n\n{text}"
    )
