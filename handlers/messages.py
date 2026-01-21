import re
from aiogram import Router
from aiogram.types import Message

from utils.state import save_adult, pop_adult, is_premium
from utils.downloader import download_video
from ui.keyboards import pm_kb
from utils.platforms import detect_platform

router = Router()

ADULT_SITES = ("pornhub", "xvideos", "xnxx", "xhamster", "youporn")
URL_RE = re.compile(r"https?://\S+")

@router.message()
async def handler(msg: Message):
    if not msg.text:
        return

    m = URL_RE.search(msg.text)
    if not m:
        return

    url = m.group(0)
    is_adult = any(x in url.lower() for x in ADULT_SITES)

    platform, fmt = detect_platform(url)

    # ❌ Not a supported platform
    if not platform and not is_adult:
        return

    # ── GROUP LOGIC ─────────────────────────
    if msg.chat.type in ("group", "supergroup"):
        if is_adult:
            await msg.delete()
            save_adult(msg.from_user.id, url)
            await msg.answer(
                "This video can only be downloaded in private.",
                reply_markup=pm_kb((await msg.bot.get_me()).username)
            )
            return

        if is_premium(msg.chat.id):
            return

        await download_video(
            msg,
            url,
            ydl_format=fmt,
            pin=True
        )
        return

    # ── PRIVATE LOGIC ───────────────────────
    stored = pop_adult(msg.from_user.id)
    if stored:
        platform, fmt = detect_platform(stored)
        await download_video(
            msg,
            stored,
            ydl_format=fmt,
            adult=True
        )
        return

    await download_video(
        msg,
        url,
        ydl_format=fmt
    )
