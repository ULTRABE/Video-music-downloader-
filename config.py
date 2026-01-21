import os
import tempfile
from pathlib import Path

BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")  # optional, lazy-loaded

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

OWNER_ID = int(os.getenv("OWNER_ID", "7363967303"))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="video_dl_"))

MAX_VIDEO_MB = 45
FREE_QUEUE = 2
PREMIUM_QUEUE = 5
GLOBAL_DOWNLOADS = 2
