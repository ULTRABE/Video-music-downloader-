from aiogram import Router  # ✅ MISSING IMPORT
from aiogram.types import CallbackQuery
from utils.state import cancel

callbacks_router = Router()  # ✅ MISSING DEFINITION

@callbacks_router.callback_query(lambda c: c.data.startswith("cancel:"))
async def cancel_cb(cb: CallbackQuery):
    task_id = cb.data.split(":")[1]
    cancel(task_id)
    await cb.answer("❌ Cancelled")
