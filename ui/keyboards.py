from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def private_button(bot):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 Download in Private", url=f"https://t.me/{bot}?start=adult")]
    ])

def cancel_button(task):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{task}")]
    ])
