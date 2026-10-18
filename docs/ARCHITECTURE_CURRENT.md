# Current JARVIS Architecture (2026-10-17)

This document describes the current wired entry points and durable mission path. It supersedes the legacy pipeline descriptions in `ARCHITECTURE.md`, `FLOW.md`, and `MODULES.md` where they conflict.

## Entry points

- `main.py`: primary Windows application/CLI entry point. The mission mode delegates to the crash-safe mission runner; `--workspace-root` controls the allowed filesystem/shell working boundary and `--require-verified` makes unverified completion return non-zero.
- `mission_crash_safe.py`: direct CLI for durable mission execution, recovery, pending approvals, and needs-review management.
- `core/bootstrap/bootstrapper.py`: composition root for the DI-backed AIOS runtime and `AutonomousGoalManager`.
- `gui/views/missions_view.py`: GUI projection for durable mission/step status, verification, approvals, and recovery controls.

## Crash-safe mission path

```text
User objective / structured plan
  -> mission_control.crash_cli
  -> CrashSafeMissionStore (SQLite durable journal)
  -> CrashSafeMissionRunner
  -> ExecutionPolicy
  -> ExecutionEngine / registered tool handlers
  -> tool result + independent postcondition verifier
  -> durable step and mission state
```

Before a side-effecting tool runs, the runner writes a durable step intent and idempotency key. Step claims are guarded against a second live runner overwriting an in-flight claim. If a process disappears after a side effect may have happened, the runner marks the step `needs_review` and does not automatically replay it.

Mission IDs are bound to their stored objective and plan. `--resume` reloads that durable plan rather than generating a replacement. Missing or malformed executor exit codes fail closed. `--require-verified` succeeds only when mission verification status is `verified`.

## Approval and filesystem boundary

- Model-authored `user_confirmed` fields are not authorization.
- High-risk actions enter `WAITING_APPROVAL`; `--approve MISSION_ID --step N` records an explicit durable approval before execution, and `--deny` records rejection. Pending approvals remain pending when the mission is inspected or resumed without an approval decision.
- Workspace-root checks apply to file mutations and shell working directories. The main application defaults to its repository root; callers may supply `--workspace-root` to authorize a different working directory.
- New files inside the workspace are supported. Overwriting an existing file requires policy approval; `create_file` does not silently overwrite an existing target.
- Shell entry points use an explicit allowlist. Inline interpreter execution is confirmation-gated, path-qualified interpreters do not match the allowlist, and direct `.env` reads through the shell are blocked.
- Chromium CDP inspection is loopback-only and opt-in via `JARVIS_ENABLE_CDP_VERIFICATION=1`.

## Goal autonomy

`AutonomousGoalManager` owns the goal lifecycle, persistence, plan/step execution, intervention metadata, and scheduling. The autonomy step executor delegates durable mission work to the crash-safe mission path and requires verified outcomes before returning success. Goal intervention metadata uses `intervention_kind` to distinguish approval, policy denial, unknown outcome, and manual intervention.

## Legacy compatibility path

`mission_control.cli` and `MissionExecutor` remain a separate legacy compatibility path with their own `MissionStore` tables. They do not own the crash-safe approval/reconciliation workflow and should not be extended as the authoritative autonomous execution path. Prefer `main.py` mission mode or `mission_crash_safe.py` for durable mission execution.

## Evidence and limits

See [`JARVIS_HARDENING_STATUS.md`](JARVIS_HARDENING_STATUS.md) for current test results and unresolved limitations. The local test suite is evidence for tested code paths, not a penetration test or proof of general-purpose autonomous reliability. Held-out private objectives and live authenticated browser/desktop flows remain unverified.
