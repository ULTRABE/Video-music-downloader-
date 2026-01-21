from services.downloader import ACTIVE

async def handle_callback(update, context):
    q = update.callback_query
    if q.data.startswith("cancel:"):
        ACTIVE.pop(q.data.split(":")[1], None)
        await q.answer("Cancelled")
