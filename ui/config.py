import os, tempfile
from pathlib import Path

BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")

OWNER_ID = 123456789  # YOUR Telegram ID

TEMP_DIR = Path(tempfile.mkdtemp(prefix="vd_"))

MAX_VIDEO_MB = 45
GLOBAL_DOWNLOADS = 2

FREE_QUEUE = 2
PREMIUM_QUEUE = 5
