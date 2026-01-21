import os
from pathlib import Path
import tempfile

BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN environment variable is required")

if not REDIS_URL:
    raise RuntimeError("❌ REDIS_URL environment variable is required")

# Create temp dir
TEMP_DIR = Path(tempfile.mkdtemp(prefix="video_dl_"))
TEMP_DIR.mkdir(exist_ok=True)

MAX_VIDEO_MB = 45
ADULT_TTL = 60
# GLOBAL_DOWNLOADS removed (unused dead code)
