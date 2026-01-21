from utils.state import get_adult_link
from ui.text import ADULT_PM
from services.downloader import process_video

async def start(update, context):
    if context.args and context.args[0] == "adult":
        await update.message.reply_text(ADULT_PM, parse_mode="Markdown")
        link = get_adult_link(update.effective_user.id)
        if link:
            await process_video(update, context, link, auto_delete=True)
