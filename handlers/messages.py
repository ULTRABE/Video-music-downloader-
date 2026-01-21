import re
import logging
from aiogram import Router
from aiogram.types import Message

from config import OWNER_ID
from services.downloader import download_video
from utils.platforms import detect_platform
from utils.rate_limit import check_rate_limit
from utils.state import save_adult, pop_adult, is_premium_group
from ui.keyboards import pm_kb

logger = logging.getLogger(__name__)
messages_router = Router()

URL_RE = re.compile(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be|instagram\.com|tiktok\.com|facebook\.com|twitter\.com|x\.com|pornhub\.com|xvideos\.com|xnxx\.com)[^\s<>"\]]+', re.IGNORECASE)

@messages_router.message()
async def handle_message(msg: Message):
    if not msg.text:
        return

    urls = URL_RE.findall(msg.text)
    if not urls:
        return

    url = urls[0]  # First URL only
    logger.info(f"🔍 URL detected: {url[:50]}... from user {msg.from_user.id}")

    # Rate limit
    if not check_rate_limit(msg.from_user.id):
        logger.warning(f"Rate limited user {msg.from_user.id}")
        await msg.reply("⏳ Too fast. Wait 30 seconds.")
        return

    # Platform detection
    platform = detect_platform(url)
    if not platform:
        logger.warning(f"❌ No platform matched: {url[:50]}...")
        return

    logger.info(f"✅ Platform: adult={platform['adult']}, format={platform['format']}")

    chat_type = msg.chat.type

    # GROUP HANDLING
    if chat_type in ("group", "supergroup"):
        is_adult_content = platform.get("adult", False)  # ✅ SAFE ACCESS
        
        if is_adult_content:
            logger.info("🔞 Adult content → PM redirect")
            await msg.delete()
            save_adult(msg.from_user.id, url)
            me = await msg.bot.get_me()
            await msg.answer(
                "🔞 <b>Adult content</b>\n\n"
                "Download in <a href='https://t.me/{}'>private chat</a> only.",
                reply_markup=pm_kb(me.username),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return

        # Non-premium groups: auto-pin
        if not is_premium_group(msg.chat.id):
            logger.info("📌 Group download + pin")
            await msg.delete()
            await download_video(msg, url, platform["format"], pin=True)
            return

    # PRIVATE CHAT - ADULT FROM GROUP?
    stored_url = pop_adult(msg.from_user.id)
    if stored_url:
        logger.info("🔞 Private adult download")
        p = detect_platform(stored_url)
        if p:
            await download_video(msg, stored_url, p["format"], adult=True)
        return

    # NORMAL PRIVATE DOWNLOAD
    logger.info("📥 Private download")
    await download_video(msg, url, platform["format"])

    logger.info("✅ Message handler complete")
