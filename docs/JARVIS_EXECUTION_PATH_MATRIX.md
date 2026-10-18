# JARVIS Reachable Execution-Path and Handler-Containment Matrix

Last updated: 2026-10-18

This document records the execution paths found in the current repository and the evidence used to validate them. A passing unit suite is not a production-readiness claim.

## Reachable entrypoints

| Entrypoint | Dispatch path | Policy / approval gate | Workspace / side-effect boundary | Status |
|---|---|---|---|---|
| `main.py` interactive Agent | `Agent._process_task` → `ExecutionEngine` → 22 registered handlers | `ExecutionPolicy`; user confirmation is a trusted caller parameter, not a task argument | Built-in tool handlers use `IsolatedToolHandler`; FileTool workspace is the repository root | Runtime registration and isolated-handler inventory tested |
| `mission_crash_safe.py` / `mission_control.crash_cli.main` | `CrashSafeMissionRunner` → SQLite write-ahead journal → registered handlers | Durable pending approval/review records; only persisted approval resolves the gate | 25 registered actions; handlers isolated; Windows Job Objects for worker/process-tree containment | Real filesystem, policy, crash/restart and journal tests |
| Autonomous goals | `CrashSafeGoalStepExecutor` → `execute_objective` → crash-safe runner | Same policy and durable journal as crash-safe CLI | Same isolated handler registry; step dependencies require independent verification | Real service + SQLite restart acceptance test |
| Legacy Mission Control CLI | `mission_control.cli.run_objective` → legacy `MissionExecutor` | Destructive actions fail closed by default; no automatic approval | FileTool workspace is `Path.home()`; file handlers are isolated | Workspace escape and handler registration tests |
| Legacy GUI “run next step” | `gui.views.missions_view` → legacy `MissionExecutor` | Existing execution policy and explicit UI action | Registered tool handlers now use `IsolatedToolHandler`; interrupted side-effecting steps are not automatically replayed | Static path review plus shared legacy-executor regression tests |
| Legacy MissionExecutor library | `mission_control.execution.MissionExecutor` | `ExecutionPolicy`; `approved_steps` is the legacy approval state | Independent action/file postconditions; stale running side-effect records transition to `needs_review` | False-success, approval-argument and interrupted-step tests |
| Low-level `ExecutorManager.register_action` API | Generic callback registry / worker pool | Caller-defined; this generic API does not itself provide the same capability policy as the Agent and mission runners | Raw callbacks are not automatically serialized into child processes; no production call site was found outside its own definition and tests | Explicit extension API limitation; production side-effecting handlers must be wrapped in `IsolatedToolHandler` |

## Registered action inventories

### Main Agent runtime (22 handlers)

`append_line`, `copy`, `create_file`, `create_folder`, `delete`, `edit_file`, `execute`, `list_directory`, `list_largest_files`, `move`, `open_app`, `open_file`, `open_site`, `open_url`, `patch_file`, `read_file`, `rename`, `run`, `search_google`, `shell_run`, `summarize_files`, `write_file`.

The main Agent's handler registry is asserted in tests and every registered handler must be an `IsolatedToolHandler`.

### Crash-safe mission runtime (25 handlers)

- Browser: `browser.open_site`, `browser.open_url`, `browser.search_google`
- Desktop: `windows.open_app`, `codex_desktop.run_codex_task`
- File mutations: `file.append_line`, `file.copy`, `file.create_file`, `file.create_folder`, `file.delete`, `file.edit_file`, `file.move`, `file.patch_file`, `file.rename`, `file.write_file`
- File read/query: `file.directory_file_stats`, `file.ensure_text_files`, `file.extension_counts`, `file.list_directory`, `file.list_directory_details`, `file.list_largest_files`, `file.open_file`, `file.read_file`, `file.summarize_files`
- Shell: `shell.run`

The exact set is asserted by `tests/test_reachable_action_matrix.py`. The legacy CLI registers only FileTool actions.

## Adversarial acceptance coverage

- All ten filesystem mutation actions are tested against workspace traversal in the real crash-safe runner: `create_file`, `write_file`, `append_line`, `patch_file`, `edit_file`, `create_folder`, `rename`, `move`, `copy`, and `delete`.
- Rename traversal is tested after durable approval; approval does not bypass the workspace boundary.
- The normal Agent and legacy MissionExecutor tests prove that a model/task argument such as `user_confirmed=True` does not itself authorize deletion.
- Untrusted plugin/MCP/skill source checks deny destructive file actions and shell execution, even when the context carries a confirmation-shaped flag.
- Nested `cmd`, PowerShell, pwsh, bash, and sh command interpreters are tested against the shell hard-deny policy.
- A success-shaped fake tool result cannot mark a mission complete when the target file is absent.
- Crash-stage tests kill real child processes before handler invocation and after completed-step persistence. Uncertain side-effecting legacy steps are now marked `needs_review` instead of automatically replayed.
- A controlled non-shell handler attempts a delayed filesystem write after timeout; its isolated worker is terminated and the delayed write does not occur.
- A real shell child-process test verifies that killing the crash-safe mission parent also terminates the shell child tree.

## Handler-containment contract

- `IsolatedToolHandler` serializes a trusted registered tool descriptor separately from JSON task arguments and invokes the tool in a child Python process.
- If a tool instance cannot be serialized or the Windows Job Object cannot be established, execution fails closed before invoking the tool.
- On Windows, the worker is assigned to a Job Object before task data is sent to it. Shell, file, Codex and custom workers use kill-on-close containment so abrupt JARVIS process termination cannot leave their worker trees alive. Browser and Windows launch handlers use a non-kill-on-close Job Object because a successfully opened browser/app is an intended side effect; a timeout while the parent is alive still terminates the active job tree. If JARVIS itself is killed during a browser/app launch, the launched application may remain, and the durable mission must be reconciled rather than assumed complete.
- On non-Windows platforms, the worker starts in a separate process group and timeout handling sends a group kill.
- The Agent caller waits at least as long as the registered isolated handler's deadline. This prevents a shorter caller timeout from returning while the worker is still alive.
- A timeout is **OUTCOME UNKNOWN**. It is not proof that the external effect did not happen. The mission must remain failed or `needs_review` unless the expected postcondition is independently verified.
- Process isolation is not a security sandbox: the worker runs with the same user privileges. FileTool and ShellTool policy/workspace restrictions, trusted approval provenance, output validation and independent postcondition checks remain required.

## Known limitations / not yet verified

- `ExecutorManager.register_action` remains a low-level generic callback API for tests and extension code. The API now accepts `side_effecting=True` only for `IsolatedToolHandler` registrations, validates the tool method and descriptor serialization before accepting them, and exposes `registration_audit()` for a release gate. The audit also detects entries added/replaced directly through the public registry. Two-argument registrations remain source-compatible but are marked `legacy-uncontained`; callers must migrate or explicitly justify them before release. This preserves existing tests/extensions without silently claiming that legacy callbacks are contained.
- Repeatable live harness: `scripts/controlled_live_acceptance.py --check {provider|browser|desktop|all}`; run categories separately to avoid repeating browser/desktop side effects.
- Controlled live acceptance on 2026-10-18 passed for the configured local Ollama provider (`qwen3:8b`, expected response marker observed), BrowserTool `open_url` (a real browser GET reached a local loopback HTTP server), and WindowsTool `open_app` (a newly created Notepad PID was observed and only that new PID was terminated). No external network was used. The browser test page redirects to `about:blank`; a blank tab may remain open.
- This live run does not verify arbitrary external websites, visual page state, richer desktop interaction, Codex Desktop CLI execution, or cloud-provider credentials/endpoints. Those remain separate integration targets.
- Independent verification is action-specific. Unsupported, ambiguous or partial outcomes must fail closed; a handler's own success string is never enough.
- Latest full automated suite at the prior checkpoint: **1,257 passed, 1 skipped, 0 failed** in 88.68 seconds; this historical result was superseded on 2026-10-18 by the hardening-status log below. Ruff passed for the changed/new modules except `core/agent.py`, where the file has pre-existing E402/E501/SIM102/BLE001 baseline findings; the changed Agent file passed F-rule lint and Python compilation. `git diff --check` passed with existing line-ending conversion warnings.
- Concurrent WAL-claim regression: two independent `CrashSafeMissionStore` instances synchronize and race to claim the same side-effecting step. Exactly one `begin_step` succeeds and the persisted `attempt_count` remains 1. This proves atomic single-step claiming under the tested two-thread race; it is not a substitute for cross-process stress testing or every runner lifecycle race.
- JARVIS is not declared production-ready. Process isolation is not a sandbox and the generic `ExecutorManager` callback API remains outside the main runtime's automatic isolation contract.
