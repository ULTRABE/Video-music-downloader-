import asyncio
import uuid
import subprocess  # ✅ FIXED: Import subprocess
import os
from pathlib import Path
from config import TEMP_DIR, MAX_VIDEO_MB, ADULT_TTL
from utils.state import is_cancelled, clear_cancel
from ui.keyboards import cancel_kb

async def download_video(msg, url, ydl_format, pin=False, adult=False):
    bot = msg.bot
    chat_id = msg.chat.id
    task_id = str(uuid.uuid4())
    out_file = TEMP_DIR / f"{task_id}.%(ext)s"

    try:
        status = await msg.answer("⬇️ Downloading…", reply_markup=cancel_kb(task_id))

        # ✅ FIXED: Correct subprocess.PIPE import
        cmd = [
            "yt-dlp",
            "-f", ydl_format,
            "--no-playlist",
            "-o", str(out_file),
            url
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,  # ✅ FIXED
            stderr=subprocess.PIPE   # ✅ FIXED
        )

        # ✅ FIXED: Correct process monitoring (NO await proc.poll())
        while True:
            if is_cancelled(task_id):
                proc.kill()
                await status.edit_text("❌ Cancelled by user")
                break
                
            if proc.returncode is not None:
                break
                
            await asyncio.sleep(1)

        if proc.returncode != 0:
            stderr = (await proc.stderr.read()).decode()
            await status.edit_text(f"❌ Failed: {stderr[:100]}...")
            return

        # Rest of the code unchanged...
        # Find output file
        mp4_file = None
        for ext in ['mp4', 'mkv', 'webm']:
            candidate = TEMP_DIR / f"{task_id}.{ext}"
            if candidate.exists():
                mp4_file = candidate
                break
        
        if not mp4_file or not mp4_file.exists():
            await status.edit_text("❌ No valid video file found")
            return

        # Check size
        size_mb = mp4_file.stat().st_size / (1024 * 1024)
        await status.edit_text("📤 Uploading…")

        if size_mb <= MAX_VIDEO_MB:
            with mp4_file.open("rb") as f:
                sent = await bot.send_video(chat_id, f)
        else:
            with mp4_file.open("rb") as f:
                sent = await bot.send_document(
                    chat_id, f,
                    caption="📎 Video exceeded 45MB, sent as document"
                )

        # Pin if requested
        if pin:
            try:
                await bot.pin_chat_message(chat_id, sent.message_id)
            except:
                pass

        await status.delete()

        # Adult content cleanup
        if adult:
            warn = await bot.send_message(
                chat_id,
                "⚠️ <b>Adult content</b>\nThis message will auto-delete in 1 minute.",
                parse_mode="HTML"
            )
            await asyncio.sleep(ADULT_TTL)
            try:
                await sent.delete()
                await warn.delete()
            except:
                pass

    except Exception as e:
        await msg.reply(f"❌ Error: {str(e)}")
    finally:
        # Cleanup
        for f in TEMP_DIR.glob(f"{task_id}.*"):
            try:
                f.unlink()
            except:
                pass
        clear_cancel(task_id)
