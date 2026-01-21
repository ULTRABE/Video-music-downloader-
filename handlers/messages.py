import re
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from config import ADULT_TTL, OWNER_ID  # ✅ FIXED: Import missing constants
from services.downloader import download_video
from utils.platforms import detect_platform
from utils.rate_limit import check_rate_limit
from utils.state import save_adult, pop_adult, is_premium_group
from ui.keyboards import pm_kb

logger = logging.getLogger(__name__)
messages_router = Router()
URL_RE = re.compile(r'https?://[^\s<>"]+[^\s<>\)]?')  # ✅ FIXED: Better regex

@messages_router.message()
async def handle_message(msg: Message):
    if not msg.text:
        return

    urls = URL_RE.findall(msg.text)
    if not urls:
        return

    url = urls[0]  # Take first URL
    logger.info(f"Processing URL: {url} from user {msg.from_user.id}")

    # Rate limit check
    if not check_rate_limit(msg.from_user.id):
        await msg.reply("⏳ Slow down. Try again in 30s.")
        return

    # Platform detection
    platform = detect_platform(url)
    if not platform:
        logger.warning(f"No platform detected for: {url}")
        return

    logger.info(f"Detected platform: {platform}")

    # Group handling
    if msg.chat.type in ("group", "supergroup"):
        is_adult = platform.get("adult", False)  # ✅ FIXED: Safe dict access
        
        if is_adult:
            await msg.delete()
            save_adult(msg.from_user.id, url)
            me = await msg.bot.get_me()
            await msg.answer(
                "🔞 Adult content can only be downloaded in private.",
                reply_markup=pm_kb(me.username)
            )
            return

        if not is_premium_group(msg.chat.id):
            await msg.delete()
            await download_video(
                msg=msg,
                url=url,
                ydl_format=platform["format"],
                pin=True
            )
            return

    # Private chat - check for stored adult content
    stored = pop_adult(msg.from_user.id)
    if stored:
        p = detect_platform(stored)
        if p:
            await download_video(
                msg=msg,
                url=stored,
                ydl_format=p["format"],
                adult=True
            )
        return

    # Normal private download
    await download_video(
        msg=msg,
        url=url,
        ydl_format=platform["format"]
    )
