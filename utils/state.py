import os
import redis

_redis = None

def r():
    global _redis
    if _redis:
        return _redis
    url = os.getenv("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL missing")
    _redis = redis.Redis.from_url(url, decode_responses=True)
    return _redis

# ── Adult link memory ─────────────────────────
def save_adult(user_id, link):
    r().setex(f"adult:{user_id}", 300, link)

def pop_adult(user_id):
    key = f"adult:{user_id}"
    val = r().get(key)
    if val:
        r().delete(key)
    return val

# ── Premium groups ───────────────────────────
def set_premium(chat_id):
    r().sadd("premium_groups", chat_id)

def is_premium(chat_id):
    return r().sismember("premium_groups", chat_id)

# ── Cancel download ──────────────────────────
def cancel(task_id):
    r().setex(f"cancel:{task_id}", 300, "1")

def cancelled(task_id):
    return r().exists(f"cancel:{task_id}") == 1
