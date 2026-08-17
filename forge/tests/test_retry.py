import asyncio

import pytest

from forge.runtime.retry import RetryConfig, retry_with_backoff


async def test_retry_succeeds_first_try():
    call_count = 0

    async def success():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await retry_with_backoff(success)
    assert result == "ok"
    assert call_count == 1


async def test_retry_succeeds_after_failures():
    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("fail")
        return "ok"

    config = RetryConfig(max_attempts=5, base_delay=0.01)
    result = await retry_with_backoff(flaky, config=config)
    assert result == "ok"
    assert call_count == 3


async def test_retry_exhausted():
    call_count = 0

    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise ValueError("always fails")

    config = RetryConfig(max_attempts=3, base_delay=0.01)
    with pytest.raises(ValueError, match="always fails"):
        await retry_with_backoff(always_fail, config=config)
    assert call_count == 3


async def test_retry_timeout():
    async def slow():
        await asyncio.sleep(10)
        return "ok"

    config = RetryConfig(max_attempts=2, base_delay=0.01, timeout_seconds=0.05)
    with pytest.raises(asyncio.TimeoutError):
        await retry_with_backoff(slow, config=config)


async def test_retry_delay_increases():
    config = RetryConfig(max_attempts=3, base_delay=0.1, backoff_factor=2.0)
    assert config.delay_for_attempt(1) == 0.1
    assert config.delay_for_attempt(2) == 0.2
    assert config.delay_for_attempt(3) == 0.4


async def test_retry_delay_capped():
    config = RetryConfig(max_attempts=10, base_delay=1.0, max_delay=5.0, backoff_factor=3.0)
    assert config.delay_for_attempt(1) == 1.0
    assert config.delay_for_attempt(2) == 3.0
    assert config.delay_for_attempt(3) == 5.0
    assert config.delay_for_attempt(4) == 5.0
