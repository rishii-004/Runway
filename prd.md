# Forge — Agent Execution & Evaluation Harness

## 1. Product Summary

**Forge** is a local-first, production-oriented runtime for executing **stateful, tool-using LangGraph agents** reliably, safely, and observably.

Forge does not replace LangGraph and is not itself an agent. It provides the infrastructure around agents:

* Durable execution and recovery
* Distributed task execution
* Tool permissions and safety policies
* Resource and cost budgets
* Human-in-the-loop approval
* Sandboxed tool execution
* Observability and tracing
* Run inspection and replay
* Agent evaluation and benchmarking

The same Forge runtime should be capable of running different agents such as:

```text
Code Review Agent
Incident RCA Agent
Data Migration Agent
Repository Intelligence Agent
```

The core idea:

> **The agent decides what should happen. Forge controls how, when, and under what constraints that decision is executed.**

---

# 2. Problem

Agent prototypes commonly look like:

```text
LLM → Tool → LLM → Tool → Answer
```

This works for demos but becomes difficult to operate reliably when agents:

* run for a long time
* call external tools
* fail halfway through execution
* consume unpredictable amounts of tokens
* perform risky operations
* require human approval
* need to run concurrently
* need to be debugged or evaluated
* need to resume after worker failure

Forge provides a controlled execution environment for these workloads.

---

# 3. Goals

## Primary Goals

1. Execute LangGraph agents as managed workloads.
2. Persist state and recover interrupted executions.
3. Distribute agent runs across workers.
4. Enforce tool permissions and execution policies.
5. Enforce runtime, step, token, and cost budgets.
6. Support asynchronous human approval.
7. Provide detailed execution traces.
8. Support run inspection and replay.
9. Evaluate different agent versions against repeatable datasets.
10. Run the complete platform locally using Docker Compose.

## Non-Goals

Forge will initially **not**:

* replace LangGraph
* become a general-purpose LLM framework
* train or fine-tune models
* require Kubernetes
* require cloud infrastructure
* provide a generic chatbot UI
* support every agent framework

---

# 4. Target Users

### Agent Developer

Builds a LangGraph agent and wants reliable execution without implementing:

* retries
* checkpoint recovery
* tool authorization
* budgets
* observability
* worker management

### AI/Backend Engineer

Needs to run many agent workloads concurrently and understand their performance and failures.

### Platform/Infrastructure Engineer

Wants a controlled runtime for autonomous agents with policies, resource limits, and auditability.

---

# 5. User Experience

A developer defines an agent:

```python
incident_agent = build_incident_agent()
```

and submits it to Forge:

```python
run = forge.run(
    agent=incident_agent,
    task="Investigate elevated payment-service latency",
    policy="production",
    budget=Budget(
        max_steps=50,
        max_tokens=100_000,
        max_cost_usd=2.00,
        max_runtime_seconds=300,
    ),
)
```

Forge handles:

```text
queueing
    ↓
worker assignment
    ↓
LangGraph execution
    ↓
checkpointing
    ↓
tool authorization
    ↓
retries/timeouts
    ↓
human approval if required
    ↓
result persistence
    ↓
observability
```

The developer can inspect the run through an API/dashboard.

---

# 6. High-Level Architecture

```text
                         Client
                           │
                           ▼
                    ┌──────────────┐
                    │   FastAPI    │
                    │ Control Plane│
                    └──────┬───────┘
                           │
              ┌────────────┼─────────────┐
              ▼            ▼             ▼
        ┌──────────┐ ┌───────────┐ ┌──────────┐
        │ Scheduler│ │   Policy  │ │  Budget  │
        │          │ │   Engine  │ │  Manager │
        └────┬─────┘ └─────┬─────┘ └────┬─────┘
             └──────────────┼─────────────┘
                            ▼
                     ┌────────────┐
                     │  RabbitMQ  │
                     │ Task Broker│
                     └─────┬──────┘
                           │
                 ┌─────────┼─────────┐
                 ▼         ▼         ▼
              Worker 1  Worker 2  Worker 3
                 │         │         │
                 └─────────┼─────────┘
                           ▼
                    ┌────────────┐
                    │ LangGraph  │
                    │  Runtime   │
                    └─────┬──────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
             LLM         Tools       HITL
              │           │           │
              └───────────┼───────────┘
                          ▼
                   ┌──────────────┐
                   │  PostgreSQL  │
                   │ Durable State│
                   └──────────────┘

             Redis → locks / cache / coordination

             Docker → sandboxed tool execution

             OpenTelemetry → traces
             Prometheus → metrics
             Grafana → dashboards
```

---

# 7. Core Components

## 7.1 Agent Runtime

Responsible for executing LangGraph agents.

Each run maintains:

```text
run_id
agent_id
task
status
current_node
iteration
started_at
completed_at
```

Run lifecycle:

```text
QUEUED
  ↓
RUNNING
  ↓
WAITING_FOR_APPROVAL
  ↓
RUNNING
  ↓
COMPLETED
```

Alternative terminal states:

```text
FAILED
CANCELLED
TIMEOUT
BUDGET_EXCEEDED
```

---

## 7.2 RabbitMQ Task Broker

RabbitMQ is responsible for **work distribution**, not durable application state.

Example messages:

```text
run.requested
run.resume
tool.execute
evaluation.execute
```

Workers consume jobs from RabbitMQ.

Successful work is acknowledged.

Failed/crashed workers can result in message redelivery according to the configured acknowledgement/retry strategy.

---

## 7.3 PostgreSQL

PostgreSQL is the **source of truth**.

Store:

```text
agents
runs
run_steps
checkpoints
tool_calls
approvals
budgets
execution_events
evaluations
evaluation_results
```

PostgreSQL should retain enough information to reconstruct and inspect a run.

---

## 7.4 Redis

Redis provides ephemeral coordination:

```text
distributed locks
short-lived cache
rate limiting
worker coordination
temporary state
```

Redis is not the authoritative source for agent state.

---

# 8. Durable Execution

Forge must support recovery from worker failure.

Example:

```text
Step 1 ✓
Step 2 ✓
Step 3 ✓
Step 4 ✓
Step 5 → executing
         ↓
       Worker crash
         ↓
       new worker
         ↓
   load checkpoint
         ↓
       Step 5
```

The system should avoid unnecessarily repeating successfully completed work.

This is a core feature rather than an optional enhancement.

---

# 9. Tool Registry & Policy Engine

Tools are centrally registered.

Example:

```yaml
name: kubectl
risk: high
requires_approval: true
timeout_seconds: 30
```

Possible policy decisions:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

Example:

```text
Agent
  ↓
request: execute_migration()
  ↓
Policy Engine
  ↓
HIGH RISK
  ↓
REQUIRE_APPROVAL
  ↓
Human
  ↓
APPROVE
  ↓
Tool Execution
```

The agent must never bypass the Forge tool gateway.

---

# 10. Resource Budgets

Every run may have limits:

```yaml
max_steps: 50
max_runtime_seconds: 300
max_tokens: 100000
max_cost_usd: 2.00
```

Forge tracks usage throughout the run.

Example:

```text
Steps:      17 / 50
Tokens:     41,290 / 100,000
Cost:       $0.73 / $2.00
Runtime:    84s / 300s
```

Exceeding a configured limit causes the run to pause or terminate according to policy.

---

# 11. Retry & Failure Handling

Forge supports configurable failure policies.

Examples:

```text
LLM timeout
    → exponential backoff → retry

HTTP 429
    → backoff → retry

Tool timeout
    → retry N times

Invalid tool arguments
    → return structured error to agent

Permission denied
    → terminate

Budget exceeded
    → terminate

Worker crash
    → recover from checkpoint
```

Retry behavior should be configurable rather than hard-coded.

---

# 12. Human-in-the-Loop

Agents can pause execution when an action requires approval.

```text
Agent
  ↓
Dangerous action
  ↓
Forge Policy Engine
  ↓
WAITING_FOR_APPROVAL
  ↓
Human approves
  ↓
Resume checkpoint
  ↓
Continue execution
```

The worker should not need to remain alive while waiting.

Approval state is persisted in PostgreSQL.

---

# 13. Sandboxed Execution

Potentially unsafe tools or generated code should execute inside Docker containers.

Example:

```text
Agent
  ↓
run_tests()
  ↓
Policy Engine
  ↓
Sandbox Manager
  ↓
Docker container
  ↓
pytest
  ↓
stdout/stderr/result
  ↓
Agent
```

Sandbox configuration should support:

```text
CPU limits
memory limits
execution timeout
filesystem isolation
optional network restrictions
```

---

# 14. Observability

Forge should provide visibility into every agent execution.

### OpenTelemetry

Used for distributed traces:

```text
run
 ├── LangGraph node
 ├── LLM call
 ├── tool call
 ├── database operation
 └── sandbox execution
```

### Prometheus

Track:

```text
agent_runs_total
agent_run_duration
tool_latency
llm_latency
queue_depth
worker_utilization
retry_count
failure_rate
token_usage
estimated_cost
```

### Grafana

Provide dashboards for:

* active runs
* queue depth
* worker health
* latency
* failures
* token usage
* estimated cost
* tool performance

---

# 15. Run History & Replay

Every run should produce an inspectable execution history.

Example:

```text
Step 1  search_repository
Step 2  analyze_dependencies
Step 3  generate_hypothesis
Step 4  execute_test
Step 5  generate_fix
Step 6  verify
```

Users should be able to:

```text
inspect(run_id)
replay(run_id)
resume(run_id)
```

A future extension should allow:

```text
Replay from checkpoint N
with different model/prompt/configuration
```

This enables agent debugging and experimentation.

---

# 16. Evaluation Framework

Forge should support repeatable agent evaluation.

Example dataset:

```text
tasks.jsonl

task_001
task_002
task_003
...
task_1000
```

Run:

```text
Agent v1
   ↓
1000 tasks
```

and collect:

```text
task success
tool accuracy
latency
token usage
cost
failure rate
```

Compare versions:

```text
                v1       v2
Success         71%      84%
Tool accuracy   83%      91%
Avg latency     8.2s     7.4s
Avg cost        $0.18    $0.13
```

This becomes the foundation for **agent regression testing**.

---

# 17. API

Initial control-plane API:

```text
POST   /agents
GET    /agents/{id}

POST   /runs
GET    /runs/{id}
POST   /runs/{id}/cancel
POST   /runs/{id}/approve
POST   /runs/{id}/deny

GET    /runs/{id}/events
GET    /runs/{id}/trace
POST   /runs/{id}/replay

POST   /evaluations
GET    /evaluations/{id}
```

---

# 18. Tech Stack

## Core

* **Python 3.12+**
* **LangGraph**
* **FastAPI**
* **Pydantic**

## Persistence & Messaging

* **PostgreSQL** — durable state/source of truth
* **RabbitMQ** — task/work distribution
* **Redis** — locks, caching, ephemeral coordination

## Execution

* **asyncio** — asynchronous worker execution
* **Docker** — sandboxed execution

## Observability

* **OpenTelemetry**
* **Prometheus**
* **Grafana**
* Structured JSON logging

## Testing

* **pytest**
* **pytest-asyncio**
* **Testcontainers**

## Local Infrastructure

* **Docker Compose**

### Explicitly excluded from v1

```text
Kubernetes
Kafka
Celery
Cloud infrastructure
```

These may be explored later if the architecture requires them.

---

# 19. Repository Structure

```text
forge/
├── api/
│   ├── routes/
│   └── schemas/
│
├── runtime/
│   ├── executor.py
│   ├── scheduler.py
│   ├── lifecycle.py
│   └── recovery.py
│
├── agents/
│   └── langgraph_adapter.py
│
├── tools/
│   ├── registry.py
│   ├── executor.py
│   └── models.py
│
├── policy/
│   ├── engine.py
│   └── rules.py
│
├── budgets/
│   └── manager.py
│
├── checkpoints/
│   └── postgres.py
│
├── messaging/
│   ├── rabbitmq.py
│   └── messages.py
│
├── workers/
│   └── worker.py
│
├── sandbox/
│   └── docker.py
│
├── events/
│   └── publisher.py
│
├── evaluation/
│   ├── runner.py
│   └── metrics.py
│
├── observability/
│   └── tracing.py
│
├── storage/
│
├── tests/
│
├── docker-compose.yml
└── pyproject.toml
```

---

# 20. Development Roadmap

## Phase 1 — Core Runtime

```text
✓ FastAPI
✓ LangGraph integration
✓ PostgreSQL
✓ RabbitMQ
✓ Worker process
✓ Run lifecycle
✓ Checkpoint persistence
✓ Basic retries
✓ Timeouts
```

Success criterion:

> Kill a worker during execution and successfully resume the run from persisted state.

---

## Phase 2 — Runtime Controls

```text
✓ Tool registry
✓ Policy engine
✓ Budgets
✓ Cancellation
✓ Redis coordination
✓ Human approval
```

Success criterion:

> An agent cannot execute a restricted tool without satisfying Forge's policy.

---

## Phase 3 — Sandbox & Observability

```text
✓ Docker sandbox
✓ OpenTelemetry
✓ Prometheus
✓ Grafana
✓ Structured execution events
```

Success criterion:

> A developer can inspect an entire agent run, including LLM calls, tools, latency, failures, and resource usage.

---

## Phase 4 — Evaluation & Replay

```text
✓ Evaluation datasets
✓ Batch evaluation
✓ Agent version comparison
✓ Run replay
✓ Checkpoint inspection
```

Success criterion:

> Run two versions of an agent against the same dataset and quantitatively compare them.

---

## Phase 5 — Demonstration Agents

Build 2–3 agents specifically to demonstrate Forge:

### Code Review Agent

```text
PR
 ↓
analyze
 ↓
find issues
 ↓
generate patch
 ↓
run tests
 ↓
verify
```

### Incident RCA Agent

```text
Alert
 ↓
metrics
 ↓
logs
 ↓
traces
 ↓
hypothesis
 ↓
verification
 ↓
optional remediation
```

### Data Pipeline RCA Agent

```text
Pipeline failure
 ↓
Kafka/data-source inspection
 ↓
storage inspection
 ↓
database inspection
 ↓
evidence correlation
 ↓
root cause
```

These agents are **demonstrations of the harness**, not the primary product.

---

# 21. Definition of Done

Forge v1 is considered successful when:

### Reliability

* A worker can crash during execution and another worker can resume from a checkpoint.
* Failed tool/LLM operations follow configurable retry policies.
* Runs have explicit lifecycle states.

### Safety

* Every tool invocation passes through the policy engine.
* Restricted operations can require human approval.
* Potentially unsafe execution occurs inside a Docker sandbox.

### Control

* Runs have configurable step/time/token/cost budgets.
* Runs can be cancelled.

### Observability

* Every run has a traceable execution history.
* Tool/LLM latency and resource usage are measurable.
* Grafana exposes runtime health and workload metrics.

### Evaluation

* Agent versions can be evaluated against the same dataset.
* Results are persisted and comparable.
* Individual runs can be inspected/replayed.

### Local Development

The complete system can be started with:

```bash
docker compose up
```

without requiring Kubernetes or cloud infrastructure.

---

# 22. Final Product Vision

Forge should ultimately demonstrate a clear separation:

```text
┌─────────────────────────────────────┐
│             AGENT                   │
│                                     │
│ "What should I do?"                 │
│                                     │
│ LangGraph                           │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│             FORGE                   │
│                                     │
│ "Can you do it safely, reliably,    │
│  observably and within constraints?"│
│                                     │
│ Runtime                             │
│ Policy                              │
│ Budgets                             │
│ Recovery                            │
│ HITL                                │
│ Replay                              │
│ Evaluation                          │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│          EXECUTION ENVIRONMENT      │
│                                     │
│ Docker / APIs / Databases / Tools   │
└─────────────────────────────────────┘
```

**Forge's core promise:**

> **Run autonomous agents reliably, safely, and measurably — without requiring every agent developer to reinvent the execution infrastructure.**
