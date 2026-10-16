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

## Item 17 — immutable shared defaults

Changed image/prompt adapter registry dictionaries to `MappingProxyType`, project required-directory defaults to a tuple, and mission-verifier default checks to a tuple. Added regressions verifying registry lookup remains functional, registry maps cannot be mutated, storage defaults cannot be appended to, and verifier instances don't share mutable per-instance checks. Verification: `pytest -q tests/test_immutable_shared_defaults.py tests/test_phase7c_mission_verification.py` → **22 passed**; `ruff check . --select RUF012` → all checks passed (0 findings).

## Item 18 — core failure observability

Optional runtime tracing previously swallowed exceptions without a diagnostic, and malformed persisted experience records were silently skipped at startup. The core agent's malformed-script fallback, context-budget/policy tracing, both ModelRouter trace paths, LLM observability export, tool-loop tracing, and persisted-experience loading now emit safe debug/warning entries containing only exception type or record index—not raw prompts, tokens, or corrupted payloads. Optional telemetry remains non-fatal. Verification: `pytest -q` on seven related suites → **82 passed**; targeted Ruff `S110,S112` across the touched core modules → all checks passed.

## Item 19 — fail-closed path resolution in shell boundary checks

`ShellTool._check_workspace_boundary()` previously continued to the next token when resolving a tokenized path raised an exception, effectively skipping validation for that token. It now blocks the command whenever an absolute path cannot be safely resolved and logs only the exception type, not the path payload or error message. Regression simulates a symlink-resolution failure and verifies no command executes and the detail is not echoed. Verification: focused shell/security tests → **47 passed**; targeted Ruff `S112,F821,F811,PLW1510` on shell and regression test → all checks passed.

## Item 20 — core safe lint cleanup

Applied Ruff's safe F401/I001 fixes under `core/` only: **168 findings removed across 117 files**. Reviewed the aggregate diff; it contains import removals/reordering and related `__all__` ordering only, with no unsafe fixes requested. Verification: `git diff --check` passed; `ruff check core --select F401,I001` passed with zero findings; focused core tests → **64 passed in 6.60s**. Global Ruff baseline-to-current now **1,157 → 880 findings** (overall, includes remaining non-import style/exception-handling work); critical `F821,F811,PLW1510,RUF012` remain clean.

## Item 21 — applications safe lint cleanup

Applied Ruff safe F401/I001 fixes under `applications/` only: **137 findings removed**. Verification: `git diff --check` passed; `ruff check applications --select F401,I001` passed with zero findings; focused SWE, test-engine, animation/image/video/voice/storyboard/script and project-manager tests → **56 passed in 2.19s**.

## Item 22 — tests and remaining first-party modules safe lint cleanup

Applied Ruff safe F401/I001 fixes under `tests/`, `agents/`, `gui/`, and `tools/`, excluding the third-party `tools/toutatis` subtree. **207 findings removed**. Verification: `git diff --check` passed; targeted Ruff F401/I001 across all included paths passed with zero findings; focused agent/bootstrap/file/shell/plugin/MCP/integration/voice/SWE/content-factory tests → **135 passed in 13.21s**. Some test files lost unused imports only; behavior was checked by the focused test run and will receive the required full-suite gate now.

## Full-suite gate after items 20–22

`pytest -q --basetemp %TEMP%\pytest-jarvis-full-after-import-cleanup` → **975 passed in 33.22s**, exit 0, no warning summary. Whole-repo Ruff at that gate: **532 findings** (down from 1,157 clean-HEAD baseline); F821/F811/PLW1510/RUF012 all clean. The first-party safe import subset (`core applications tests agents gui tools`, excluding the untracked third-party `tools/toutatis` tree) also now reports zero F401/I001 findings.

## Item 23 — entrypoint and scripts safe lint cleanup

Applied Ruff's safe F401/I001 fixes to `main.py`, tracked `scripts/`, and tracked `workspace/` helpers only. The pre-existing untracked `jarvis_test_workspace/` remains untouched; its 3 import-order/unused-import findings are still included in an unfiltered `ruff check .`. Verification: `git diff --check` passed; targeted F401/I001 passed; `compileall` passed for `main.py scripts workspace`; `python main.py --help` succeeded; startup/evaluation/phase regression tests → **152 passed in 6.47s**.

## Observability follow-up

Completed three optional-failure logging edits that were left unstaged after the earlier core-observability item: ComfyUI history polling now logs a debug retry diagnostic; n8n failure-reporting logs the exception type if marking a mission failed itself fails; SQLite mission-repository path discovery logs a safe debug diagnostic before falling back to the supplied connection. Verification: `pytest -q tests/test_comfyui.py tests/test_mission_persistence.py tests/test_mission_control.py` → **12 passed**; Ruff `F821,F811,S110,S112` on the three modules → all checks passed.

## Item 24 — safe typing modernization

Applied only Ruff safe fixes for `UP006,UP035,UP045,UP037,UP007` across first-party Python paths (excluding third-party `tools/toutatis`), fixing **175 typing findings**. Ruff also exposed unused typing imports/order changes caused by these transformations, so a second safe F401/I001 pass removed **86 follow-on import findings**. Verification: first-party `compileall` passed; full test suite → **976 passed in 32.30s**, exit 0; first-party F401/I001 → zero; critical F821/F811/PLW1510/RUF012 → zero. Ruff still reports 46 UP035 findings that its normal safe fixer will not rewrite, so those were intentionally left for manual compatibility review. Global lint is **1,157 baseline findings → 412 current findings**; the remaining global count includes code outside this checklist, including untracked local benchmark files and third-party content.

## Item 25 — shell command chaining and nested-shell defense

Added a quote-aware pre-execution shell-syntax guard before `subprocess.run(shell=True)`. It blocks unquoted separators/pipes/redirects, multiline/control characters, shell command substitution, unmatched quotes, direct launches of `cmd`/PowerShell/bash/sh/wsl interpreters, and cmd.exe `%VAR%`/`!VAR!` expansion on Windows. Quoted Python `-c` snippets and pytest arguments remain supported; the existing non-zero exit-code test now uses Python rather than launching a nested `cmd.exe`. Regression tests prove chained commands are blocked before subprocess launch and cover quoted arguments and Windows expansion. Verification: Ruff on `tools/shell.py` and affected tests → clean; focused shell/security suites → **69 passed in 11.01s**. This is defence-in-depth, not an OS-level sandbox for running arbitrary project code.

## Item 26 — ShellTool configuration and timeout validation

`ShellTool` now rejects invalid default timeouts (zero/negative/non-finite/boolean/unparseable) and output caps that are not positive integers, including booleans. Runtime timeout overrides are normalized from numeric values or numeric JSON strings, but malformed, zero, negative, non-finite, boolean, and other object values return a blocked `ShellResult` before invoking a subprocess. Empty/non-string commands also fail closed. Verification: Ruff on the modified shell module and its regression test → clean; focused shell/security suites → **100 passed in 11.12s**.