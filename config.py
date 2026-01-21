import os
import tempfile
from pathlib import Path

# ── ENV ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is missing")

# ── OWNER / ADMIN ───────────────────────────────────
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # set in env

# ── TEMP STORAGE ────────────────────────────────────
TEMP_DIR = Path(tempfile.mkdtemp(prefix="video_dl_"))

# ── SIZE LIMITS ─────────────────────────────────────
MAX_VIDEO_MB = 45  # Telegram video limit

# ── ADULT CONTENT TTL (PRIVATE ONLY) ─────────────────
ADULT_TTL = 60  # seconds (1 minute auto-delete)

# ── CONCURRENCY ─────────────────────────────────────
GLOBAL_DOWNLOADS = 2
