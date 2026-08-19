# Forge — Build Roadmap

This roadmap turns [prd.md](prd.md) into an ordered, checkable task list. It is meant to
be executed **top to bottom, one task at a time**, by a coding agent (opencode) or a human.

## How to use this file

- Work in order. Later tasks assume earlier ones exist (e.g. you cannot build the worker
  before the DB models it persists to).
- Each task lists the files it touches and a **Verify** step. Do not check a task off until
  Verify passes.
- Commit after each completed task (small, reviewable diffs).
- Local infrastructure (Postgres/RabbitMQ/Redis/Grafana/Prometheus) is brought up with
  `docker-compose.yml`, but the **actual runtime target for testing is Podman**, not Docker.
  Read the [Podman Notes](#podman-notes) section before Phase 0 — it changes a couple of
  design choices (mainly the sandbox module) so you don't have to retrofit them later.
- Phase numbers match `prd.md` §20. Phase 0 (scaffolding) is not in the PRD but has to exist
  before Phase 1 can start.

---

## Podman Notes

Read once, apply throughout:

1. **macOS needs a VM.** Podman is daemonless and on macOS needs a lightweight VM:
   `podman machine init && podman machine start` before anything else.
2. **Compose.** Use `podman compose up -d` (native in Podman ≥4.7) or install
   `podman-compose` as a fallback. Keep `docker-compose.yml` vanilla — no Docker-only
   extensions (e.g. avoid `platform:` quirks, use standard `healthcheck:` blocks) — so it
   runs unmodified under either engine.
3. **Sandbox module must not hardcode Docker.** `sandbox/docker.py` (Phase 3) should use the
   `docker` Python SDK configured from a `DOCKER_HOST` env var, never a hardcoded socket path.
   Podman exposes a Docker-API-compatible socket, so pointing `DOCKER_HOST` at it (e.g.
   `unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}')` on
   macOS, or `unix:///run/user/$(id -u)/podman/podman.sock` on rootless Linux) makes the same
   code work against either engine with zero branching logic.
4. **Testcontainers.** Point it at the same socket via `DOCKER_HOST` (or
   `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE`) so `pytest` + Testcontainers integration tests
   run against Podman too.
5. **Volumes.** On rootless Linux, bind mounts may need `:Z`/`:z` SELinux labels in
   `docker-compose.yml`. No-op on macOS, but add them anyway for portability.
6. **Definition of Done in the PRD says `docker compose up`.** Treat that as
   `podman compose up` for this project — same file, different engine.

---

## Phase 0 — Project Scaffolding

- [x] **0.1 Repo layout.** Create the directory tree from `prd.md` §19 as empty packages
  (`__init__.py` in each) under `forge/`: `api/{routes,schemas}`, `runtime/`, `agents/`,
  `tools/`, `policy/`, `budgets/`, `checkpoints/`, `messaging/`, `workers/`, `sandbox/`,
  `events/`, `evaluation/`, `observability/`, `storage/`, `tests/`.
  **Verify:** `python -c "import forge"` succeeds (add root `forge/__init__.py`).

- [x] **0.2 Dependency management.** `pyproject.toml` targeting Python 3.12+, with
  `fastapi`, `pydantic`, `pydantic-settings`, `langgraph`, `langchain-core`, `sqlalchemy`,
  `alembic`, `asyncpg`, `aio-pika` (RabbitMQ), `redis`, `docker` (SDK), `opentelemetry-sdk`,
  `opentelemetry-exporter-otlp`, `prometheus-client`, `structlog`, dev deps `pytest`,
  `pytest-asyncio`, `testcontainers`, `ruff`, `mypy`.
  **Verify:** `uv sync` (or `pip install -e ".[dev]"`) completes cleanly.

- [x] **0.3 Settings & config.** `forge/config.py` — a `pydantic-settings` `Settings` class
  reading `DATABASE_URL`, `RABBITMQ_URL`, `REDIS_URL`, `DOCKER_HOST`, `OTEL_EXPORTER_OTLP_ENDPOINT`
  from env, with a `.env.example` documenting each.
  **Verify:** `Settings()` loads with only `.env.example` values copied to `.env`.

- [x] **0.4 Local infra.** `docker-compose.yml` with `postgres:16`, `rabbitmq:3-management`,
  `redis:7`, each with a healthcheck and a named volume. Add `prometheus` and `grafana`
  services now (config wired later in Phase 3) so the compose file doesn't churn.
  **Verify:** `podman compose up -d postgres rabbitmq redis` — all three report healthy.

- [x] **0.5 Structured logging.** `forge/observability/logging.py` — `structlog` JSON
  logging setup, called once at process start in both the API and worker entrypoints.
  **Verify:** running the (stub) API logs one JSON line to stdout.

- [x] **0.6 Lint/test baseline.** `ruff` config in `pyproject.toml`, `pytest.ini`/`[tool.pytest.ini_options]`
  with `asyncio_mode = "auto"`, empty `tests/conftest.py`.
  **Verify:** `ruff check .` and `pytest` both run (0 tests, 0 errors) cleanly.

---

## Phase 1 — Core Runtime

Goal (PRD success criterion): *kill a worker mid-run and have another worker resume it from
persisted state.*

- [x] **1.1 DB models.** `forge/storage/models.py` (SQLAlchemy 2.0 declarative) for
  `agents`, `runs`, `run_steps`, `checkpoints`, `tool_calls`, `approvals`, `budgets`,
  `execution_events`, `evaluations`, `evaluation_results` per PRD §7.3. Minimal columns for
  now (id, fk's, status, timestamps, jsonb payload column) — widen later phases as needed
  rather than guessing every column up front.
  **Verify:** `alembic revision --autogenerate` produces a non-empty migration; `alembic upgrade head`
  against the compose Postgres succeeds.

- [x] **1.2 Pydantic schemas.** `forge/api/schemas/` — request/response models for `Agent`
  and `Run` (matching the run lifecycle fields in PRD §7.1: `run_id, agent_id, task, status,
  current_node, iteration, started_at, completed_at`).
  **Verify:** schemas round-trip through `model_dump()`/`model_validate()` in a unit test.

- [x] **1.3 FastAPI skeleton.** `forge/api/main.py` with a `GET /health` route, DB session
  dependency, and app lifespan that opens/closes the async engine.
  **Verify:** `uvicorn forge.api.main:app` boots; `curl localhost:8000/health` → 200.

- [x] **1.4 LangGraph adapter.** `forge/agents/langgraph_adapter.py` — wraps a compiled
  LangGraph graph so the runtime can step through it node-by-node and read intermediate
  state after each node (not just invoke end-to-end). Add one trivial demo graph
  (`forge/agents/demo_echo_agent.py`, 2-3 nodes) purely to exercise the adapter in tests —
  this is scaffolding, not one of the Phase 5 demo agents.
  **Verify:** unit test drives the demo graph through the adapter and asserts state after
  each step.

- [x] **1.5 Checkpoint persistence.** `forge/checkpoints/postgres.py` — a LangGraph
  `BaseCheckpointSaver` implementation backed by the `checkpoints`/`run_steps` tables.
  **Verify:** unit test: save a checkpoint, reload it in a fresh saver instance, state matches.

- [x] **1.6 Messaging layer.** `forge/messaging/messages.py` (Pydantic message schemas:
  `run.requested`, `run.resume`) and `forge/messaging/rabbitmq.py` (connection, publish,
  consume via `aio-pika`, with manual ack).
  **Verify:** integration test — publish a `run.requested`, consume it back, ack, queue is empty.

- [x] **1.7 Runtime lifecycle & executor.** `forge/runtime/lifecycle.py` (state machine:
  `QUEUED → RUNNING → WAITING_FOR_APPROVAL → RUNNING → COMPLETED`, plus terminal
  `FAILED/CANCELLED/TIMEOUT/BUDGET_EXCEEDED`, with a table of legal transitions) and
  `forge/runtime/executor.py` (drives the LangGraph adapter one step at a time, persisting a
  checkpoint via 1.5 after every step, updating `runs.status`/`current_node`/`iteration`).
  **Verify:** unit test runs the demo agent through the executor to completion; DB row
  ends in `COMPLETED` with the right `iteration` count.

- [x] **1.8 Basic retry/timeout.** Wrap LLM/tool invocation points in the executor with a
  small retry helper (exponential backoff, max attempts, per-call timeout) — configurable,
  not hardcoded (PRD §11). No policy engine yet; this is just resilience plumbing.
  **Verify:** unit test with a flaky stub tool (fails twice, succeeds 3rd try) completes
  without manual intervention; a stub that never succeeds ends the run `FAILED`.

- [x] **1.9 Scheduler & worker process.** `forge/runtime/scheduler.py` (enqueues
  `run.requested` when a run is submitted) and `forge/workers/worker.py` (long-running
  process: consumes `run.requested`/`run.resume`, calls the executor, acks on
  checkpoint-or-completion).
  **Verify:** start one worker process, submit a run via a script, observe it complete and
  the message get acked (queue depth returns to 0).

- [x] **1.10 Recovery.** `forge/runtime/recovery.py` — on worker startup, and on message
  redelivery, load the latest checkpoint for the run and resume instead of restarting from
  node 0.
  **Verify (this is the Phase 1 exit criterion):** integration test — start a worker, submit
  a multi-step demo run, `SIGKILL` the worker process mid-run after step 3 of ~6, start a new
  worker, assert the run completes and steps 1-3 are not re-executed (assert via a counter/spy
  in the demo agent's nodes, not just wall-clock).

- [x] **1.11 Minimal API surface.** `POST /agents`, `GET /agents/{id}`, `POST /runs`,
  `GET /runs/{id}`, `POST /runs/{id}/cancel` (cancel just flips a DB flag for now; the
  executor doesn't check it yet — that's Phase 2).
  **Verify:** end-to-end script: register agent → submit run → poll status → COMPLETED.

---

## Phase 2 — Runtime Controls

Goal: *an agent cannot execute a restricted tool without satisfying Forge's policy.*

- [x] **2.1 Tool registry.** `forge/tools/models.py` (`ToolSpec`: name, risk, requires_approval,
  timeout_seconds) and `forge/tools/registry.py` (loads tool specs from YAML, exposes
  `get(name) -> ToolSpec`).
  **Verify:** unit test loads a sample YAML registry and resolves a known/unknown tool name.

- [x] **2.2 Policy engine.** `forge/policy/rules.py` (rule definitions) and
  `forge/policy/engine.py` (`evaluate(tool_spec, run, context) -> ALLOW|DENY|REQUIRE_APPROVAL`),
  with a "production" policy profile as the first concrete ruleset (PRD §9).
  **Verify:** unit tests for each decision branch (low-risk → ALLOW, high-risk → REQUIRE_APPROVAL,
  explicitly blocked tool → DENY).

- [x] **2.3 Tool gateway (executor).** `forge/tools/executor.py` — the **only** code path
  that may invoke a real tool. Looks up the `ToolSpec`, asks the policy engine, then either
  executes, raises a structured permission error, or signals approval-needed. Wire the
  executor from 1.7 to call tools only through this gateway — no direct calls anywhere else.
  **Verify:** unit test asserts a DENY decision never reaches the underlying tool function
  (mock it and assert `not called`).

- [x] **2.4 Budgets.** `forge/budgets/manager.py` — tracks steps/tokens/cost/runtime per run
  against the `budgets` table, exposes `check()` (raises/returns exceeded) and `record_usage()`.
  Wire into the executor: check before each step, record after.
  **Verify:** unit test with `max_steps=2` on a 5-step demo agent ends the run
  `BUDGET_EXCEEDED` after step 2, not step 5.

- [x] **2.5 Redis coordination.** `forge/runtime/locks.py` (or extend `executor.py`) —
  Redis-based lock so only one worker claims a given run at a time (prevents double-execution
  on redelivery), plus a simple rate limiter for tool calls if the registry marks a tool
  rate-limited.
  **Verify:** integration test — two workers race to claim the same run_id; exactly one wins.

- [x] **2.6 Cancellation (real).** Executor checks a Redis/DB cancel flag between steps and
  halts to `CANCELLED` (upgrades the stub from 1.11).
  **Verify:** submit a long-running demo run, call `POST /runs/{id}/cancel` mid-execution,
  assert it stops within one step and status is `CANCELLED`.

- [x] **2.7 Human approval.** `approvals` table wiring, `POST /runs/{id}/approve` and
  `POST /runs/{id}/deny`. On `REQUIRE_APPROVAL` from the policy engine, executor persists
  checkpoint, sets `WAITING_FOR_APPROVAL`, and returns — **the worker process exits/moves on,
  it does not block** (PRD §12). Approval publishes `run.resume` to pick it back up.
  **Verify:** integration test — demo agent calls a `requires_approval: true` tool, run
  reaches `WAITING_FOR_APPROVAL`, worker is free to process other runs, `POST .../approve`
  causes a (possibly different) worker to resume and complete the run.

- [x] **2.8 Phase exit test.** Add a demo tool marked `risk: high, requires_approval: true`
  with no approval granted → run must reach `WAITING_FOR_APPROVAL` and the tool function
  itself must never execute; granting approval must let it execute exactly once.

---

## Phase 3 — Sandbox & Observability

Goal: *inspect an entire run — LLM calls, tools, latency, failures, resource usage.*

- [x] **3.1 Sandbox manager.** `forge/sandbox/docker.py` — runs a command in a container via
  the `docker` SDK against `settings.DOCKER_HOST` (see Podman Notes above — do not hardcode
  a socket path). Support CPU limit, memory limit, timeout, no-network option, and
  filesystem isolation (fresh container per call, no host mounts by default).
  **Verify:** unit/integration test runs `pytest` inside a sandboxed container against a
  tiny fixture repo, captures stdout/stderr/exit code, and enforces a timeout (kill a
  container that runs `sleep 999`).

- [x] **3.2 Wire sandbox into tool gateway.** Tools flagged `sandbox: true` in the registry
  execute via 3.1 instead of in-process (PRD §13 example: `run_tests()`).
  **Verify:** existing tool-gateway tests still pass; a new sandboxed tool's actual `exec`
  happens inside a container (assert via a marker file only writable inside the container).

- [x] **3.3 Execution events.** `forge/events/publisher.py` — every meaningful runtime
  transition (step start/end, tool call, policy decision, budget check, approval) writes a
  row to `execution_events`.
  **Verify:** run the demo agent once, query `execution_events` for that run_id, assert the
  sequence matches what actually happened (step-by-step).

- [x] **3.4 OpenTelemetry.** `forge/observability/tracing.py` — spans for
  `run → node → llm call → tool call → db operation → sandbox execution` (PRD §14), OTLP
  exporter configured from `OTEL_EXPORTER_OTLP_ENDPOINT`.
  **Verify:** run the demo agent with a console/OTLP exporter, confirm a single trace
  contains nested spans for at least one LLM call, one tool call, and one DB write.

- [x] **3.5 Prometheus metrics.** Instrument executor/worker/tool-gateway with the counters
  from PRD §14 (`agent_runs_total`, `agent_run_duration`, `tool_latency`, `llm_latency`,
  `queue_depth`, `worker_utilization`, `retry_count`, `failure_rate`, `token_usage`,
  `estimated_cost`); expose `GET /metrics`.
  **Verify:** `curl localhost:8000/metrics` after a run shows non-zero values for each metric.

- [x] **3.6 Grafana provisioning.** Compose-mounted `grafana/provisioning/` with a
  Prometheus datasource and one dashboard covering: active runs, queue depth, worker health,
  latency, failures, token usage, cost, tool performance (PRD §14).
  **Verify:** `podman compose up -d prometheus grafana`, open Grafana, dashboard renders
  live data from a run you just executed.

---

## Phase 4 — Evaluation & Replay

Goal: *run two agent versions against the same dataset and quantitatively compare them.*

- [ ] **4.1 History endpoints.** `GET /runs/{id}/events`, `GET /runs/{id}/trace` — surface
  what 3.3/3.4 already persist.
  **Verify:** both endpoints return the events/trace for a completed demo run.

- [ ] **4.2 Replay/resume.** `POST /runs/{id}/replay` — reconstruct a run's state from its
  checkpoints and re-execute (initially: replay from the latest checkpoint; note
  "replay from checkpoint N with a different model/config" as a stretch/follow-up, don't
  block the phase on it).
  **Verify:** replay of a completed run produces an equivalent execution trail.

- [ ] **4.3 Evaluation runner.** `forge/evaluation/runner.py` — loads a `tasks.jsonl`
  dataset, submits one run per task against a given agent version through the existing
  runtime (no separate execution path), waits for completion.
  `forge/evaluation/metrics.py` — aggregates success rate, tool accuracy, latency, tokens,
  cost, failure rate across the batch.
  **Verify:** run a 5-task dataset against the demo agent, get an aggregated metrics object
  back with sane values.

- [ ] **4.4 Evaluation persistence & API.** `evaluations`/`evaluation_results` tables wired,
  `POST /evaluations`, `GET /evaluations/{id}`.
  **Verify:** submit two evaluations (e.g. demo agent with two different budgets standing in
  for "v1"/"v2"), fetch both, diff their metrics — matches the comparison-table shape in
  PRD §16.

---

## Phase 5 — Demonstration Agents

Goal: prove the harness on real(ish) agents. These are consumers of Forge, not part of Forge
itself — put them under `forge/agents/` alongside the demo echo agent, each with its own
tool registrations and a small eval dataset.

- [ ] **5.1 Code Review Agent.** Graph: analyze PR → find issues → generate patch → run
  tests (via sandbox, 3.1) → verify. Tools: repo read, patch apply, sandboxed `pytest`.
  **Verify:** point it at a small fixture repo with one seeded bug; it produces a patch and
  a passing sandboxed test run.

- [ ] **5.2 Incident RCA Agent.** Graph: alert → metrics → logs → traces → hypothesis →
  verification → optional remediation (remediation tool marked `requires_approval: true`,
  exercising Phase 2's HITL path for real).
  **Verify:** feed a synthetic alert + canned metrics/logs/traces fixtures; agent reaches a
  hypothesis and, if remediation is attempted, actually pauses for approval.

- [ ] **5.3 (Optional/stretch) Data Pipeline RCA Agent.** Only if time remains — same
  pattern as 5.2 applied to pipeline/storage/DB evidence correlation. Do not let this block
  calling v1 done; PRD §20 already frames it as 2-3 demo agents, not a hard 3.

---

## Final Validation (maps to PRD §21)

Run through this checklist once Phases 1-4 (and at least one Phase 5 agent) are done:

- [ ] Kill a worker mid-run → another worker resumes from checkpoint, no duplicate work.
- [ ] Every tool call in a full agent run passes through the policy engine (spot-check
  `execution_events` — no tool_call event lacking a preceding policy decision).
- [ ] A restricted tool call reaches `WAITING_FOR_APPROVAL` and only executes post-approval.
- [ ] A sandboxed tool call actually runs inside a container (not in-process).
- [ ] A run with a tight budget terminates `BUDGET_EXCEEDED` before finishing all steps.
- [ ] A run can be cancelled mid-execution.
- [ ] A completed run's full trace is inspectable via `/runs/{id}/trace` and in
  OpenTelemetry.
- [ ] Grafana shows live runtime health for an in-progress run.
- [ ] Two evaluation runs against the same dataset produce a comparable metrics table.
- [ ] `podman compose up` (mapping the PRD's `docker compose up`) brings up the entire
  system with no Kubernetes/cloud dependency.
