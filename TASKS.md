# Audit-Derived Reliability Tasks

Baseline: clean `feature/jarvis-control-center` HEAD, commit `9fd4956`. On 2026-10-17, the full suite reported **922 passed, 1 failed** (`tests/test_codex_desktop.py::test_codex_timeout_exceeds_subprocess_timeout`); `ruff check . --statistics` reported **1,157 findings**, 782 marked safe-fixable. The pre-preservation worktree separately passed 1,403 tests but contained extensive uncommitted code/tests; that snapshot is preserved on `backup/pre-audit-working-tree-20261017` and is not mixed into this clean baseline.

- [x] **Timeout policy:** implement handler-specific timeout resolution in `ExecutionEngine` and apply the selected timeout to dispatched `ExecutionContext` tasks; pass `tests/test_codex_desktop.py::test_codex_timeout_exceeds_subprocess_timeout` plus default-timeout coverage.
- [x] **Undefined names:** resolve all 29 Ruff `F821` findings under `core/` (currently missing `Any`, `ExecutionPlan`, and `TaskStatus` bindings); verify `ruff check core --select F821` and affected unit tests.
- [x] **Dependency integrity:** make `WorkflowBuilder.build()` reject dependencies that reference missing node IDs; add tests for missing and valid dependencies.
- [x] **Workflow termination:** prevent `WorkflowScheduler.run_graph()` from spinning forever when upstream nodes fail and dependent nodes remain pending; add a dependent-failure regression test that completes within a bounded timeout.
- [x] **Retry validation:** reject `WorkflowNode.retries < 1` at construction; test zero and negative retry counts and preserve normal retries.
- [x] **Duplicate definitions:** remove the four Ruff `F811` redefinition findings in `core/cognition/conversation.py` and `tests/test_world_model.py`; run the focused tests and `ruff check . --select F811`.
- [x] **Subprocess result handling:** add an explicit `check=` policy to all six Ruff `PLW1510` call sites; preserve intentionally handled non-zero return codes and test affected behavior.
- [x] **Truthful mission outcome:** make `SoftwareEngineeringCoordinator.execute_mission()` fail the mission when its test phase reports failures, and prevent documentation/final commit from running afterward; add success/failure regressions.
- [x] **Truthful test telemetry:** replace fabricated `TestResult` counts and hardcoded coverage in `TestEngine.run_tests()` with parsed pytest results, use `sys.executable`, and bound subprocess duration; add tests for pass/fail/collection error/timeout; make `generate_tests()` fail explicitly while unimplemented instead of silently doing nothing.
- [ ] **Pytest collection warning:** prevent the imported domain model `TestResult` from being collected as a test class; verify the full suite no longer emits the warning.
