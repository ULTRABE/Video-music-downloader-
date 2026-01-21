import asyncio
import yt_dlp
from pathlib import Path
from config import TEMP_DIR, MAX_VIDEO_MB
from utils.rate_limit import done_request
from ui import text

DOWNLOAD_SEM = asyncio.Semaphore(2)

async def process_video(update, context, url: str, user_id: int):
    chat_id = update.effective_chat.id
    status = await context.bot.send_message(chat_id, text.ANALYZING)

    try:
        async with DOWNLOAD_SEM:
            await status.edit_text(text.DOWNLOADING)
            path = await download(url)

            if not path:
                raise RuntimeError("download failed")

            size_mb = path.stat().st_size / (1024 * 1024)
            await status.edit_text(text.PROCESSING)

            with open(path, "rb") as f:
                if size_mb <= MAX_VIDEO_MB:
                    sent = await context.bot.send_video(chat_id, f, supports_streaming=True)
                else:
                    sent = await context.bot.send_document(chat_id, f)

            await status.delete()

    except Exception:
        await status.edit_text(text.FAILED)

    finally:
        done_request(user_id)
