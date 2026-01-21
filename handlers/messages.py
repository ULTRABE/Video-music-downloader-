import re
from aiogram import Router
from aiogram.types import Message

from services.downloader import download_video
from utils.platforms import detect_platform
from utils.rate_limit import check_rate_limit
from utils.state import (
    save_adult,
    pop_adult,
    is_premium_group,
)
from ui.keyboards import pm_kb

messages_router = Router()

URL_RE = re.compile(r"https?://\S+")

@messages_router.message()
async def handle_message(msg: Message):
    if not msg.text:
        return

    match = URL_RE.search(msg.text)
    if not match:
        return

    url = match.group(0)

    # Rate limit (per-user, global)
    if not check_rate_limit(msg.from_user.id):
        await msg.reply("⏳ Too many requests. Try again shortly.")
        return

    platform = detect_platform(url)

    # Not supported at all
    if not platform:
        return

    is_adult = platform["adult"]
    ydl_format = platform["format"]

    # ── GROUP / SUPERGROUP LOGIC ─────────────────────
    if msg.chat.type in ("group", "supergroup"):
        # Adult content → force PM
        if is_adult:
            await msg.delete()
            save_adult(msg.from_user.id, url)

            me = await msg.bot.get_me()
            await msg.answer(
                "🔞 This video can only be downloaded in private.\n"
                "Tap below to continue 👇",
                reply_markup=pm_kb(me.username)
            )
            return

        # Premium group: adult-only mode enabled → block normal downloads
        if is_premium_group(msg.chat.id):
            return

        # Normal GC download
        await msg.delete()
        await download_video(
            msg=msg,
            url=url,
            ydl_format=ydl_format,
            pin=True,
            adult=False
        )
        return

    # ── PRIVATE CHAT LOGIC ───────────────────────────
    stored = pop_adult(msg.from_user.id)
    if stored:
        # Silent adult flow (no UI hint)
        platform = detect_platform(stored)
        if platform:
            await download_video(
                msg=msg,
                url=stored,
                ydl_format=platform["format"],
                adult=True
            )
        return

    # Normal private download
    await download_video(
        msg=msg,
        url=url,
        ydl_format=ydl_format,
        adult=False
    )
