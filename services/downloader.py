import asyncio
import uuid
import subprocess
import logging
from pathlib import Path
from config import TEMP_DIR, MAX_VIDEO_MB, ADULT_TTL
from utils.state import is_cancelled, clear_cancel
from ui.keyboards import cancel_kb

logger = logging.getLogger(__name__)

async def download_video(msg, url, ydl_format, pin=False, adult=False):
    bot = msg.bot
    chat_id = msg.chat.id
    task_id = str(uuid.uuid4())
    out_file = TEMP_DIR / f"{task_id}.%(ext)s"

    try:
        status = await msg.answer("⬇️ Downloading…", reply_markup=cancel_kb(task_id))
        logger.info(f"Starting download: {url}")

        cmd = [
            "yt-dlp",
            "-f", ydl_format,
            "--no-playlist",
            "-o", str(out_file),
            url
        ]
        
        logger.debug(f"yt-dlp command: {' '.join(cmd)}")
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Process monitoring
        while True:
            if is_cancelled(task_id):
                proc.kill()
                await status.edit_text("❌ Cancelled by user")
                logger.info(f"Download cancelled: {task_id}")
                break
                
            if proc.returncode is not None:
                break
                
            await asyncio.sleep(1)

        if proc.returncode != 0:
            stderr = (await proc.stderr.read()).decode(errors='ignore')
            error_msg = stderr[:200] if stderr else "Unknown error"
            await status.edit_text(f"❌ Download failed: {error_msg}")
            logger.error(f"yt-dlp failed: {error_msg}")
            return

        # Find output file
        mp4_file = None
        for ext in ['mp4', 'mkv', 'webm', 'mp4']:
            candidate = TEMP_DIR / f"{task_id}.{ext}"
            if candidate.exists():
                mp4_file = candidate
                break
        
        if not mp4_file:
            await status.edit_text("❌ No video file created")
            return

        size_mb = mp4_file.stat().st_size / (1024 * 1024)
        await status.edit_text("📤 Uploading…")

        if size_mb <= MAX_VIDEO_MB:
            with open(mp4_file, "rb") as f:
                sent = await bot.send_video(chat_id, f)
        else:
            with open(mp4_file, "rb") as f:
                sent = await bot.send_document(
                    chat_id, f,
                    caption="📎 Video exceeded 45MB, sent as document"
                )

        if pin:
            try:
                await bot.pin_chat_message(chat_id, sent.message_id)
            except Exception as e:
                logger.warning(f"Pin failed: {e}")

        await status.delete()
        logger.info(f"Download complete: {task_id}")

        # Adult cleanup
        if adult:
            warn = await bot.send_message(
                chat_id,
                f"⚠️ <b>Adult content</b>\nAuto-deletes in {ADULT_TTL}s.",
                parse_mode="HTML"
            )
            await asyncio.sleep(ADULT_TTL)
            try:
                await sent.delete()
                await warn.delete()
            except:
                pass

    except Exception as e:
        logger.error(f"Download error {task_id}: {e}", exc_info=True)
        await msg.reply(f"❌ Failed: {str(e)}")
    finally:
        # Cleanup
        for f in TEMP_DIR.glob(f"{task_id}.*"):
            try:
                f.unlink()
            except:
                pass
        clear_cancel(task_id)
