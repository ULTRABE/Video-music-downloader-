import yt_dlp, asyncio, uuid
from pathlib import Path
from config import *
from utils.progress import bar
from ui.keyboards import cancel_button

ACTIVE = {}
SEM = asyncio.Semaphore(GLOBAL_DOWNLOADS)

def clean(name):
    return "".join(c if c.isalnum() or c in " ._-" else "_" for c in name)[:120]

async def process_video(update, context, url, pin=False, auto_delete=False):
    chat = update.effective_chat.id
    task = str(uuid.uuid4())
    ACTIVE[task] = True

    status = await context.bot.send_message(
        chat, f"Downloading\n{bar(1)}", reply_markup=cancel_button(task)
    )

    async with SEM:
        if not ACTIVE.get(task):
            return

        opts = {
            "quiet": True,
            "format": "best[height<=720]/best",
            "outtmpl": str(TEMP_DIR / "%(title)s.%(ext)s"),
            "merge_output_format": "mp4"
        }

        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=True)
            path = Path(y.prepare_filename(info)).with_suffix(".mp4")

        title = clean(path.stem)
        size = path.stat().st_size / (1024*1024)

        if size <= MAX_VIDEO_MB:
            sent = await context.bot.send_video(chat, open(path,"rb"), caption=title)
        else:
            sent = await context.bot.send_document(
                chat, open(path,"rb"),
                filename=f"{title}.mp4",
                caption="This video exceeded the 45 MB limit, so it was sent as a document."
            )

        if pin:
            try:
                await context.bot.pin_chat_message(chat, sent.message_id, disable_notification=True)
            except:
                pass

        if auto_delete:
            await asyncio.sleep(60)
            try:
                await sent.delete()
            except:
                pass

        await status.delete()
        ACTIVE.pop(task, None)
