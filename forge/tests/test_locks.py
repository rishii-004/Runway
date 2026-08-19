from __future__ import annotations

from forge.runtime.locks import CancelFlag, RateLimiter, RunLock


class FakeRedis:
    def __init__(self):
        self._store: dict[str, str | float] = {}
        self._sorted_sets: dict[str, dict[str, float]] = {}
        self._ttls: dict[str, int] = {}
        self._pipelines: list[_FakePipeline] = []

    async def set(
        self, key: str, value: str, nx: bool = False, ex: int | None = None
    ) -> bool | None:
        if nx and key in self._store:
            return None
        self._store[key] = value
        if ex:
            self._ttls[key] = ex
        return True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
        return count

    async def eval(self, script: str, num_keys: int, *args: str) -> int:
        key = args[0]
        value = args[1] if len(args) > 1 else None
        if "del" in script:
            if self._store.get(key) == value:
                del self._store[key]
                return 1
            return 0
        if "expire" in script:
            if self._store.get(key) == value:
                ttl = int(args[2]) if len(args) > 2 else 300
                self._ttls[key] = ttl
                return 1
            return 0
        return 0

    async def zremrangebyscore(self, key: str, min_val: str, max_val: float) -> int:
        if key not in self._sorted_sets:
            return 0
        sset = self._sorted_sets[key]
        to_remove = [k for k, v in sset.items() if v <= max_val]
        for k in to_remove:
            del sset[k]
        return len(to_remove)

    async def zcard(self, key: str) -> int:
        return len(self._sorted_sets.get(key, {}))

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        if key not in self._sorted_sets:
            self._sorted_sets[key] = {}
        count = 0
        for member, score in mapping.items():
            if member not in self._sorted_sets[key]:
                count += 1
            self._sorted_sets[key][member] = score
        return count

    async def expire(self, key: str, seconds: int) -> bool:
        self._ttls[key] = seconds
        return True

    def pipeline(self) -> _FakePipeline:
        pipe = _FakePipeline(self)
        self._pipelines.append(pipe)
        return pipe


class _FakePipeline:
    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._commands: list[tuple] = []

    def zremrangebyscore(self, key: str, min_val: str, max_val: float):
        self._commands.append(("zremrangebyscore", key, min_val, max_val))
        return self

    def zcard(self, key: str):
        self._commands.append(("zcard", key))
        return self

    def zadd(self, key: str, mapping: dict[str, float]):
        self._commands.append(("zadd", key, mapping))
        return self

    def expire(self, key: str, seconds: int):
        self._commands.append(("expire", key, seconds))
        return self

    async def execute(self) -> list:
        results = []
        for cmd in self._commands:
            op = cmd[0]
            if op == "zremrangebyscore":
                results.append(await self._redis.zremrangebyscore(cmd[1], cmd[2], cmd[3]))
            elif op == "zcard":
                results.append(await self._redis.zcard(cmd[1]))
            elif op == "zadd":
                results.append(await self._redis.zadd(cmd[1], cmd[2]))
            elif op == "expire":
                results.append(await self._redis.expire(cmd[1], cmd[2]))
        self._commands.clear()
        return results


class TestRunLock:
    async def test_acquire_success(self):
        redis = FakeRedis()
        lock = RunLock(redis, "run-123")
        assert await lock.acquire("worker-1") is True
        assert await lock.is_locked() is True

    async def test_acquire_contention(self):
        redis = FakeRedis()
        lock = RunLock(redis, "run-123")
        assert await lock.acquire("worker-1") is True
        assert await lock.acquire("worker-2") is False

    async def test_release_by_owner(self):
        redis = FakeRedis()
        lock = RunLock(redis, "run-123")
        await lock.acquire("worker-1")
        assert await lock.release("worker-1") is True
        assert await lock.is_locked() is False

    async def test_release_by_non_owner(self):
        redis = FakeRedis()
        lock = RunLock(redis, "run-123")
        await lock.acquire("worker-1")
        assert await lock.release("worker-2") is False
        assert await lock.is_locked() is True

    async def test_extend(self):
        redis = FakeRedis()
        lock = RunLock(redis, "run-123", ttl_seconds=60)
        await lock.acquire("worker-1")
        assert await lock.extend("worker-1", 120) is True

    async def test_extend_by_non_owner(self):
        redis = FakeRedis()
        lock = RunLock(redis, "run-123")
        await lock.acquire("worker-1")
        assert await lock.extend("worker-2") is False


class TestRateLimiter:
    async def test_allows_within_limit(self):
        redis = FakeRedis()
        limiter = RateLimiter(redis, "kubectl", rpm=5)
        for _ in range(4):
            assert await limiter.allow() is True

    async def test_blocks_over_limit(self):
        redis = FakeRedis()
        limiter = RateLimiter(redis, "kubectl", rpm=2)
        assert await limiter.allow() is True
        assert await limiter.allow() is True
        assert await limiter.allow() is False

    async def test_tracks_count(self):
        redis = FakeRedis()
        limiter = RateLimiter(redis, "kubectl", rpm=10)
        await limiter.allow()
        await limiter.allow()
        assert await limiter.current_count() == 2


class TestCancelFlag:
    async def test_set_and_check(self):
        redis = FakeRedis()
        flag = CancelFlag(redis, "run-123")
        assert await flag.is_cancelled() is False
        await flag.set_cancel()
        assert await flag.is_cancelled() is True

    async def test_clear(self):
        redis = FakeRedis()
        flag = CancelFlag(redis, "run-123")
        await flag.set_cancel()
        await flag.clear()
        assert await flag.is_cancelled() is False
