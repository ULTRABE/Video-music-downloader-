import asyncio, uuid, subprocess
from config import TEMP_DIR, MAX_MB, ADULT_TTL
from utils.state import cancelled
from ui.keyboards import cancel_kb

async def download_video(
    msg,
    url,
    ydl_format,
    pin=False,
    adult=False
):
    bot = msg.bot
    chat_id = msg.chat.id
    task_id = str(uuid.uuid4())

    status = await msg.answer(
        "⬇️ Downloading…",
        reply_markup=cancel_kb(task_id)
    )

    out = TEMP_DIR / f"{task_id}.mp4"

    cmd = [
        "yt-dlp",
        "-f", ydl_format,
        "-o", str(out),
        url
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    while True:
        if cancelled(task_id):
            proc.kill()
            await status.edit_text("❌ Cancelled")
            return
        if proc.returncode is not None:
            break
        await asyncio.sleep(1)
        await proc.poll()

    size_mb = out.stat().st_size / (1024 * 1024)

    await status.edit_text("📤 Uploading…")

    if size_mb <= MAX_MB:
        sent = await bot.send_video(chat_id, out.open("rb"))
    else:
        sent = await bot.send_document(
            chat_id,
            out.open("rb"),
            caption="This video exceeded 45 MB and was sent as a document."
        )

    if pin:
        try:
            await bot.pin_chat_message(chat_id, sent.message_id)
        except:
            pass

    await status.delete()

    if adult:
        warn = await bot.send_message(
            chat_id,
            "⚠️ This message will be deleted in 1 minute. Save it."
        )
        await asyncio.sleep(ADULT_TTL)
        await sent.delete()
        await warn.delete()

    out.unlink(missing_ok=True)
