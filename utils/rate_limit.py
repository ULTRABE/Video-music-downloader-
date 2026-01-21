import time
import asyncio
from collections import defaultdict, deque
from config import USER_COOLDOWN_SECONDS, USER_MAX_QUEUE

_user_last_request = {}
_user_queues = defaultdict(deque)

async def allow_request(user_id: int) -> bool:
    now = time.time()
    last = _user_last_request.get(user_id, 0)

    if now - last < USER_COOLDOWN_SECONDS:
        return False

    if len(_user_queues[user_id]) >= USER_MAX_QUEUE:
        return False

    _user_last_request[user_id] = now
    _user_queues[user_id].append(now)
    return True

def done_request(user_id: int):
    if _user_queues[user_id]:
        _user_queues[user_id].popleft()
