import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, Set
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType, ParseMode

# ---------------- CONFIGURATION ----------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
load_dotenv()

# Bot Configuration
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Paths
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = Client(
    "premium_video_downloader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workers=4
)

# Global State Management
download_queue = asyncio.Queue(maxsize=50)
active_downloads: Dict[int, str] = {}
user_stats: Dict[int, int] = {}
supported_sites = [
    "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "twitter.com", 
    "x.com", "facebook.com", "vimeo.com", "dailymotion.com", "bilibili.com",
    "pinterest.com", "soundcloud.com", "reddit.com", 
]

# ---------------- UTILITY FUNCTIONS ----------------
def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text with regex."""
    url_pattern = r'https?://[^\s<>"]+[^\s\.<>"]*'
    return re.findall(url_pattern, text)

async def cleanup_file(filepath: Path):
    """Safely remove file after delay."""
    await asyncio.sleep(2)
    if filepath.exists():
        filepath.unlink()

def get_progress_msg(chat_id: int, url: str) -> str:
    """Generate download progress message."""
    return f"🔄 **Downloading** from `{url[:50]}...`\n⏳ Please wait..."

def get_success_msg() -> str:
    """Success message template."""
    return "✅ **Download Complete!**\n🎥 Premium Quality Video Delivered!"

# ---------------- PREMIUM FEATURES ----------------
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, msg: Message):
    """Premium welcome message with features."""
    welcome_text = """
🎬 **Premium Video Downloader** 🎬

Download videos from 50+ platforms instantly!
✨ **Features:**
• YouTube, TikTok, Instagram, Twitter & more
• Premium 1080p quality
• Works in Groups & Private
• Auto-pin in groups
• Lightning fast downloads

Just send any video link! 🚀
    """
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Supported Sites", callback_data="sites")],
        [InlineKeyboardButton("⭐ Rate Bot", url="https://t.me/your_bot")]
    ])
    
    await msg.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=buttons,
        disable_web_page_preview=True
    )

@app.on_message(filters.command("start") & filters.group)
async def group_start(_, msg: Message):
    """Group welcome message."""
    await msg.reply_text(
        "🎬 **Premium Video Downloader Active!**\n\n"
        "Send any video link and I'll download it instantly! 🚀",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_callback_query(filters.regex("sites"))
async def sites_callback(_, callback_query):
    """Show supported sites."""
    sites_text = "✅ **Supported Platforms:**\n\n"
    sites_text += " • YouTube • TikTok • Instagram\n"
    sites_text += " • Twitter/X • Facebook • Vimeo\n"
    sites_text += " • Reddit • SoundCloud • 50+ more!"
    
    await callback_query.answer("Supported sites listed!")
    await callback_query.edit_message_text(
        sites_text,
        parse_mode=ParseMode.MARKDOWN
    )

# ---------------- MAIN DOWNLOAD HANDLER ----------------
@app.on_message(
    (filters.private | filters.group) 
    & filters.text 
    & (filters.regex(r"https?://") | filters.regex(r"instagram|twitter|tiktok"))
)
async def handle_media_links(_, msg: Message):
    """Handle all media links in private and groups."""
    urls = extract_urls(msg.text)
    
    if not urls:
        return
        
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    
    # Update user stats
    user_stats[user_id] = user_stats.get(user_id, 0) + 1
    
    # Delete original message in groups
    if msg.chat.type != ChatType.PRIVATE:
        try:
            await msg.delete()
        except:
            pass
    
    # Add to queue with status message
    status_msg = await msg.reply_text(
        f"🚀 **Queued:** {len(urls)} link(s)\n⏳ Position: Processing...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    for i, url in enumerate(urls[:3]):  # Limit to 3 URLs per message
        await download_queue.put((chat_id, url, user_id, status_msg.message_id))
        
        # Update status for multiple URLs
        if len(urls) > 1:
            await status_msg.edit_text(
                f"🚀 **Queued:** {len(urls)} links\n"
                f"📥 Processing {i+1}/{len(urls)}...",
                parse_mode=ParseMode.MARKDOWN
            )

# ---------------- ADVANCED DOWNLOAD WORKER ----------------
async def download_worker():
    """Enhanced worker with progress tracking and quality optimization."""
    while True:
        try:
            chat_id, url, user_id, status_msg_id = await download_queue.get()
            
            # Skip if already downloading
            if user_id in active_downloads:
                download_queue.task_done()
                continue
                
            active_downloads[user_id] = url
            output_path = DOWNLOAD_DIR / f"video_{user_id}_{asyncio.get_event_loop().time():.0f}.mp4"
            
            try:
                # Send progress message
                progress_msg = await app.send_message(
                    chat_id, 
                    get_progress_msg(chat_id, url),
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Advanced yt-dlp command with premium settings
                yt_dlp_cmd = [
                    "yt-dlp",
                    "-f", "best[ext=mp4][height<=1080]/best[height<=1080]/best",
                    "--merge-output-format", "mp4",
                    "--embed-subs", "--embed-metadata",
                    "-o", str(output_path),
                    "--no-playlist",  # Single video only
                    url
                ]
                
                proc = await asyncio.create_subprocess_exec(
                    *yt_dlp_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                if output_path.exists() and output_path.stat().st_size > 1024:
                    # Send video with premium settings
                    sent_msg = await app.send_video(
                        chat_id,
                        output_path,
                        supports_streaming=True,
                        caption=get_success_msg(),
                        parse_mode=ParseMode.MARKDOWN,
                        progress=progress_callback
                    )
                    
                    # Pin in groups
                    if chat_id < 0:  # Group chat
                        try:
                            await app.pin_chat_message(chat_id, sent_msg.id)
                        except:
                            pass
                            
                else:
                    await progress_msg.edit_text(
                        "❌ **Download failed.**\nTry another link!",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
            finally:
                # Cleanup
                if output_path.exists():
                    asyncio.create_task(cleanup_file(output_path))
                    
                active_downloads.pop(user_id, None)
                download_queue.task_done()
                
        except Exception as e:
            logging.error(f"Download error: {e}")
            download_queue.task_done()

async def progress_callback(current: int, total: int):
    """Streaming progress callback."""
    percent = (current / total) * 100
    print(f"Progress: {percent:.1f}%")

# ---------------- STATS & HELP ----------------
@app.on_message(filters.command("stats") & filters.private)
async def stats_cmd(_, msg: Message):
    """User statistics."""
    downloads = user_stats.get(msg.from_user.id, 0)
    await msg.reply_text(
        f"📊 **Your Stats:**\n"
        f"Downloads: `{downloads}`\n"
        f"Active: {'✅' if msg.from_user.id in active_downloads else '❌'}",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command("help"))
async def help_cmd(_, msg: Message):
    """Help command."""
    await msg.reply_text(
        "🔥 **Just send any video link!**\n\n"
        "Supported: YouTube, TikTok, Instagram, Twitter, Facebook & 50+ sites\n"
        "Quality: Up to 1080p • Fast • Reliable",
        parse_mode=ParseMode.MARKDOWN
    )

# ---------------- MAIN EXECUTION ----------------
async def main():
    """Initialize and start all workers."""
    await app.start()
    print("🚀 Premium Video Downloader Started!")
    
    # Start multiple workers for speed
    workers = [asyncio.create_task(download_worker()) for _ in range(4)]
    
    # Graceful idle
    await idle()
    
    # Cleanup on stop
    for worker in workers:
        worker.cancel()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
