from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def adult_redirect_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Continue in Private",
                    url="https://t.me/@nagudownloaderbot?start=adult"
                )
            ]
        ]
    )
