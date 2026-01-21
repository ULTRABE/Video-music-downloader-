import re
from aiogram import Router
from aiogram.types import Message
from utils.state import save_adult_link, get_adult_link, is_premium_group
from ui.keyboards import adult_redirect_kb

messages_router = Router()

ADULT_DOMAINS = (
    "pornhub.org",
    "xvideos.com",
    "xnxx.com",
    "xhamster44.desi",
    "youporn.com"
)

URL_RE = re.compile(r"https?://\S+")

@messages_router.message()
async def handle_links(message: Message):
    if not message.text:
        return

    urls = URL_RE.findall(message.text)
    if not urls:
        return

    url = urls[0]
    is_adult = any(d in url for d in ADULT_DOMAINS)

    # GROUP LOGIC
    if message.chat.type in ("group", "supergroup"):
        if is_adult:
            await message.delete()
            save_adult_link(message.from_user.id, url)
            await message.answer(
                "Adult content → continue in private",
                reply_markup=adult_redirect_kb()
            )
        else:
            await message.answer("Normal video detected (GC logic placeholder)")
        return

    # PRIVATE LOGIC
    if message.chat.type == "private":
        stored = get_adult_link(message.from_user.id)
        final_url = stored or url

        await message.answer(
            f"Downloading:\n{final_url}\n\n(This will auto-delete in 1 min)"
        )
