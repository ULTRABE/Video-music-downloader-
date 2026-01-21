import os
import tempfile
from pathlib import Path

# ── ENV ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")  # lazy-loaded later

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

# ── OWNER / ADMIN ───────────────────────────────────
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))  # replace later

# ── TEMP STORAGE ────────────────────────────────────
TEMP_DIR = Path(tempfile.mkdtemp(prefix="video_dl_"))

# ── LIMITS ──────────────────────────────────────────
MAX_VIDEO_MB = 45
GLOBAL_DOWNLOADS = 2

# ── QUEUES ──────────────────────────────────────────
FREE_QUEUE = 2
PREMIUM_QUEUE = 5
