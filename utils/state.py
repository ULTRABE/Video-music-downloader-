import os
import redis

REDIS_URL = os.getenv("REDIS_URL")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# ── KEYS ────────────────────────────────────────────
def _adult_key(user_id): 
    return f"adult:{user_id}"

def _premium_key(chat_id): 
    return f"premium:{chat_id}"

def _cancel_key(task_id):
    return f"cancel:{task_id}"

# ── ADULT LINK MEMORY ───────────────────────────────
def save_adult(user_id: int, url: str):
    r.setex(_adult_key(user_id), 300, url)  # 5 min memory

def pop_adult(user_id: int):
    key = _adult_key(user_id)
    url = r.get(key)
    if url:
        r.delete(key)
    return url

# ── PREMIUM GROUPS ──────────────────────────────────
def set_premium(chat_id: int):
    r.set(_premium_key(chat_id), "1")

def is_premium_group(chat_id: int) -> bool:
    return r.exists(_premium_key(chat_id)) == 1

# ── CANCEL DOWNLOAD SUPPORT ─────────────────────────
def mark_cancelled(task_id: str):
    r.setex(_cancel_key(task_id), 600, "1")

def is_cancelled(task_id: str) -> bool:
    return r.exists(_cancel_key(task_id)) == 1

def clear_cancel(task_id: str):
    r.delete(_cancel_key(task_id))
