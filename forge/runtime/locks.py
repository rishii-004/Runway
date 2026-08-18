from __future__ import annotations

import time
from typing import Any

import structlog

logger = structlog.get_logger()


class RunLock:
    def __init__(self, redis_client: Any, run_id: str, ttl_seconds: int = 300):
        self._redis = redis_client
        self._key = f"forge:run_lock:{run_id}"
        self._ttl = ttl_seconds
        self._acquired = False

    async def acquire(self, worker_id: str) -> bool:
        result = await self._redis.set(
            self._key, worker_id, nx=True, ex=self._ttl
        )
        self._acquired = result is True
        if self._acquired:
            logger.info("run_lock_acquired", run_id=self._key.split(":")[-1], worker=worker_id)
        else:
            logger.debug("run_lock_contention", run_id=self._key.split(":")[-1], worker=worker_id)
        return self._acquired

    async def release(self, worker_id: str) -> bool:
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self._redis.eval(script, 1, self._key, worker_id)
        released = result == 1
        if released:
            logger.info("run_lock_released", run_id=self._key.split(":")[-1], worker=worker_id)
        return released

    async def is_locked(self) -> bool:
        return await self._redis.exists(self._key) > 0

    async def extend(self, worker_id: str, additional_seconds: int | None = None) -> bool:
        ttl = additional_seconds or self._ttl
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = await self._redis.eval(script, 1, self._key, worker_id, ttl)
        return result == 1


class RateLimiter:
    def __init__(self, redis_client: Any, tool_name: str, rpm: int, window_seconds: int = 60):
        self._redis = redis_client
        self._key = f"forge:rate_limit:{tool_name}"
        self._rpm = rpm
        self._window = window_seconds

    async def allow(self) -> bool:
        now = time.time()
        window_start = now - self._window

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(self._key, "-inf", window_start)
        pipe.zcard(self._key)
        pipe.zadd(self._key, {str(now): now})
        pipe.expire(self._key, self._window)
        results = await pipe.execute()

        current_count = results[1]
        return current_count < self._rpm

    async def current_count(self) -> int:
        now = time.time()
        window_start = now - self._window
        await self._redis.zremrangebyscore(self._key, "-inf", window_start)
        return await self._redis.zcard(self._key)


class CancelFlag:
    def __init__(self, redis_client: Any, run_id: str):
        self._redis = redis_client
        self._key = f"forge:cancel:{run_id}"

    async def set_cancel(self) -> None:
        await self._redis.set(self._key, "1", ex=3600)

    async def is_cancelled(self) -> bool:
        return await self._redis.exists(self._key) > 0

    async def clear(self) -> None:
        await self._redis.delete(self._key)
