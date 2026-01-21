from aiogram import Router, F
from aiogram.types import CallbackQuery
from utils.state import cancel

router = Router()

@router.callback_query(F.data.startswith("cancel:"))
async def cancel_download(cb: CallbackQuery):
    cancel(cb.data.split(":")[1])
    await cb.answer("Download cancelled")
