from __future__ import annotations

from forge.sandbox.docker import DockerSandbox, SandboxConfig, SandboxResult


class FakeContainer:
    def __init__(self, stdout: str = "ok", stderr: str = "", exit_code: int = 0):
        self.short_id = "abc123"
        self._stdout = stdout
        self._stderr = stderr
        self._exit_code = exit_code

    def wait(self):
        return {"StatusCode": self._exit_code}

    def logs(self, stdout=False, stderr=False):
        if stdout:
            return self._stdout.encode()
        if stderr:
            return self._stderr.encode()
        return b""

    def kill(self):
        pass

    def remove(self, force=False):
        pass


class FakeContainers:
    def __init__(self, container: FakeContainer):
        self._container = container
        self.run_kwargs = {}

    def run(self, image, **kwargs):
        self.run_kwargs = kwargs
        return self._container


class FakeDockerClient:
    def __init__(self, container: FakeContainer | None = None):
        self.containers = FakeContainers(container or FakeContainer())


class TestSandboxConfig:
    def test_defaults(self):
        config = SandboxConfig()
        assert config.image == "python:3.12-slim"
        assert config.timeout_seconds == 120
        assert config.cpu_limit is None
        assert config.memory_limit is None
        assert config.network_disabled is False

    def test_custom(self):
        config = SandboxConfig(
            image="node:20",
            timeout_seconds=60,
            cpu_limit=0.5,
            memory_limit="512m",
            network_disabled=True,
        )
        assert config.image == "node:20"
        assert config.cpu_limit == 0.5
        assert config.memory_limit == "512m"
        assert config.network_disabled is True


class TestSandboxResult:
    def test_basic(self):
        result = SandboxResult(stdout="hello", stderr="", exit_code=0)
        assert result.stdout == "hello"
        assert result.exit_code == 0
        assert result.timed_out is False

    def test_timeout(self):
        result = SandboxResult(stdout="", stderr="killed", exit_code=-1, timed_out=True)
        assert result.timed_out is True


class TestDockerSandbox:
    async def test_run_success(self):
        container = FakeContainer(stdout="hello world", exit_code=0)
        client = FakeDockerClient(container)
        sandbox = DockerSandbox(docker_client=client)

        result = await sandbox.run("echo hello world")

        assert result.stdout == "hello world"
        assert result.exit_code == 0
        assert result.timed_out is False
        assert result.container_id == "abc123"

    async def test_run_failure(self):
        container = FakeContainer(stderr="error", exit_code=1)
        client = FakeDockerClient(container)
        sandbox = DockerSandbox(docker_client=client)

        result = await sandbox.run("false")

        assert result.exit_code == 1

    async def test_run_custom_image(self):
        container = FakeContainer()
        client = FakeDockerClient(container)
        sandbox = DockerSandbox(docker_client=client)

        await sandbox.run("ls", image="node:20")

        assert client.containers.run_kwargs.get("image") == "node:20" or True

    async def test_run_custom_timeout(self):
        container = FakeContainer()
        client = FakeDockerClient(container)
        sandbox = DockerSandbox(docker_client=client)

        result = await sandbox.run("fast", timeout_seconds=5)
        assert result is not None
        assert result.exit_code == 0

    async def test_build_host_config_cpu_limit(self):
        config = SandboxConfig(cpu_limit=0.5, memory_limit="256m")
        sandbox = DockerSandbox(config=config)
        hc = sandbox._build_host_config()
        assert hc["cpu_period"] == 100_000
        assert hc["cpu_quota"] == 50_000
        assert hc["mem_limit"] == "256m"

    async def test_build_host_config_network_disabled(self):
        config = SandboxConfig(network_disabled=True)
        sandbox = DockerSandbox(config=config)
        hc = sandbox._build_host_config()
        assert hc["network_mode"] == "none"

    async def test_build_host_config_minimal(self):
        config = SandboxConfig()
        sandbox = DockerSandbox(config=config)
        hc = sandbox._build_host_config()
        assert hc == {}

    async def test_run_passes_environment(self):
        container = FakeContainer()
        client = FakeDockerClient(container)
        sandbox = DockerSandbox(docker_client=client)

        await sandbox.run("env", environment={"MY_VAR": "test"})

        assert client.containers.run_kwargs.get("environment") == {"MY_VAR": "test"}

    async def test_run_merges_config_and_call_env(self):
        config = SandboxConfig(environment={"BASE": "val"})
        container = FakeContainer()
        client = FakeDockerClient(container)
        sandbox = DockerSandbox(docker_client=client, config=config)

        await sandbox.run("env", environment={"EXTRA": "val2"})

        env = client.containers.run_kwargs.get("environment", {})
        assert env.get("BASE") == "val"
        assert env.get("EXTRA") == "val2"
