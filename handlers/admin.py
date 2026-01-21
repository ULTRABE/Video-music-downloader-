from config import OWNER_ID
from utils.state import set_premium_group

async def chatid(update, context):
    u = update.effective_user
    c = update.effective_chat
    await update.message.reply_text(
        f"Chat ID: {c.id}\nUser ID: {u.id}\nUsername: {u.username}"
    )

async def premium(update, context):
    if update.effective_user.id != OWNER_ID:
        return

    chat_id = int(context.args[0])
    set_premium_group(chat_id)
    await update.message.reply_text("✅ Premium adult mode enabled.")
