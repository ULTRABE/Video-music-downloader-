import os
import redis

_redis = None

def get_redis():
    global _redis
    if _redis:
        return _redis

    url = os.getenv("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL not set")

    _redis = redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5
    )
    return _redis


def save_adult_link(user_id: int, link: str):
    r = get_redis()
    r.setex(f"adult:{user_id}", 300, link)


def get_adult_link(user_id: int):
    r = get_redis()
    return r.get(f"adult:{user_id}")


def set_premium_group(chat_id: int):
    r = get_redis()
    r.sadd("premium_groups", chat_id)


def is_premium_group(chat_id: int) -> bool:
    r = get_redis()
    return r.sismember("premium_groups", chat_id)
