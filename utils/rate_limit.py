import time
import redis
import os

r = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

def allow_request(user_id: int, limit: int) -> bool:
    """
    Returns True if user is allowed to start a new download
    """
    key = f"queue:{user_id}"
    if r.llen(key) >= limit:
        return False

    r.rpush(key, time.time())
    r.expire(key, 180)
    return True

def done_request(user_id: int):
    """
    Removes one active job from user's queue
    """
    r.lpop(f"queue:{user_id}")
