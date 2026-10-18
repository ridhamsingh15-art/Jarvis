# JARVIS Capability Maturity Ledger

**Purpose:** Track the full JARVIS vision one capability at a time. Do not begin implementation on the next capability until the current capability's acceptance gate is satisfied and recorded here.

**Scoring note:** This is a transparent engineering rubric, not a universal objective percentage. Weights total 100%. Maturity scores are evidence-based engineering judgments. A capability can be marked 100% only when all of its scoped acceptance criteria are documented, executed, and passing; this does not mean the software is bug-free or production-ready.

## Scoring model

Weighted points = `weight × maturity / 100`.

- **0%:** no implementation/evidence found in the reviewed project state.
- **25%:** concept or narrow/experimental implementation; major acceptance cases absent.
- **50%:** partly functional; key integrations or failure cases unverified.
- **75%:** substantial implementation and regression coverage; material gaps remain.
- **100%:** all capability-specific acceptance criteria are documented, executed, and passing; relevant limitations are fixed or expressly excluded from the scoped requirement.

## Full vision scorecard

These are the current evidence-based maturity estimates. Revise each capability only when its acceptance gate is closed.

| # | Capability | Weight | Maturity now | Status |
|---:|---|---:|---:|---|
| 1 | Core conversational agent and orchestration | 10% | 100% | **ACCEPTED — gate complete** |
| 2 | Best-model strategy and provider routing | 8% | 50% | QUEUED |
| 3 | Planning, reasoning and multi-step execution | 9% | 75% | QUEUED |
| 4 | Computer use: files, shell, browser and applications | 10% | 75% | QUEUED |
| 5 | Long-term personal memory | 7% | 50% | QUEUED |
| 6 | Adaptive personality and personalization | 4% | 25% | QUEUED |
| 7 | Voice input and output | 7% | 0% | QUEUED |
| 8 | Screen-aware perception and context | 7% | 25% | QUEUED |
| 9 | REA: research and JARVIS auditing workflow | 6% | 25% | QUEUED |
| 10 | Autonomous goals, background tasks and schedules | 6% | 75% | QUEUED |
| 11 | Safety, permissions and approvals | 8% | 50% | QUEUED |
| 12 | Durable persistence and crash recovery | 6% | 75% | QUEUED |
| 13 | Testing, independent verification and observability | 4% | 75% | QUEUED |
| 14 | GUI and user experience | 3% | 75% | QUEUED |
| 15 | Extensible tools, skills and integrations | 3% | 50% | QUEUED |
| 16 | Deployment and operational management | 2% | 50% | QUEUED |
| | **Total** | **100%** | | |

Initial weighted baseline: **54.25 / 100**. Current weighted score after accepting Gate 1: **56.75 / 100**. These are rubric-based progress estimates, not objective proof that the overall vision is complete.

## Gate 1 — Core conversational agent and orchestration

### Scope

Cover the main Agent request path and coordination layer. Do not treat voice, complete model/provider selection, full screen perception, or the separate durable Mission Control capability as complete just because the Agent can route to those systems.

### Acceptance criteria

1. **Request/session lifecycle:** normal chat/tool/memory/mission routes preserve session/turn state and usable conversation context; optional memory or persistence errors do not create false tool success.
2. **Task-state discipline:** only runnable tasks are dispatched; terminal tasks are not re-executed or transitioned twice; retryable failures use legal state transitions; active tasks owned by another execution are not mutated.
3. **Bounded orchestration:** model-directed execution remains behind the canonical Agent processing/policy boundary; iteration ceilings and duplicate-action detection stop loops; malformed task arguments do not crash loop fingerprinting.
4. **Uncertain side effects:** callback exceptions, invalid callback returns, and side-effecting timeouts become explicit `OUTCOME UNKNOWN`; no automatic retry, subsequent model-directed action, or later preplanned batch action occurs after uncertainty.
5. **Truthful responses:** uncertain outcomes override optimistic model claims; broken callback contracts cannot be reported as success; skipped tasks do not inflate actual execution counts.
6. **Trace and diagnostics:** request trace records route, outcome-unknown status and final response; telemetry does not classify uncertain operations as plain success.
7. **Regression acceptance:** focused tests, broader Agent/planner/parser/router/session/runtime acceptance, targeted Ruff and compile checks, complete repository test suite, and review of all skips. No claim of zero bugs or full repository audit is implied.
8. **Preservation:** no staging, commit, push, reset, stash, or rewriting unrelated user work without explicit permission.

### Gate 1 worklog

- **2026-10-18 — accepted at 100% within this gate's scope.** Hardened `core/tool_feedback_loop.py` to stop on `OUTCOME UNKNOWN`, prevent automatic retry/model continuation, annotate later preplanned tasks as not executed, handle invalid callback returns/exceptions, preserve completed/running task state, and create deterministic cycle-safe task fingerprints.
- Added `core/action_safety.py` with an explicit read-only allowlist and narrowly scoped pre-side-effect failure classification for `file.open_file`. Generic mutation errors (including permission errors) remain uncertain; only documented pre-launch path/type/blocked checks use ordinary bounded recovery.
- Hardened `core/executor/executor.py`, legacy `core/executor.py`, `core/agent.py`, and `core/execution_summary.py` so handler exceptions after possible side effects are recorded as `OUTCOME UNKNOWN`, optimistic model claims cannot conceal them, callback faults are not retried because of internal `TypeError`, and uncertain result summaries preserve target names and partial-completion facts.
- Added regressions in `tests/test_tool_feedback_loop.py`, `tests/test_agent_timeout_isolation.py`, and `tests/test_executor_reexecution_guard.py` for no-retry behavior, no follow-on batch action, already-terminal tasks, invalid callback results, malformed args, safe read-only recovery, and truthfulness of final responses.
- Focused final grounding/orchestration/executor regression set: **88 passed**. Expanded Agent/execution-path suite: **315 passed**.
- Final full repository test run: **1,431 passed, 8 skipped, 0 failed in 103.67s**. The 8 skips were reviewed: 1 directory-symlink test skipped because the environment disallows creating symlinks; 7 POSIX-specific shell tests skipped on Windows (1 POSIX absolute-path-vs-Windows-switch case, 4 POSIX parameter-expansion cases, 1 POSIX shell-quoting case, and 1 POSIX absolute-path-handling case). No failing tests remain.
- Runtime smoke check: `SMOKE_TEST=PASS`; `main.py --help`, `mission_crash_safe.py --help`, and `mission_control.cli --help` exited successfully; whole-package `compileall` passed. Targeted Ruff on the touched modules passed. `git diff --check` passed; Git emitted existing LF-to-CRLF conversion warnings only.
- Scope boundary: Gate 1 acceptance covers the conversational Agent orchestration seam, not the later provider-routing, computer-use capability depth, voice, screen awareness, or production-readiness release gate. Those remain queued rows and are not implied complete by this acceptance record.

## Operating rule

Work one row at a time in the displayed order. For each row: inspect code and callers, reproduce defects, apply focused fixes, add/adjust regression tests, run relevant integration/release checks, and record actual output. Only set maturity to 100% and start the next row when the current gate's evidence is complete.