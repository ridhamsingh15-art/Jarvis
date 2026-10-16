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

## Item 8 — truthful software-engineering mission results

A failed test phase previously only logged a warning, then continued documentation, committed a final checkpoint, and returned `success=True`. The coordinator now raises `TestFailureError` with test counts and failure detail, which the mission boundary reports as `success=False` and stops before docs/final checkpoint. Added regressions for both a failing test phase (no docs/final commit) and a passing phase (normal flow continues). Verification: `pytest -q tests/test_software_engineer.py` → **6 passed, 1 existing collection warning**; Ruff on the coordinator and its tests → all checks passed.

## Item 9 — truthful test telemetry

`TestEngine.run_tests()` used a hard-coded `.venv/Scripts/python` path, had no timeout, and invented `10` tests / `85%` coverage irrespective of actual output. It now runs the current `sys.executable` with a 300-second timeout, parses pytest's terminal outcome summary (including errors/skips/xfails), returns zero/unknown coverage unless coverage is measured, and fails closed on unparseable output or missing test directory. Timeouts and launch errors become failed results without made-up test counts. The old `generate_tests()` no-op now raises `NotImplementedError` instead of silently implying work occurred. Verification: `pytest -q tests/test_test_engine.py tests/test_software_engineer.py` → **13 passed, 1 known collection warning**; Ruff on touched test-engine/model/test files → all checks passed.

## Item 10 — pytest collection warning

Marked the `TestResult` data model with `__test__ = False`, so pytest no longer tries to collect an imported value object as a test class. Added a small regression asserting the model opt-out. Verification: `pytest -q tests/test_software_engineer.py tests/test_test_engine.py` → **14 passed**, with no warning; focused Ruff → all checks passed.

The mandatory full-suite run after items 7–9 initially used a repository-local `--basetemp`, causing three sandbox/path-guard test failures because temp files were placed under the protected repository root. Re-ran unchanged code with an explicit basetemp under `%TEMP%`: **939 passed, 1 warning in 32.53s** (exit 0). The only warning was the `TestResult` collection warning that item 10 is meant to remove.

## Item 11 — fail-closed code generation and review

The software-engineering architecture designer returned a synthetic `StubComponent`, the code generator fabricated placeholder file contents while claiming `compile_success=True`, and reviewers approved any successful-looking result without reviewing it. `ArchitectureDesigner.design()` now raises `NotImplementedError` rather than fabricating a plan; `CodeGenerator.generate()` returns an explicit failed `ImplementationResult` with no diffs/files; `CodeReviewer.review()` withholds approval when review is unavailable; `SecurityReviewer.review()` raises instead of auto-approving. Regression tests cover each behavior and preserve rejection of compilation failures. Verification: focused tests → **11 passed**; Ruff on changed modules/tests → all checks passed.

## Item 12 — honest maintenance-agent results

`DependencyManager.add_dependency()` now validates simple package specifiers, updates only an existing in-workspace `requirements.txt`, is idempotent for an identical requirement, rejects conflicting pins and direct URLs, and returns false rather than success if it cannot update safely; it never installs packages. `DocumentationEngine.document_changes()` and `ReleaseManager.generate_release()` now explicitly raise `NotImplementedError` rather than silently skipping work or returning a fabricated release. `RefactoringEngine.refactor()` returns an unsuccessful result with no fake changes. Verification: focused maintenance-agent/component and coordinator tests → **16 passed**; Ruff on changed modules/tests → all checks passed.

## Item 13 — coordinator validates implementation status

The coordinator previously handed any `ImplementationResult` to the review phase even if `compile_success=False`, relying entirely on the reviewer to notice. It now raises exported `ImplementationFailureError` before adding file paths to the report or invoking review/testing/documentation/final checkpoint. Regression simulates a generator that lists a file it did not write and verifies no later phase is called and no false file is reported. Verification: focused SWE tests → **17 passed**; Ruff on changed coordinator, exception/export, and test files → all checks passed.

## Item 14 — confirmation is an enforcement outcome

`ExecutionPolicy.enforce()` previously raised only on DENY and silently returned for REQUIRE_CONFIRMATION, allowing callers that use `enforce()` as a gate to proceed before explicit approval. It now raises a dedicated `PolicyConfirmationRequired` (a `PolicyDeniedError` subtype) for pending confirmation, while continuing only for ALLOW. Verification: `pytest -q tests/test_execution_policy.py` → **21 passed**; Ruff import/unused-import checks on policy and tests → all checks passed. Existing unrelated SIM102 and silent trace-failure Ruff findings in `core/execution_policy.py` remain unmodified.

## Item 15 — sensitive-file access and rename/copy/move bypasses

`FileTool` previously protected only an exactly lower-case `.env`, `.pem`, and `.key` during direct reads. Added case-insensitive detection for `.env` variants, private-key and credential filenames, key/certificate/database suffixes, SSH/cloud credential directories, Google Cloud ADC, and Windows credential-store paths. Applied the guard to reading, opening, listing sensitive directories, and the source side of rename/copy/move so a secret cannot simply be renamed or copied to a benign filename before reading. Verification: `pytest -q tests/test_file_sensitive_paths.py tests/test_file_tool.py` → **16 passed**; Ruff on touched file code/tests → all checks passed.

## Item 16 — child-process credential sanitization

Expanded shell subprocess filtering beyond a few named API keys to generic `TOKEN`, `SECRET`, `PASSWORD`, `PASSWD`, `API_KEY`/`APIKEY`, `PRIVATE_KEY`, `ACCESS_KEY`, `CREDENTIAL`, `BEARER`, `AUTHORIZATION`, and signing-key fragments, plus common AWS/Azure/GCloud/Kubernetes/Docker/Git-askpass/SSH credential configuration variables. Added a real child-process test proving AWS access keys, Azure client secrets, HF tokens, custom passwords/signing keys, and GitHub personal tokens arrive as `NOT_FOUND`, plus key-pattern unit coverage. Verification: focused shell/security tests → **48 passed**. Existing Ruff debt in `tools/shell.py` remains (silent parse fallback, broad exception fallback, and conditional simplification findings); no unsafe bulk autofix was applied.