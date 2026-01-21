from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def private_button(bot_username: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 Open Private Chat", url=f"https://t.me/{bot_username}")]
    ])
