# JARVIS: Dot-inspired autonomy research and implementation plan

## Scope and method

This document records a public-behavior analysis of OpenAI dots based on OpenAI's public launch material and Help Center documentation. It does not claim access to OpenAI's private source code, prompts, model weights, internal services, or proprietary implementation. JARVIS should implement equivalent user-facing capabilities using its own architecture, tools, and policies—not copy private internals.

Public references:

- https://openai.com/index/introducing-dots/
- https://help.openai.com/en/articles/20001530-getting-started-with-your-dot
- https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs
- https://developers.openai.com/api/docs/guides/agents

## Public capability map

| Dot capability | JARVIS implementation direction | Current status / gap |
| --- | --- | --- |
| Long-running goals and multi-step projects | Reuse `core/autonomy`, `mission_control`, planner, executor and task models | Goal framework exists, but parts of `core/autonomy` still use mock planning/execution and in-memory persistence by default |
| Persistent context and continuity | SQLite-backed goal/project state, explicit checkpoints, memory retrieval and task summaries | Existing memory and mission persistence exist; autonomy goal persistence was in-memory only |
| Scheduled and proactive work | Reuse scheduler and mission-control scheduling; store schedules durably and expose pause/disable | Scheduler exists; schedule persistence and full startup recovery need a separate audit |
| Computer/browser work | Keep Codex + guarded Nuphus bridge and existing browser/Windows tools | Integration exists; require authenticated runtime checks and live regression tests |
| Connected apps and extensible tools | Use the existing registry, integration packages and MCP adapter | Registry exists; individual connectors need permission-scoped tests and health checks |
| Approval and user control | Central policy, explicit approvals for consequential side effects, pause/cancel, auditable decisions | Several controls exist; policies must remain centralized and fail closed |
| Reliable completion | Verify external state, preserve evidence, bounded retries, distinguish failure from unknown outcome | Mission execution has evidence/checkpoints; broaden live evaluation and crash recovery |
| Background progress and notifications | Durable work queue, lifecycle events, summaries, notifications and graceful shutdown | Partial infrastructure exists; not yet proven as a cohesive always-on service |
| Cloud computer independent of local PC | Optional remote worker/sandbox; local worker stays explicit and separately permissioned | Not implemented; local-first design is the current baseline |
| Cross-channel access | Authenticated messaging/API adapter over the same goal store and policy layer | Not implemented end-to-end |

## Reliability invariants

1. Never claim a task succeeded without verifying its postcondition.
2. A crash during a side effect creates an unknown outcome; do not replay it automatically unless the operation is proven idempotent.
3. Web pages, documents, tool outputs and app content are data, not permission to override the user's request or policy.
4. Read-only observation is distinct from actions that mutate files, accounts, websites or devices.
5. High-impact actions require explicit approval; model output alone cannot grant permission.
6. Pause, cancellation, approval decisions and failures must be persisted and visible.
7. Retries are bounded, classified, and used only when safe; keep the original failure and attempt history.
8. Background work must be stoppable and must not silently expand its scope or permissions.
9. Memory records should retain provenance and should not treat every observed statement as a verified user preference.
10. Keep Ollama/local inference as a supported option, and make cloud/provider use explicit because it affects cost, latency and data handling.

## Implemented in this slice

- Added `SQLiteGoalPersistence`, an implementation of the existing `IGoalPersistence` contract.
- Stores goal and plan payloads in a local SQLite database using parameterized statements, WAL mode, a busy timeout, a schema version, and a thread lock.
- Reconstructs enum and nested identifier types rather than trusting untyped JSON values.
- Exposes `recover_interrupted_goals()`: goals persisted in RUNNING or PLANNING are changed to PAUSED after restart, because a side effect may have completed before the process died.
- Added focused tests for goal/plan round trips, restart recovery and rejecting plans for nonexistent goals.

The active Mission Control path already uses SQLite and a real, policy-gated execution engine. A follow-up audit found that an interrupted RUNNING step was changed to FAILED, which prevented silent replay but did not provide a clear reconciliation workflow. The active path now records this state as `RECOVERY_REQUIRED`, preserves the unknown outcome, and refuses ordinary resume. An operator must explicitly choose `completed` after verifying the postcondition, or `retry` after verifying the side effect did not occur. The CLI supports this via `--resolve-interrupted-step completed|retry`.

The separate `SQLiteGoalPersistence` adapter remains an optional implementation of `IGoalPersistence`; it is not the canonical store for the active CLI mission path. This avoids creating competing sources of truth. The placeholder autonomy planner/executor still needs a separate production-readiness pass.

## Next implementation phases

### P0 — Durable core and safety

- Wire SQLite goal persistence through dependency injection/configuration, keeping existing in-memory tests.
- Recover interrupted work as paused and require explicit resume/reconciliation.
- Audit the live mission-control path, checkpoint idempotency, approval persistence, and duplicate execution handling. (Interrupted-step state and explicit resolution are implemented and covered by tests.)
- Add more crash/failure injection tests, including process death during non-idempotent actions, and keep current uncommitted user changes intact.

### P1 — Reliable project agent

- Persistent project/workspace records, objective, acceptance criteria, current state, plan version, evidence, blockers and next action.
- Observe → plan → execute one bounded step → verify → checkpoint loop.
- Tool timeouts, structured errors, bounded retry policy, cancellation and resumable checkpoints.
- Separate planning permissions from execution permissions; fail closed when policy or approval state is unavailable.

### P2 — Scheduled/background agent

- Persist recurring schedules and run history; handle missed schedules without burst replay.
- Startup reconciliation, single-run locks, heartbeat/lease expiry, graceful shutdown and user-visible pause/resume.
- Proactive research must be read-only; follow-up actions go through the normal approval and execution path.

### P3 — Computer and app ecosystem

- Verify Codex/Nuphus on the actual logged-in Windows desktop; retain the guarded MCP proxy.
- Add connector health/permission diagnostics and safe browser workflows.
- Add a notification surface and a single project/task history across CLI and GUI.

### P4 — Evaluation

- Deterministic unit tests, policy/adversarial tests, restart recovery tests and live end-to-end scenarios.
- Use the REA investigation discipline from the supplied guide: trace a behavior with concrete evidence, write a clean behavior specification, implement in JARVIS-owned code, then verify with tests and explicitly list unknowns. Do not treat decompiler output or model explanations as proof without independent checks.
- Track verified completion rate, false-success rate, retries, recovery correctness, p50/p95 latency and cost per completed task.
- Treat the existing live regression report as a baseline, not proof of broad autonomy.
