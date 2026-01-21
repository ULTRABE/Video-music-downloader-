import re
from utils.adult import is_adult
from utils.state import save_adult_link, get_adult_link, is_premium_group
from services.downloader import process_video
from ui.keyboards import private_button
from ui.text import ADULT_PM

URL = re.compile(r"https?://\S+")

async def handle_message(update, context):
    msg = update.message
    text = msg.text or msg.caption or ""
    m = URL.search(text)
    if not m:
        return

    url = m.group(0)
    chat = msg.chat
    user = msg.from_user.id

    try: await msg.delete()
    except: pass

    if is_adult(url):
        if chat.type != "private" and not is_premium_group(chat.id):
            save_adult_link(user, url)
            me = await context.bot.get_me()
            await context.bot.send_message(
                chat.id,
                "🔞 Adult content → private only",
                reply_markup=private_button(me.username)
            )
            return

        await process_video(update, context, url, pin=True, auto_delete=True)
        return

    if is_premium_group(chat.id):
        return  # normal videos disabled

    await process_video(update, context, url, pin=True)
