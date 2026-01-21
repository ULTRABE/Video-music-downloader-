import time, os, redis

REDIS_URL = os.getenv("REDIS_URL")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

WINDOW = 30
MAX = 3

def check_rate_limit(user_id: int) -> bool:
    key = f"rate:{user_id}"
    now = int(time.time())

    val = r.get(key)
    if not val:
        r.setex(key, WINDOW, f"1:{now}")
        return True

    count, start = map(int, val.split(":"))

    if now - start > WINDOW:
        r.setex(key, WINDOW, f"1:{now}")
        return True

    if count >= MAX:
        return False

    r.setex(key, WINDOW, f"{count+1}:{start}")
    return True
