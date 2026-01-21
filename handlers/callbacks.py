from aiogram import Router, F
from aiogram.types import CallbackQuery

callbacks_router = Router()

@callbacks_router.callback_query(F.data == "adult_go")
async def adult_redirect(cb: CallbackQuery):
    await cb.message.answer("Send the link again here to start download.")
    await cb.answer()
