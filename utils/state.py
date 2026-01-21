import os
import redis
from redis.exceptions import ConnectionError

REDIS_URL = os.getenv("REDIS_URL")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)

def _adult(u): return f"adult:{u}"
def _premium(c): return f"premium:{c}"
def _cancel(t): return f"cancel:{t}"

def save_adult(u, url): 
    r.setex(_adult(u), 300, url)

def pop_adult(u):
    v = r.get(_adult(u))
    if v: 
        r.delete(_adult(u))
    return v

def set_premium(c): 
    r.setex(_premium(c), 86400*30, "1")  # 30 days

def is_premium_group(c): 
    return r.exists(_premium(c)) == 1

def cancel(t): 
    r.setex(_cancel(t), 600, "1")

def is_cancelled(t): 
    return r.exists(_cancel(t)) == 1

def clear_cancel(t): 
    r.delete(_cancel(t))
