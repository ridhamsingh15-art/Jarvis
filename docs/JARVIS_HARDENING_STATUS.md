# JARVIS Hardening Status

This document records security/reliability changes made against the current working tree. It does not certify JARVIS as production-ready.

## Implemented in this hardening pass

- Destructive file mutations, append operations, patches/edits, and overwrites of existing files require policy approval; creating new files is allowed only inside the configured workspace, and `create_file` refuses to overwrite an existing file.
- Mission plan fields such as `user_confirmed` are not treated as authorization. Approval comes from the durable approval record.
- The crash-safe CLI and `main.py` mission entry point use a deterministic workspace boundary. The crash-safe CLI can list pending approvals (`--pending-approvals`), explicitly approve a step (`--approve MISSION_ID --step N`), or deny it (`--deny MISSION_ID --step N`). Approval is persisted before the runner executes the step.
- Re-running a mission awaiting approval preserves the approval queue; policy decisions do not inflate execution-attempt counts.
- WAL step claims are guarded so an in-flight side-effecting step cannot be overwritten by a second runner. Read-only interrupted steps remain retryable.
- The crash-safe CLI's `--resume` uses the stored objective and plan; a mission ID cannot silently be reused with a different plan. CLI success now requires a completed mission with independently verified status; `--require-verified` remains accepted for compatibility.
- Missing/malformed legacy executor exit codes fail closed; duplicate step descriptions are tracked by step index; the legacy state enum includes `ABANDONED`.
- Production shell entry points use explicit command prefixes with token-boundary matching. Quoted/absolute-path nested shells are blocked, inline Python execution is approval-gated even with a quoted interpreter path, and direct `.env` access through shell is blocked.
- Shell stdout/stderr pipes are drained concurrently with a strict in-memory retention limit; sensitive command arguments are omitted from shell logs. Test doubles use a separate mocked-process fallback and do not alter the real-pipe path.
- FileTool can enforce a workspace boundary for writes; the main agent, bootstrap runtime, and crash-safe mission engine configure it. Project-root mutation exceptions are scoped to named test-workspace directories, not filename prefixes.
- The crash-safe runner now stops dependent steps unless independent verification returns `verified`; uncertain side effects are persisted as `needs_review`, and CLI success requires a verified completed mission. Common file mutation postconditions are checked on disk.
- Output-only `expected_outcome` assertions cannot upgrade failed/unsupported independent verification. Browser URL evidence and shell logs redact credentials/query values and raw command arguments.
- Codex child processes receive a filtered environment without keys classified as sensitive. The GUI Missions view receives the configured `--mission-db` path.
- The adaptive planner honours `JARVIS_DISABLE_LIVE_MODEL_PLANNING` as well as `JARVIS_LLM_PLANNING`.
- Gemini API keys are sent in the `x-goog-api-key` header instead of URL query strings.
- Skill execution fails closed when no policy is configured.
- Untrusted tool output cannot forge the closing `UNTRUSTED_TOOL_RESULT` delimiter.
- `open_app` verification requires a before/after process baseline; an already-running app is reported as partial rather than verified.
- Chromium CDP inspection requires `JARVIS_ENABLE_CDP_VERIFICATION=1` and remains loopback-only.
- The smoke test validates actual bootstrap/runtime wiring without opening applications or writing user files.
- Added `requests` to runtime dependencies and a Windows CI workflow for compile, tests, smoke test, and CLI help.

## Last local verification (2026-10-17)

- Latest full suite after the additional audit follow-up: **1,210 passed, 1 skipped, 0 failed** in 125.08 seconds; exit code 0. The skip remains the Windows unprivileged-symlink limitation documented in the test suite.
- `compileall` over `core`, `mission_control`, `tools`, and `providers`: exit 0.
- `smoke_test.py`: exit 0; bootstrap and `AutonomousGoalManager` resolution passed; no external/state-changing actions executed.
- `main.py --help` and `mission_crash_safe.py --help`: exit 0.
- Ruff on the changed/hardened runtime and regression-test module set: all checks passed. Full-repository comparison: 258 current findings vs. 247 at HEAD; 11 new unique signatures are confined to existing untracked `jarvis_test_workspace/` and `workspace/OfficeForge/` files, with **zero new tracked-file signatures** and 4 resolved baseline signatures. No workspace/vendor files were modified.
- Targeted Ruff on the newly changed SQLite, planner, Qt bridge, GUI entry point, and regression tests: all checks passed. `compileall` over `core`, `mission_control`, `tools`, `providers`, `memory`, `gui`, and `main.py`: exit 0. `smoke_test.py`, both CLI help paths, and `git diff --check`: exit 0. Only Git line-ending conversion warnings remained.
- No commit, push, branch change, stash operation, or destructive Git command was performed. Existing user/agent changes and untracked workspaces were preserved.

## Verification commands

Run from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe smoke_test.py
.\.venv\Scripts\python.exe main.py --help
.\.venv\Scripts\python.exe mission_crash_safe.py --help
.\.venv\Scripts\python.exe -m compileall -q core mission_control tools providers
```

## Remaining limitations to verify before release

- A full penetration test, live provider/browser/desktop end-to-end test, and held-out objective evaluation have not been performed by this hardening pass.
- CDP remains a local debugging interface; opt-in reduces exposure but does not authenticate other local processes.
- The legacy `mission_control.cli` uses its legacy mission tables/executor and intentionally denies high-risk operations rather than sharing the crash-safe approval queue. Treat it as a compatibility path, not the authoritative autonomy interface.
- Mission/goal-wide execution deadlines are still not implemented (individual tools have their own timeouts). GUI projection/state vocabulary and broader legacy/runtime subsystem integration still need dedicated tests.
- CI now gates Ruff on the hardened runtime modules, but the full-repository Ruff baseline, type checking, and coverage are not enforced yet. The repository has pre-existing Ruff findings; this pass did not mass-reformat unrelated code.
- Planner evaluations remain curated/planning-only and are not evidence of general autonomous success. Private held-out objectives were not read or executed.


## Additional repository-audit follow-up (2026-10-17)

- `memory/sqlite_memory.py` now enables WAL for file-backed databases, sets a 10-second SQLite busy timeout, serializes mutations across `SqliteMemory` instances in the same process, and closes operation-scoped connections reliably. Regression tests exercise WAL settings, multiple instances, and concurrent writes.
- Added `gui/qt_event_bridge.py`. `build_agent()` now exposes the canonical EventBus in GUI context; `MainWindow` forwards core events through a queued Qt signal and unsubscribes on close. GUI consumers should connect their QObject slots with `Qt.ConnectionType.QueuedConnection` and avoid direct widget calls from EventBus handlers.
- `core/planner.py` now validates the tool-call envelope before normalization and allows one bounded schema-correction retry for malformed JSON or invalid action structure. Provider/router errors are not retried by this middleware; downstream registry/action validation remains mandatory.
- Existing `tools/shell.py` timeout and Windows Job Object process-tree cleanup remain the relevant host-specific safeguards. The generic executor still does not have a hard process-level deadline for every arbitrary in-process tool handler.
- Scope note: the per-database writer lock is synchronous in-process serialization, **not** a dedicated asynchronous writer queue and not a cross-process mutex. WAL/busy-timeout provide SQLite coordination across processes. A true queue remains a separate architecture change if asynchronous multi-agent write throughput requires it.
- Verification: **1,210 passed, 1 skipped** in the full suite; the targeted regression set passed (19 tests), targeted Ruff passed, smoke test and CLI help passed, compileall passed, and `git diff --check` passed. No commit or push was made.

## Concurrency decision follow-up (2026-10-17)

- Crash-safe operator approval/denial and `needs_review` retry/abandon now acquire a SQLite `BEGIN IMMEDIATE` transaction before reading the pending state. This serializes each read/decision/write sequence across concurrent connections so opposing decisions cannot both win for the same step.
- Added concurrent regression tests for approve-vs-deny and retry-vs-abandon. Each asserts one successful decision, one rejected stale decision, and consistent persisted mission/step states.
- Verification after this change: full suite **1,212 passed, 1 skipped, 0 failed** in 66.22 seconds; the skip remains the Windows unprivileged-symlink limitation. The 28 crash-safe mission/recovery tests passed, Ruff passed on the touched Python files, and `git diff --check` passed.
- This closes only the tested state-transition race. It does not establish exactly-once side effects across arbitrary external systems, complete authorization security, or production readiness; those still require broader adversarial and end-to-end evaluation.

## End-to-end runtime acceptance follow-up (2026-10-17)

- Added `tests/test_runtime_acceptance.py` to make two cross-layer behaviors executable acceptance gates:
  - Real CLI execution reads a real file, fails an independently checked `file_contains` postcondition, and must not perform the dependent file write.
  - A real `AutonomyService` thread executes a two-step file objective through `ExecutionBackedGoalPlanner`, `CrashSafeGoalStepExecutor`, the crash-safe mission journal, and registered `FileTool` handlers. Both steps must have independent verification evidence; a fresh service instance must reload the completed goal without replaying either step.
- The acceptance test does not mock the execution engine, file tool, or independent file verifier. The autonomy planner/manager are instantiated with a controlled local workspace and temporary SQLite stores; no external accounts, browser sessions, or user files are touched.
- Verification: acceptance-focused set **94 passed, 0 failed**; full suite **1,214 passed, 1 skipped, 0 failed** in 67.12 seconds. The skipped test remains the Windows unprivileged-symlink limitation. Ruff passed for `tests/test_runtime_acceptance.py`; `git diff --check` passed for that file.
- This demonstrates one real multi-step objective and one real failed-postcondition stop condition, plus durable completed-goal reload. It does **not** prove crash recovery at every possible instruction boundary, general exactly-once side effects, every tool/action authorization path, or whole-process deadlines for arbitrary in-process handlers.
- Remaining acceptance work is explicit: adversarially enumerate every registered tool/action through each reachable entrypoint; terminate and restart at planning, before execution, during execution, after external side effect, and before/after persistence; verify recovery classifications and duplicate-side-effect counts; exercise stalled non-shell handlers and service shutdown/startup under deadlines; and run live browser/desktop/provider tests only in a controlled environment.
- No commit, push, branch change, stash operation, or destructive Git command was performed. Pre-existing modified and untracked user/agent work remains preserved.

## Execution-path adversarial follow-up (2026-10-17)

- Added `tests/test_execution_path_acceptance.py` to exercise workspace boundaries and shell restrictions through the actual `mission_crash_safe.py` subprocess, then inspect real filesystem side effects and the durable mission journal.
- The first adversarial run found a **real workspace escape**: a workspace-scoped `file.rename` validated the source path but did not validate `new_name` as a single filename. After durable approval, `new_name="../escaped-renamed.txt"` renamed a file from inside the workspace to its parent, and the runner incorrectly recorded the action as completed/verified. This was reproduced against a temporary directory, not user files.
- Fixed `tools/file.py`: workspace-scoped rename now validates the destination filename and its resolved destination against the configured workspace; the rename handler also rejects path-like `new_name` values even when no workspace root is configured.
- Regression coverage proves that create/write/folder traversal, rename-target traversal after approval, and recursive nested-shell deletion attempts do not produce the prohibited side effect. The shell test's plan-authored `user_confirmed` field does not override shell hard-deny rules.
- Verification after the fix: **126 targeted tests passed** across execution-path acceptance, runtime acceptance, crash-safe mission recovery, execution policy, sensitive file paths, shell safeguards, and Agent timeout isolation. Ruff passed on the modified implementation and new acceptance modules.
- This closes the reproduced rename-target traversal, not all path-race/symlink adversaries or every reachable entrypoint. Legacy execution, the normal Agent path, provider/desktop integrations, and stalled non-shell tool lifecycle still need dedicated side-effect-observing acceptance coverage.

- Final verification after the rename-target containment fix: full suite **1,219 passed, 1 skipped, 0 failed** in 66.06 seconds; Ruff, Python compilation for the changed/new Python modules, and `git diff --check` passed. Git emitted only the existing LF-to-CRLF working-copy warnings. No commit/push/branch operation was performed.

- Expanded the workspace-boundary matrix to cover all ten FileTool mutation actions: create, overwrite, append, patch/edit, folder creation, rename, move, copy, and delete. High-risk actions are tested after the durable approval step; each assertion checks the real filesystem, not only the returned status.
- Latest verification after expanding that matrix: full suite **1,225 passed, 1 skipped, 0 failed** in 69.20 seconds. The focused execution/security/runtime set is now **132 passed**; Ruff, Python compilation, and `git diff --check` passed for the changed/new modules.

## Crash-stage and legacy verification follow-up (2026-10-17)

- Added `tests/test_crash_stage_matrix.py`. It starts a real child process, executes a real file handler, blocks only after the verified step record has been durably persisted, kills the process, and resumes from the same SQLite journal. The file remains present, the step remains completed, and `attempt_count` stays at 1 after recovery.
- Added success-shaped false-result tests against both the crash-safe runner and the legacy `MissionExecutor`: a fake handler claims a file was created and reports exit code 0, but does not create it. Neither path may mark the mission completed; independent on-disk verification rejects the claim.
- Hardened `mission_control/execution.py` so the legacy mission executor uses the existing independent action/file postcondition verifiers before appending a step to `completed_steps`. Unsupported or partial verification fails closed; side-effecting outcomes that cannot be established are recorded as requiring review rather than silently accepted. The crash-safe path remains the authoritative durable approval/recovery path.
- Verification: full suite **1,228 passed, 1 skipped, 0 failed** in 70.61 seconds using the repository virtual environment. Ruff and Python compilation passed for the changed/new modules; `git diff --check` passed with only existing line-ending conversion warnings.
- This adds an after-persistence process-kill case and closes the legacy false-success gap, but the crash matrix is not yet exhaustive: a deterministic kill after write-ahead intent and before handler invocation still needs a dedicated seam/test. The non-shell thread timeout issue also remains unresolved: Python cannot forcibly stop an arbitrary running handler thread, so a timeout currently bounds the caller's wait, not necessarily the handler's lifetime or side effects.
- Controlled live browser/desktop/provider acceptance remains outstanding. No held-out material was read or executed. No commit, push, branch change, stash, or destructive Git operation was performed.

## Recovery-stage and deadline-lifecycle follow-up (2026-10-17)

- Added a controlled `before_execute` seam to `CrashSafeMissionRunner` so tests can terminate a real child process after the durable write-ahead intent exists but before the registered handler is called. The new process-kill test confirms restart classifies the step as `needs_review`, leaves the target absent, and keeps `attempt_count=1` rather than replaying an uncertain side effect.
- Combined with existing tests, the tested crash stages now include: during a long-running shell handler, after a real side effect but before result persistence, after the completed step is persisted but before mission finalization, and after write-ahead intent but before handler invocation. Read-only interruption/retry is also covered. This is a representative acceptance matrix, not exhaustive fault injection at every instruction boundary.
- Agent timeout handling now explicitly labels timed-out work **OUTCOME UNKNOWN** and tells callers not to retry automatically without reconciling external state. Added a controlled stalled non-shell handler test proving that (a) the caller times out, (b) an unrelated task can still complete in another worker slot, (c) shutdown returns within a bounded interval, and (d) a handler that ignores cancellation can still perform a late side effect after timeout. The last observation is an intentionally preserved limitation, not a passing claim of hard cancellation.
- Generic in-process Python handlers cannot be forcibly terminated safely by `Future.cancel()`. The caller deadline and bounded `Agent.close()` are enforced, but a stuck handler may continue running; repeated stuck handlers can exhaust the bounded worker pool. Full containment requires a separately designed process-isolation/capability boundary for handlers that can be serialized and safely reinitialized. Do not represent this as solved by the uncertainty message.
- Verification: full suite **1,231 passed, 1 skipped, 0 failed** in 69.66 seconds using `.venv\Scripts\python.exe`; targeted Ruff and Python compilation passed for the changed/new modules; `git diff --check` passed with existing line-ending warnings. No commits, pushes, branch changes, stash operations, or destructive Git commands were performed.

## Normal Agent authorization-path follow-up (2026-10-18)

- Added a real `Agent._process_task` policy-gate regression: a model-shaped task includes `user_confirmed=True` in its arguments for `file.delete`, but the normal Agent path derives confirmation only from the trusted caller parameter. The registered executor is never invoked and the real temporary target file remains unchanged.
- This is distinct from the crash-safe CLI tests: the normal Agent entrypoint and the durable mission entrypoint now each have a direct test that untrusted plan/task data cannot manufacture operator approval.
- Final full-suite verification after this addition: **1,232 passed, 1 skipped, 0 failed** in 74.19 seconds. Targeted Ruff and Python compilation passed for the changed/new acceptance modules. Smoke test passed; `main.py --help` and `mission_crash_safe.py --help` both exited successfully.
- Still unresolved: generic running Python handlers cannot be forcibly cancelled safely in-process, and the controlled test confirms a late side effect can occur after timeout. The next architecture step is process isolation for eligible handlers or an explicit cooperative-cancellation contract with a clear quarantine/reconciliation policy; it must not claim hard cancellation for handlers that ignore cancellation. Live browser/desktop/provider tests and broader legacy-entrypoint authorization enumeration remain open.


## Reachable-entrypoint matrix and process-isolation follow-up (2026-10-18)

- Added `docs/JARVIS_EXECUTION_PATH_MATRIX.md` and `tests/test_reachable_action_matrix.py`. The tests assert the exact 22-handler main Agent registry and 25-action crash-safe registry, verify all main handlers are process-isolated, exercise policy denials for untrusted plugin/MCP/skill sources, test seven nested-shell interpreter patterns, and verify that the legacy CLI's FileTool handler is isolated and workspace-bounded.
- Added `core/executor/isolated_handler.py` and `core/executor/isolated_tool_worker.py`. Main Agent, crash-safe mission, legacy CLI and legacy GUI one-step action handlers now use a child-process boundary. Tool descriptors are serialized by trusted registration code; task arguments are JSON. Unserializable handlers or inability to establish a Windows Job Object fail closed.
- Windows workers use Job Objects. Shell, FileTool, Codex and custom registered handlers use kill-on-close containment; Browser/Windows launch handlers deliberately do not use kill-on-close because the opened app/browser is the expected success side effect. Active timeouts terminate the job tree, but if JARVIS itself is abruptly killed during a browser/app launch, the launched app may remain and the mission outcome must be reconciled. Non-Windows workers use a separate process group.
- The Agent now waits at least until the registered isolated handler's own deadline. A controlled non-shell test confirms the worker is killed before it can perform a delayed write; the real shell child-process regression confirms killing the mission parent terminates the shell child tree. Legacy MissionExecutor now marks side-effecting failures as `needs_review` and refuses to replay persisted `running`/`needs_review` side-effecting steps after restart.
- Automated verification: **1,257 passed, 1 skipped, 0 failed** in 88.68 seconds. Ruff passed on the new/changed execution, mission and test modules; `core/agent.py` passed F-rule lint and Python compilation but has pre-existing broader lint findings. `git diff --check` passed with line-ending conversion warnings only.
- Repeatable controlled live harness: `scripts/controlled_live_acceptance.py --check provider|browser|desktop|all`; the first combined run exposed a harness-only provider import error, which was corrected and rerun provider-only successfully. Browser and desktop checks passed in the first run; they were not repeated to avoid duplicate UI side effects.
- Controlled live acceptance on 2026-10-18: local Ollama `qwen3:8b` returned the expected marker; BrowserTool opened a local loopback URL and the local server observed the HTTP request; WindowsTool launched Notepad as a new process and the test terminated only the newly observed PID. No external network was used. A blank browser tab may remain open after the local test page redirects to `about:blank`.
- Still outstanding: live Codex Desktop CLI integration, any cloud-provider integration, browser visual/page-state verification beyond a loopback request, richer desktop UI interaction, and the low-level generic `ExecutorManager.register_action` API's raw-callback containment contract. Process isolation is not a security sandbox. No commit, push, branch change, stash, or destructive Git operation was performed.


## ExecutorManager containment contract follow-up (2026-10-18)

- `ExecutorManager.register_action(action_name, handler)` remains backward-compatible for existing two-argument callers. Such registrations are explicitly recorded as `legacy-uncontained`, not silently considered safe.
- New side-effecting registrations must use `side_effecting=True`; that mode accepts only `IsolatedToolHandler` and fails closed for raw callbacks. `registration_audit()` reports registered actions, their declared contracts, the uncontained inventory, and a `release_safe` boolean.
- This is an enforceable contract for explicitly classified side-effecting registrations, not an automatic way to infer whether arbitrary Python callbacks have side effects. Existing legacy registrations still require migration/review before a release gate can pass.
- A tool's successful return remains execution output, not proof of a real-world postcondition. Independent action-specific verification is still required.


## Next-phase follow-up (2026-10-18)

- Re-ran the controlled local provider check after the containment-contract changes: Ollama `qwen3:8b` returned the expected marker; `external_network_used=false`; result `passed`.
- Confirmed the Codex CLI executable is installed (`codex-cli 0.162.1`) and inspected its help without submitting a task. This is installation/CLI-surface evidence only, not a live Codex task or cloud-provider integration test. No paid endpoint was called because explicit paid-usage authorization was not supplied.
- Added `docs/JARVIS_RELEASE_GATE.md`, defining evidence required for regression, lint, runtime wiring, action containment, independent verification, crash recovery, adversarial authorization, local provider, browser/desktop, Codex/cloud-provider integration, and exact-candidate release review. Added executor containment modules and focused tests to the CI Ruff list.
- `ExecutorManager.register_action` now preserves the legacy two-argument API but records those registrations as `legacy-uncontained`. `side_effecting=True` rejects raw callbacks and requires `IsolatedToolHandler`; `registration_audit()` reports whether any registrations remain uncontained and detects actions added/replaced directly through the public registry, which would otherwise bypass the declared contract. `IsolatedToolHandler.validate_configuration()` also rejects missing execution methods and unserializable descriptors before a side-effecting registration is accepted. Existing legacy registrations must still be migrated/reviewed before a release gate can pass.
- Final verification after the containment-contract changes: **1,263 passed, 1 skipped, 0 failed** in 87.50 seconds. The hardened-module Ruff list passed, Python compileall passed, smoke test passed without external/state-changing actions, all three CLI help checks passed, and `git diff --check` passed (only existing LF-to-CRLF working-copy warnings).


## Verification-integrity adversarial follow-up (2026-10-18)

- Audit found that some `expected_outcome` branches (`file_exists`, `file_contains`, `url_matches`, `process_running`) could mark the overall verification as `verified` even when the underlying action verifier had returned `failed`, and file/process/URL assertions were not consistently bound to the action's requested target.
- Hardened `mission_control/crash_safe.py`: file assertions must match the requested file path and supported file-producing action; URL assertions must match the URL/site requested by `browser.open_url`/`browser.open_site`; process assertions must match the known executable mapping for the app requested by `windows.open_app`. A `failed` or `partial` independent verifier can no longer be upgraded by these declared assertions.
- Added `tests/test_verification_integrity.py` for unrelated pre-existing files, mismatched URL/app assertions, and attempted upgrades of failed action verification. Focused verifier/crash/restart/runtime set passed **13 tests**, and targeted Ruff passed. Final full-suite verification after the verifier changes: **1,269 passed, 1 skipped, 0 failed** in 93.34 seconds. The hardened-module Ruff list passed, Python compileall passed, smoke test passed without external/state-changing actions, all three CLI help checks passed, and `git diff --check` passed (only existing LF-to-CRLF working-copy warnings). An existing structured `read_file` expected-outcome test initially exposed an overly narrow allowed-action list; `read_file` was added while retaining target binding, and the regression plus full suite now pass.


## Legacy Mission Control GUI approval-path follow-up (2026-10-18)

- Audited the actual PySide6 MissionsView._approve_selected path and confirmed it reloads the mission from SQLite, validates the selected one-based UI step against the persisted plan, and refuses ambiguous text-only approval for duplicate step descriptions.
- Removed duplicated occurrence-approval mutation logic from the GUI and routed it through the shared ApprovalManager.approve_step / approve contract. The GUI still persists the decision through MissionStore; the approval button does not execute the step.
- Added an end-to-end GUI regression covering two identical side-effecting step descriptions: approving occurrence 1 leaves occurrence 2 pending; a new view/store load preserves the indexed decision; repeating approval for the already-approved occurrence does not authorize the other; approving occurrence 2 separately transitions the mission to RUNNING.
- Verification on the current local working tree: focused Mission Control GUI, occurrence-checkpoint and legacy duplicate-step tests: 13 passed. Full suite: 1,277 passed, 1 skipped, 0 failed in 95.30 seconds. Ruff for gui/views/missions_view.py and tests/test_missions_view.py passed; Python compilation passed; git diff --check passed with existing LF-to-CRLF working-copy warnings.
- Remaining limitation: this proves the legacy GUI approval path and persistence semantics for the tested cases. It does not by itself prove every external API/UI entrypoint or real execution route is release-safe; the broader release gate and other-agent working-tree changes remain in scope. No commit, push, branch switch, stash, or destructive Git operation was performed.


### Indexed approval enforcement at execution time (2026-10-18)

- Added runtime-level regression tests for MissionExecutor: indexed approval for each duplicate occurrence is passed into the policy context for that exact index; with only index 0 approved, the first action can run but the second identical action is stopped for approval and is not executed.
- Final full suite after the runtime tests: **1,279 passed, 1 skipped, 0 failed** in 97.21 seconds. Focused approval/GUI/executor tests: **15 passed**. Ruff, py_compile, and git diff --check passed; only pre-existing LF-to-CRLF working-copy warnings were reported.


### MissionControlManager approval API follow-up (2026-10-18)

- Added coverage for the public MissionControlManager.approve_mission_step API. The test verifies one occurrence remains pending after the first approval, stale approval of that same index cannot release the duplicate, each decision is checkpointed/recoverable, and only the final distinct approval resumes the mission executor.
- Latest full-suite result including the API test: **1,280 passed, 1 skipped, 0 failed** in 96.82 seconds. Focused approval tests passed; Ruff and Python compilation passed for the touched GUI and test modules. No commit, push, branch switch, stash, or destructive Git operation was performed.


## Concurrent durable-claim follow-up (2026-10-18)

- Added `test_concurrent_wal_claim_allows_only_one_side_effecting_runner` to `tests/test_crash_safe_missions.py`. Two independent `CrashSafeMissionStore` instances synchronize on a barrier and race to claim the same side-effecting step. Exactly one claim succeeds; the durable row remains `started` with `attempt_count=1`.
- Focused claim + crash-stage tests: **7 passed** in 1.83 seconds. This covers an actual simultaneous SQLite write race between independent store instances, but is not exhaustive cross-process stress testing of every runner lifecycle interleaving.
- Full suite after the regression: **1,281 passed, 1 skipped, 0 failed** in 95.21 seconds.
- Release-gate checks also passed: hardened-module Ruff list, `compileall -q core mission_control tools providers`, smoke test (explicitly reported no external or state-changing actions), `main.py --help`, `mission_crash_safe.py --help`, and `python -m mission_control.cli --help`. `git diff --check` passed; Git emitted only existing LF-to-CRLF working-copy warnings.
- No commit, push, branch switch, stash, or destructive Git operation was performed. Release disposition remains **NOT PROVEN PRODUCTION-READY**: generic legacy-uncontained callbacks, full cross-process/concurrency stress, Codex/cloud integration, richer browser/desktop verification, and other release-gate evidence remain open.
