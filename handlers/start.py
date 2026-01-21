from aiogram import Router
from aiogram.types import Message

router = Router()

@router.message()
async def start(msg: Message):
    if msg.text != "/start":
        return

    await msg.reply(
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
    )
