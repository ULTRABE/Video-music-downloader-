import redis, os

r = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

def save_adult_link(user_id, url):
    r.setex(f"adult:{user_id}", 300, url)

def get_adult_link(user_id):
    return r.get(f"adult:{user_id}")

def set_premium_group(chat_id):
    r.set(f"premium_gc:{chat_id}", 1)

def is_premium_group(chat_id):
    return r.exists(f"premium_gc:{chat_id}")
