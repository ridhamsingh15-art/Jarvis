# Audit Notes — 2026-10-17

## Preserved pre-existing work

Before editing code, the worktree contained 102 modified tracked files plus many untracked files. I preserved them with `git stash push -u -m 'preserve pre-audit worktree 2026-10-17'` and created the reference `backup/pre-audit-working-tree-20261017` pointing at the saved snapshot (`5d12a64cdf315bb7465507f0cde4949ac7774e21`). The stash remains as `stash@{0}` too. Review that snapshot before restoring it over future changes; do not drop the stash or delete the backup branch. `jarvis_test_workspace/` remained untracked after the stash and has been left untouched.

## Verified baseline

- Branch: `feature/jarvis-control-center`; HEAD at audit start: `9fd4956 security: harden desktop bridge request handling`.
- Pre-preservation working-tree full suite: `1403 passed in 75.27s`.
- Clean HEAD full suite: `922 passed, 1 failed, 1 warning in 34.14s`; failure: `tests/test_codex_desktop.py::test_codex_timeout_exceeds_subprocess_timeout`, which calls missing `ExecutionEngine.timeout_for_task`.
- Clean HEAD `ruff check . --statistics`: `Found 1157 errors`; `782` marked safe-fixable. Major categories included 282 unused imports, 277 import-order findings, 122 blind-except findings, 91 legacy annotations, 41 unused unpacked variables, 39 broad try/except-pass patterns, 32 unused variables, and 29 undefined names. The original uncommitted worktree reported 1,376 errors; this is not directly comparable to the clean-HEAD baseline.
- Clean-HEAD `F821` findings: 29, concentrated in `core/agent.py`, `core/cognition/context_orchestrator.py`, `core/executor.py`, and `core/planner.py`. The `TaskStatus` references in `core/executor.py` can reach runtime paths.
- `PLW1510` identified six `subprocess.run` calls without explicit `check=` policy. OS-specific skips in pairing-store and Windows process tests were conditional by design; the scan also found two `NotImplementedError` occurrences in test doubles, not unfinished production methods.
- The broad static scan traversed a nested third-party virtual environment under `tools/toutatis`; its upstream TODO/FIXME markers are not JARVIS-owned findings and are excluded from the task list.

## Known unaddressed audit scope

The full Ruff backlog is not equivalent to 1,157 demonstrated defects. This pass prioritizes confirmed test failure, undefined-name references, orchestration hangs, invalid dependency/retry inputs, duplicate imports, and explicit subprocess exit handling. Remaining Ruff findings must not be described as clean or resolved unless rerun and fixed. No live provider/API or authenticated desktop end-to-end test has been performed as part of this baseline.

## Item 1 — handler-specific timeouts

Implemented `ExecutionEngine.timeout_for_task`, validating handler timeout overrides and falling back safely for missing handlers or invalid values. Wired the resolved limit into `TaskDispatcher` before it creates the execution context, while preserving larger explicit time budgets and leaving tasks without a configured timeout unbounded when their handler has no override. Verification: `pytest -q tests/test_codex_desktop.py` → **8 passed**; Ruff check of the three touched executor files and this test file → **all checks passed**. Changes are ready for the per-item commit.

## Item 2 — undefined names

Added the missing `Any` bindings in `core/agent.py` and `core/planner.py`, imported `ExecutionPlan` for the context orchestrator annotation, and imported `TaskStatus` for executor lifecycle checks (the latter was a runtime NameError on executor branches). Verification: `pytest -q tests/test_executor.py tests/test_context_orchestrator.py tests/test_planner.py tests/test_agents.py` → **17 passed**; `ruff check core --select F821` → **all checks passed** (0 undefined-name findings).

## Item 3 — dependency integrity

`DependencyGraph.detect_cycles()` now rejects references to missing node IDs and orphaned dependency-map entries before cycle traversal. Added tests for a missing dependency and a valid prerequisite/dependent pair. Verification: `pytest -q tests/test_orchestrator.py` → **5 passed**; Ruff on `agents/orchestrator` and `tests/test_orchestrator.py` → all checks passed.

Full-suite gate after items 1–3: `pytest -q` → **926 passed, 1 warning in 32.91s** (exit 0). The warning is the existing pytest collection warning for the dataclass `TestResult` in `applications/software_engineer/models.py`.

## Item 4 — scheduler no-progress termination

Changed `WorkflowScheduler.run_graph()` so that after all spawned executor tasks have been awaited, any still-pending nodes with incomplete dependencies and any stale RUNNING nodes become FAILED with diagnostic results; checkpointing and status logging happen before the scheduler exits. This replaces the previous endless 10 ms polling loop. Regression test exercises a failing prerequisite with a dependent node under a 0.5-second timeout. Verification: `pytest -q tests/test_orchestrator.py` → **6 passed**; focused Ruff → all checks passed.

## Item 5 — retry-count validation

`WorkflowNode.validate()` now rejects boolean, non-integer, zero, and negative retry counts at construction so `WorkflowExecutor` cannot leave a node RUNNING because `range(retries)` was empty. Added tests for zero, negative, and valid one-retry cases. Verification: `pytest -q tests/test_orchestrator.py` → **9 passed**; focused Ruff → all checks passed.

## Item 6 — duplicate definitions

Removed two redundant local `core.context_budget` imports from `ConversationEngine` (module-level imports already provide the names) and the repeated local `MagicMock` import in the World Model test. Verification: `pytest -q tests/test_conversation.py tests/test_world_model.py` → **29 passed**; `ruff check . --select F811` → all checks passed (0 findings).

## Item 7 — subprocess exit-code policy

Added explicit `check=False` to all six `subprocess.run` sites flagged by Ruff. These call sites intentionally inspect `.returncode` and handle test failures, missing Git repos, or shell failures themselves, so raising `CalledProcessError` would change intended behavior. Verification: `ruff check . --select PLW1510` → all checks passed; `py_compile` passed for all six edited files; focused tests `tests/test_software_engineer.py`, `tests/test_world_model.py`, `tests/test_shell_tool.py` → **52 passed, 1 existing warning** using a unique repository-local pytest basetemp after the default temp cleanup hit a Windows access-denied error (`pytest-current`).