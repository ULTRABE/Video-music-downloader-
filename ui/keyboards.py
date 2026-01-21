from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def cancel_kb(task_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"cancel:{task_id}"
            )]
        ]
    )

def pm_kb(username):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔒 Open in Private",
                url=f"https://t.me/{username}"
            )]
        ]
    )
