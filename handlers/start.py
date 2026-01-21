from aiogram import Router
from aiogram.types import Message

start_router = Router()

@start_router.message()
async def start_cmd(message: Message):
    if message.text != "/start":
        return

    await message.reply(
        "Send a video link.\n"
        "Adult links work only in private.\n"
        "Files auto-delete after 1 minute."
    )
