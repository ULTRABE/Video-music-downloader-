from telegram.ext import ContextTypes
from utils.urls import extract_url, is_supported, is_adult
from utils.rate_limit import allow_request, done_request
from ui import text
from services.downloader import process_video

async def handle_message(update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    url = extract_url(msg.text or msg.caption or "")
    if not url:
        return

    user_id = msg.from_user.id

    if not await allow_request(user_id):
        await msg.reply_text(text.TOO_FAST)
        return

    try:
        await msg.delete()
    except:
        pass

    if is_adult(url) and msg.chat.type != "private":
        me = await context.bot.get_me()
        await context.bot.send_message(
            msg.chat.id,
            text.PRIVATE_ONLY,
            reply_markup=private_button(me.username)
        )
        done_request(user_id)
        return

    await process_video(update, context, url, user_id)
