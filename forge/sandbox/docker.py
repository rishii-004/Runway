from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    container_id: str | None = None


@dataclass
class SandboxConfig:
    image: str = "python:3.12-slim"
    timeout_seconds: int = 120
    cpu_limit: float | None = None
    memory_limit: str | None = None
    network_disabled: bool = False
    working_dir: str = "/workspace"
    environment: dict[str, str] = field(default_factory=dict)


class DockerSandbox:
    def __init__(self, docker_client: Any | None = None, config: SandboxConfig | None = None):
        self._client = docker_client
        self._config = config or SandboxConfig()

    def _get_client(self):
        if self._client is not None:
            return self._client
        import docker

        return docker.from_env()

    def _build_host_config(self) -> dict:
        hc: dict[str, Any] = {}
        if self._config.cpu_limit is not None:
            hc["cpu_period"] = 100_000
            hc["cpu_quota"] = int(self._config.cpu_limit * 100_000)
        if self._config.memory_limit is not None:
            hc["mem_limit"] = self._config.memory_limit
        if self._config.network_disabled:
            hc["network_mode"] = "none"
        return hc

    async def run(
        self,
        command: str | list[str],
        *,
        image: str | None = None,
        timeout_seconds: int | None = None,
        environment: dict[str, str] | None = None,
        volumes: dict[str, dict[str, str]] | None = None,
    ) -> SandboxResult:
        effective_image = image or self._config.image
        effective_timeout = timeout_seconds or self._config.timeout_seconds
        effective_env = {**self._config.environment, **(environment or {})}

        logger.info(
            "sandbox_run_start",
            image=effective_image,
            timeout=effective_timeout,
        )

        client = self._get_client()
        host_config = self._build_host_config()

        container = await asyncio.to_thread(
            client.containers.run,
            effective_image,
            command=command,
            detach=True,
            stdout=True,
            stderr=True,
            environment=effective_env if effective_env else None,
            working_dir=self._config.working_dir,
            volumes=volumes,
            **host_config,
        )

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(container.wait),
                timeout=effective_timeout,
            )
            exit_code = result.get("StatusCode", -1)
            timed_out = False
        except TimeoutError:
            logger.warning("sandbox_timeout", container_id=container.short_id)
            await asyncio.to_thread(container.kill)
            exit_code = -1
            timed_out = True

        stdout = await asyncio.to_thread(
            lambda: container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        )
        stderr = await asyncio.to_thread(
            lambda: container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        )

        with contextlib.suppress(Exception):
            await asyncio.to_thread(container.remove, force=True)

        logger.info(
            "sandbox_run_complete",
            container_id=container.short_id,
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_len=len(stdout),
            stderr_len=len(stderr),
        )

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            timed_out=timed_out,
            container_id=container.short_id,
        )
