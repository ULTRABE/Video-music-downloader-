import time
import os
import redis

REDIS_URL = os.getenv("REDIS_URL")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# ── CONFIG ──────────────────────────────────────────
WINDOW_SECONDS = 30      # time window
MAX_REQUESTS = 3         # max requests per window

def _key(user_id: int) -> str:
    return f"rate:{user_id}"

def check_rate_limit(user_id: int) -> bool:
    """
    Returns True if user is allowed.
    Returns False if rate-limited.
    """
    key = _key(user_id)
    now = int(time.time())

    data = r.get(key)
    if not data:
        # First request
        r.setex(key, WINDOW_SECONDS, f"1:{now}")
        return True

    count, start = map(int, data.split(":"))

    # Window expired
    if now - start >= WINDOW_SECONDS:
        r.setex(key, WINDOW_SECONDS, f"1:{now}")
        return True

    # Too many requests
    if count >= MAX_REQUESTS:
        return False

    # Increment
    r.setex(key, WINDOW_SECONDS, f"{count + 1}:{start}")
    return True
