import asyncio
import uuid
import subprocess
from pathlib import Path

from config import TEMP_DIR, MAX_VIDEO_MB, ADULT_TTL
from utils.state import is_cancelled, clear_cancel
from ui.keyboards import cancel_kb

FAKE_PROGRESS = ["⬛⬜⬜⬜⬜", "⬛⬛⬜⬜⬜", "⬛⬛⬛⬜⬜", "⬛⬛⬛⬛⬜", "⬛⬛⬛⬛⬛"]

async def download_video(
    msg,
    url: str,
    ydl_format: str,
    *,
    pin: bool = False,
    adult: bool = False
):
    bot = msg.bot
    chat_id = msg.chat.id
    task_id = str(uuid.uuid4())

    status = await msg.answer(
        "⬇️ **Preparing download…**\n⬜⬜⬜⬜⬜",
        reply_markup=cancel_kb(task_id)
    )

    out: Path = TEMP_DIR / f"{task_id}.mp4"

    cmd = [
        "yt-dlp",
        "-f", ydl_format,
        "-o", str(out),
        "--no-playlist",
        "--quiet",
        url
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # ── Fake progress animation ──
    for bar in FAKE_PROGRESS:
        await asyncio.sleep(1)

        if is_cancelled(task_id):
            proc.kill()
            clear_cancel(task_id)
            await status.edit_text("❌ **Download cancelled**")
            if out.exists():
                out.unlink(missing_ok=True)
            return

        await status.edit_text(
            f"⬇️ **Downloading…**\n{bar}",
            reply_markup=cancel_kb(task_id)
        )

    await proc.wait()

    if not out.exists():
        await status.edit_text("❌ **Download failed**")
        clear_cancel(task_id)
        return

    size_mb = out.stat().st_size / (1024 * 1024)

    await status.edit_text("📤 **Uploading…**")

    if size_mb <= MAX_VIDEO_MB:
        with out.open("rb") as f:
            sent = await bot.send_video(chat_id, f)
    else:
        with out.open("rb") as f:
            sent = await bot.send_document(
                chat_id,
                f,
                caption="This video exceeded 45 MB and was sent as a document."
            )

    if pin:
        try:
            await bot.pin_chat_message(chat_id, sent.message_id)
        except Exception:
            pass

    await status.delete()

    # ── Adult auto-delete logic ──
    if adult:
        warn = await bot.send_message(
            chat_id,
            "⚠️ **This message will be deleted in 1 minute.**\nSave it to Saved Messages."
        )
        await asyncio.sleep(ADULT_TTL)
        await sent.delete()
        await warn.delete()

    out.unlink(missing_ok=True)
    clear_cancel(task_id)
