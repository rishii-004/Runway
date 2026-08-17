from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class RetryConfig:
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        timeout_seconds: float | None = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.timeout_seconds = timeout_seconds

    def delay_for_attempt(self, attempt: int) -> float:
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay)


async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> Any:
    config = config or RetryConfig()
    last_error: Exception | None = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            if config.timeout_seconds:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=config.timeout_seconds,
                )
            else:
                result = await func(*args, **kwargs)
            return result
        except asyncio.TimeoutError as e:
            last_error = e
            logger.warning(
                "retry_timeout",
                attempt=attempt,
                max_attempts=config.max_attempts,
                timeout=config.timeout_seconds,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "retry_error",
                attempt=attempt,
                max_attempts=config.max_attempts,
                error=str(e),
            )

        if attempt < config.max_attempts:
            delay = config.delay_for_attempt(attempt)
            logger.info("retry_waiting", attempt=attempt, delay=delay)
            await asyncio.sleep(delay)

    raise last_error  # type: ignore[misc]
