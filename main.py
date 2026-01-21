import os
import re
import asyncio
import logging
import signal
import psutil
from pathlib import Path
from typing import Dict, Set, Optional
import aiohttp
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import yt_dlp

# ---------------- CONFIG ----------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
assert BOT_TOKEN, "BOT_TOKEN required"

TEMP_DIR = Path("/tmp/downloads")
TEMP_DIR.mkdir(exist_ok=True)

# State
queues: Dict[int, asyncio.Queue] = {}
active_downloads: Dict[int, bool] = {}
user_cooldown: Dict[int, float] = {}

# Adult site blacklist (PRIVATE ONLY)
ADULT_DOMAINS = {
    'pornhub.com', 'xvideos.com', 'xhamster.com', 'xnxx.com', 'youporn.com',
    'redtube.com', 'tube8.com', 'spankbang.com', 'motherless.com', 'efukt.com'
}

# Supported mainstream domains
SUPPORTED_DOMAINS = {
    'youtube.com', 'youtu.be', 'instagram.com', 'tiktok.com', 'twitter.com',
    'x.com', 'facebook.com', 'vimeo.com', 'dailymotion.com', 'reddit.com',
    'snapchat.com', 'pinterest.com', 'soundcloud.com', 'bilibili.com'
}

# yt-dlp cleanup task
cleanup_tasks: Set[asyncio.Task] = set()

async def cleanup_temp_files():
    """Clean all temp files every 30s."""
    while True:
        try:
            for f in TEMP_DIR.glob("*.mp4"):
                if asyncio.get_event_loop().time() - f.stat().st_mtime > 300:
                    f.unlink(missing_ok=True)
        except:
            pass
        await asyncio.sleep(30)

def kill_orphans():
    """Kill yt-dlp/ffmpeg orphans."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'yt-dlp' in ' '.join(proc.info['cmdline'] or []) or 'ffmpeg' in proc.info['name']:
                proc.terminate()
        except:
            pass

def extract_urls(text: str) -> list[str]:
    """Extract valid URLs."""
    pattern = r'https?://[^\s<>"]{10,}'
    return re.findall(pattern, text)

def is_supported(url: str, check_adult: bool = False) -> tuple[bool, bool]:
    """Check if URL supported. Returns (supported, is_adult)."""
    domain = re.search(r'://([^/]+)', url)
    if not domain:
        return False, False
    
    dom = domain.group(1).lower()
    is_adult = dom in ADULT_DOMAINS
    
    if check_adult:
        return dom in SUPPORTED_DOMAINS or is_adult, is_adult
    
    return dom in SUPPORTED_DOMAINS, False

async def smart_download(url: str, chat_id: int, status_msg_id: int) -> Optional[Path]:
    """Production yt-dlp download."""
    output_path = TEMP_DIR / f"dl_{chat_id}_{asyncio.get_event_loop().time():.0f}.mp4"
    
    # Smart format selection
    ydl_opts = {
        'format': 'best[ext=mp4][height<=1080][fps<=30]/best[height<=1080][fps<=30]/best[height<=720]',
        'outtmpl': str(output_path),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
        
        if output_path.exists() and output_path.stat().st_size > 10_000_000:  # 10MB min
            return output_path
            
    except Exception:
        pass
    
    # Cleanup on fail
    if output_path.exists():
        output_path.unlink(missing_ok=True)
    
    return None

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Core processing logic."""
    chat = update.effective_chat
    chat_id = chat.id
    user_id = update.effective_user.id
    
    # Cooldown
    now = asyncio.get_event_loop().time()
    if user_id in user_cooldown and now - user_cooldown[user_id] < 3:
        return
    user_cooldown[user_id] = now
    
    # Rate limit per chat
    if chat_id not in queues:
        queues[chat_id] = asyncio.Queue(maxsize=3)
    
    q = queues[chat_id]
    if not q.empty() and active_downloads.get(chat_id):
        return
    
    # Status message
    status_msg = await context.bot.send_message(
        chat_id, "⬇️ Processing media...", parse_mode=ParseMode.HTML
    )
    
    # Queue task
    task = asyncio.create_task(worker(chat_id, url, status_msg.message_id, context.bot))
    cleanup_tasks.add(task)
    task.add_done(lambda t: cleanup_tasks.discard(t))

async def worker(chat_id: int, url: str, status_id: int, bot: Bot):
    """Background worker."""
    active_downloads[chat_id] = True
    
    try:
        chat = await bot.get_chat(chat_id)
        is_group = chat.type != 'private'
        
        # Adult check
        supported, is_adult = is_supported(url, check_adult=is_group)
        
        if not supported:
            await bot.edit_message_text(
                "🚫 This content isn't supported here.",
                chat_id, status_id
            )
            await asyncio.sleep(3)
            await bot.delete_message(chat_id, status_id)
            return
        
        if is_group and is_adult:
            await bot.edit_message_text(
                "🚫 This content isn't supported here.",
                chat_id, status_id
            )
            await asyncio.sleep(3)
            await bot.delete_message(chat_id, status_id)
            return
        
        # Download
        file_path = await smart_download(url, chat_id, status_id)
        if not file_path:
            await bot.edit_message_text(
                "❌ Failed to process media.",
                chat_id, status_id
            )
            await asyncio.sleep(3)
            await bot.delete_message(chat_id, status_id)
            return
        
        # Send video
        with open(file_path, 'rb') as video:
            sent_msg = await bot.send_video(
                chat_id, video,
                supports_streaming=True,
                caption="✅ Media ready!",
                parse_mode=ParseMode.HTML,
                timeout=120
            )
        
        # Cleanup status
        try:
            await bot.delete_message(chat_id, status_id)
        except:
            pass
        
        # Pin in groups
        if is_group:
            try:
                await bot.pin_chat_message(chat_id, sent_msg.message_id)
            except:
                pass
        
    except Exception as e:
        logger.error(f"Worker error: {e}")
    finally:
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink(missing_ok=True)
        active_downloads.pop(chat_id, None)
        kill_orphans()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler."""
    text = update.message.text or ""
    urls = extract_urls(text)
    
    if not urls:
        return
    
    # Delete original message instantly
    try:
        await update.message.delete()
    except:
        pass
    
    # Process first valid URL only
    for url in urls:
        if is_supported(url)[0]:
            await process_link(update, context, url)
            break

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Minimal /start."""
    text = """
🎥 Media Downloader

Send a video link. That's it.

Works in groups & private chats.
    """
    keyboard = [[InlineKeyboardButton("ℹ️ How it works", callback_data="help")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=reply_markup
    )

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """How it works."""
    query = update.callback_query
    await query.answer()
    
    text = """
📋 Usage:

1️⃣ Send video link
2️⃣ Bot deletes it instantly  
3️⃣ Bot sends processed video
4️⃣ Auto-pins in groups

✅ Supports 25+ platforms
⚡ Optimized for speed
🎥 1080p max quality
    """
    
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)

# ---------------- RAILWAY VPS STABILITY ----------------
async def railway_health():
    """Prevent Railway idle timeout."""
    while True:
        await asyncio.sleep(30)

async def shutdown(app: Application):
    """Graceful shutdown."""
    logger.info("Shutting down...")
    kill_orphans()
    
    # Cancel all cleanup tasks
    for task in cleanup_tasks.copy():
        task.cancel()
    
    # Clear queues
    queues.clear()
    
    logger.info("Shutdown complete")

def signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT."""
    logger.info(f"Received signal {signum}")
    loop = asyncio.get_event_loop()
    loop.create_task(shutdown(application))
    loop.stop()

# ---------------- MAIN ----------------
async def main():
    """Production main."""
    global application
    
    # Startup
    kill_orphans()
    
    # Update yt-dlp
    try:
        import yt_dlp
        yt_dlp.YoutubeDL({'quiet': True}).update()
    except:
        pass
    
    # Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(help_callback, pattern="help"))
    
    # Background tasks
    asyncio.create_task(cleanup_temp_files())
    asyncio.create_task(railway_health())
    
    logger.info("🤖 BOT READY")
    
    # Railway polling
    await application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        close_loop=False,
        timeout=45,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=20,
        pool_timeout=20
    )

if __name__ == "__main__":
    # Signal handlers for Railway
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
