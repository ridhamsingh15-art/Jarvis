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

## Full-suite gate after items 25–27

`pytest -q --basetemp %TEMP%\pytest-jarvis-full-after-item27` → **1,028 passed, 1 skipped in 31.93s**, exit 0. The skip is the environment-conditional directory-symlink test when the platform does not allow symlink creation.

## Item 27 — workspace-relative working directory

`ShellTool._resolve_cwd("subdirectory")` previously resolved relative to the application process's current directory rather than `workspace_root`, so legitimate workspace-relative working directories were rejected and behavior depended on where JARVIS was launched. It now resolves relative overrides against the configured workspace, then resolves symlinks and requires the final location to remain inside the workspace. Traversal, absolute outside paths, and symlink escapes remain rejected; invalid/path-resolution exceptions fail closed. Verification: focused shell suites → **102 passed, 1 skipped**; Ruff on `tools/shell.py` and the new cwd tests → clean; full suite after items 25–27 → **1,028 passed, 1 skipped**.

## Item 28 — repository analyzer correctness and diagnostics

Reworked `RepositoryAnalyzer` to prune exact generated/environment directory names (fixing the prior substring bug that excluded `.github`), detect `if __name__ == "__main__"` using AST instead of string matching, and report safe parse/read diagnostics without dumping exception contents. Requirements parsing now ignores comments, options, direct URL/VCS references, and malformed package-name lines while preserving common version/extra/marker forms. Regression tests cover `.github`, similarly named directories, excluded `.venv`, AST entry points, dependency parsing, and syntax-error recovery. Verification: Ruff clean; software-engineering + analyzer tests → **20 passed in 0.16s**.

## Item 29 — application permission enforcement

Replaced the application permission manager's unsafe stub (`check_permission` always returned `True`, and `grant_permissions` only logged) with an adapter to the core plugin permission authority. It now requests permission review without granting access, verifies every requested permission against explicit grants, denies when the backend is missing/unavailable, and raises `AppPermissionError` if required grants are absent. Installer/updater convert that expected denial into a normal failed result; updates retain rollback behavior. Added tests for unavailable backend, no implicit grant, explicit grant, and permissionless apps. Verification: Ruff F821/F811 clean and safe import/format fixes applied; application + SWE regression tests → **24 passed in 0.37s**. Full-suite verification follows.
## Fresh audit — 2026-10-17 (verified in this session)

- Actual repository: `C:\Users\ridha\Projects\Jarvis`, branch `feature/jarvis-control-center`, HEAD `c720084 fix(swe): harden repository analysis`.
- `git log --oneline -20`, `git status --short --branch`, and `git diff --stat` were run. The worktree already had modified `core/applications/installer.py` and `core/applications/permissions.py`, plus untracked `jarvis_test_workspace/` files. These edits were not created by this audit and remain untouched; audit commits must stage only explicitly named audit files.
- Baseline full suite: `.venv\Scripts\python.exe -m pytest -q --basetemp %TEMP%\pytest-jarvis-audit-20261017` → **1031 passed, 1 skipped in 33.86s**, exit 0.
- Baseline Ruff: `.venv\Scripts\ruff.exe check . --statistics` → **275 findings**. The largest group is 103 `BLE001` broad catches, followed by 41 `RUF059`, 32 `F841`, 25 `S110`, 15 `RUF022`, 12 `SIM102`, and 46 `UP035` (Ruff's complete output also includes smaller categories; the exact baseline output is in this session).
- `ruff check . --select E722,B019,S110,S112,BLE001 --output-format concise` found 131 findings in those selected rules: 103 `BLE001`, 25 `S110`, 2 `E722`, and 1 `B019`. The `B019` finding is `IdentityManager.build_planner_prompt` using `functools.lru_cache` on an instance method, which keys by `self` in a function-level cache and can retain manager instances. Two bare exception handlers are in optional environment probing in `scripts/evaluate_intelligence.py`.
- `ruff check applications core scripts mission_control tools --select S110 --output-format concise` found 24 production `S110` sites (a further `S110` exists in tests). These best-effort paths silently discard failures; the task list will add safe diagnostics rather than raw exception messages.
- Test skip scan found one conditional test in `tests/test_shell_operator_guard.py` for Windows-specific `%VAR%`/`!VAR!` behavior. No unconditional skip/xfail was identified in the visible scan.
- No first-party TODO/FIXME/HACK/XXX marker was confirmed by the initial scan; the scan also traversed `.jarvis_backups` and found old backup copies, so those are not treated as current source. A docs example containing `todo.txt` is not a TODO marker.
- Several `NotImplementedError` paths are explicit fail-closed responses for unsupported software-engineering capabilities, rather than false-success stubs. They remain a documented capability limitation unless tests or call paths show that an advertised workflow falsely claims completion.
- Audit caution: prior NOTES/TASKS history contains historical test and Ruff counts from different commits and worktree snapshots. The counts above are the authoritative baseline for this session; historical figures are not comparable without matching commit/worktree state.


## Task 1 ? per-instance identity prompt cache

Replaced the shared method-level `functools.lru_cache` with a bounded 16-entry LRU-style dictionary owned by each `IdentityManager`. This preserves prompt reuse and eviction behavior without the function-level cache retaining manager instances across their lifetimes. Added regressions for cache hits, capacity, and least-recently-used eviction. Verification: `pytest -q tests/test_identity.py` ? **22 passed in 0.16s**; Ruff on `core/identity/manager.py` and `tests/test_identity.py` ? all checks passed; `ruff check . --select B019` ? all checks passed (0 findings).


## Task 2 ? explicit environment-probe exceptions

Replaced both bare `except:` clauses in `scripts/evaluate_intelligence.py` with the expected `OSError`, `subprocess.CalledProcessError`, and `subprocess.TimeoutExpired` exception types. Missing tools and failed/timed-out probes still produce the existing `unavailable` fallback; unexpected programming errors are no longer silently hidden. Verification: `python -m py_compile scripts/evaluate_intelligence.py` passed; `ruff check scripts/evaluate_intelligence.py --select E722` passed with zero findings; `pytest -q tests/test_evaluation.py` ? **14 passed in 0.12s**; `git diff --check` passed.


## Task 3 ? observable best-effort failures and SQLite cleanup

Replaced all 24 production `S110` try/except/pass sites in `applications/`, `core/`, and `scripts/` with debug diagnostics that record only the exception type, preserving best-effort behavior without exposing exception payloads. Removed the broad swallowed cleanup exception in `tests/test_second_pass_routing.py`. That exposed a real Windows file-lock failure: `SqliteMissionRepository` did not offer a way to close the current thread's SQLite connection before the temporary database file was removed. Added `close()` for the calling thread's connection and updated the regression test to close it explicitly; this preserves the repository's per-thread connection model. Verification: focused suites (`test_animation_engine`, `test_image_engine`, `test_script_engine`, `test_storyboard_engine`, `test_video_engine`, `test_voice`, `test_voice_engine`, `test_mission_persistence`, and `test_second_pass_routing`) ? **24 passed in 1.04s** after the cleanup fix; `ruff check applications core scripts mission_control tools --select S110` and the test-file `S110` check ? all checks passed; mandatory full suite after items 1?3 ? **1037 passed, 1 skipped in 33.05s**, exit 0. Whole-repo Ruff is now **243 findings**, down from the audited baseline of 275.

The first focused run before the repository-close fix reported 50 passed and one failure due to `PermissionError` deleting the SQLite file. That failure was not ignored; the repository lifecycle and test were corrected, then the focused suite and full suite were rerun successfully.


## Task 4 ? public asset-path facade

Added `ProjectManager.get_asset_absolute_path()` as a public delegation to the existing `AssetManager` API and updated `AssetPipeline` to use it instead of reaching into `ProjectManager._storage`. The image-engine fixture also contained an unused `ImageEngineManager` construction; removed that dead setup and its now-unused import. Verification: `pytest -q tests/test_image_engine.py tests/test_project_manager.py` ? **9 passed in 1.83s**; Ruff on all three changed Python files ? all checks passed; `git diff --check` passed.

## Capability and marker audit

The current-source scan found one actionable `# Hack` in `applications/content_factory/image_engine/asset_pipeline.py`, now removed by Task 4. Other `NotImplementedError` paths are explicit, truthful refusals for still-unimplemented architecture design, automated documentation writing, release-summary generation, automated security review, and automated test generation. These are real capability blockers for those workflows, but their code does not falsely claim success; they remain limitations rather than safe candidates for speculative implementation in this audit. The one test skip is the Windows-only shell expansion case and is correctly guarded by `skipif`. No active first-party TODO/FIXME marker was confirmed in current source; the marker scan also sees historical backup copies, which are not current code.


## Task 5 ? final regression gate

Final verification after all code changes: `python -m pytest -q --basetemp %TEMP%\pytest-jarvis-final-<unique>` ? **1037 passed, 1 skipped in 32.63s**, exit 0. `ruff check . --statistics` ? **242 findings**, down from **275** at the session baseline (33 fewer). `ruff check . --select E722,B019,S110` ? all checks passed; first-party `compileall` passed; `git diff --check` passed. The one skip remains the expected OS-conditional Windows shell-expansion test. Current-source final review shows no remaining bare `except:`, no `B019` cache finding, and no `S110` silent except/pass findings in the audited production paths. Final tracked worktree is clean after the documentation commit; the pre-existing untracked `jarvis_test_workspace/` remains untouched.

## Remaining audit findings / limits

The global Ruff backlog remains **242 findings**, mainly `BLE001` 102, `RUF059` 41, `F841` 31, `RUF022` 15, `SIM102` 12, `PIE790` 10, and 46 `UP035` findings included in the broader rule set/output. These were not bulk-autofixed: broad exception handlers and unused assignments require call-site review to avoid changing failure semantics, while import ordering/typing/style items are lower priority than demonstrated correctness issues. They are recorded for a future focused lint pass rather than claimed clean. No live authenticated provider/API or desktop end-to-end test was run; those require external services and are not represented by the local pytest suite.

## Worktree preservation note

At initial audit, `core/applications/installer.py` and `core/applications/permissions.py` were modified in the worktree. They were not staged by this audit's commits. By final review, their changes appeared in the repository history as `ad2fe74 fix(security): enforce application permission grants`; the current worktree has no tracked modifications. The pre-existing untracked `jarvis_test_workspace/` directory was never modified or added to commits.


## Executor lifecycle task 1 ? preserve queued tasks on shutdown

The new regression reproduced task loss: the dispatcher dequeued a task, found no worker, and discarded the task when shutdown set its stop event. Added a dispatch critical section shared with shutdown and explicit requeueing whenever a task has been dequeued but no worker accepted it. This keeps its persisted status QUEUED and leaves it available for a later dispatcher start. Verification: the regression failed before the fix because the queue was empty; `pytest -q tests/test_dispatcher_lifecycle.py` ? **1 passed in 0.18s**; Ruff on `core/executor/dispatcher.py` and the regression test ? all checks passed; `git diff --check` passed.


## Executor lifecycle task 2 ? cooperative cancellation and bounded joins

`WorkerThread.stop()` now cancels the current context token, and the worker loop consumes any already-assigned context after shutdown only to emit a cancellation result instead of abandoning a RUNNING task. Assignments to stopped/busy workers are rejected. `WorkerPool.shutdown(timeout=...)` signals all workers, joins against one shared deadline, prunes exited threads, and retains still-alive workers for accurate diagnostics; idle/busy counts now reflect actual worker states. Also fixed a latent cancellation path that accessed nonexistent `CancellationToken.reason`, and kept result-duration timestamps on the wall-clock basis expected by `ExecutionResultBuilder`.

Verification: before the fix, the new cooperative-shutdown test failed with `AttributeError` for the nonexistent token `reason`; after the fix, `pytest -q tests/test_worker_pool_lifecycle.py tests/test_executor.py tests/test_runtime.py` ? **11 passed in 5.40s**; Ruff on worker, pool, and tests ? all checks passed. The unresponsive-worker test proves shutdown respects a short deadline, retains the still-alive thread in stats, and prunes it once it exits. `git diff --check` passed.


## Executor lifecycle task 3 ? close all path-backed SQLite handles

The mandatory full-suite gate found an intermittent Windows `PermissionError` when deleting a temporary SQLite database after `SqliteMissionRepository` was used from five threads. `close()` only closed the calling thread's connection, while path-backed connections created with `check_same_thread=False` could remain registered through thread-local state. The repository now tracks each thread's connection, closes all tracked path-backed handles under the repository lock, and detects stale local references so a later access cannot reuse a closed handle. Factory-created connections remain closed per calling thread to respect potentially thread-affine factories.

Verification: the first full-suite gate after executor changes found **1 failure, 1040 passed, 1 skipped in 33.34s** (`test_bug_3_sqlite_thread_safety` file deletion). After the fix, `pytest -q tests/test_second_pass_routing.py tests/test_mission_persistence.py` ? **24 passed in 1.02s**; the multi-thread SQLite regression passed **5/5 repeated isolated runs** (0.89?0.93s each); Ruff on `core/mission/repository.py` passed; `git diff --check` passed. The full-suite gate will be rerun after the scoped fixes.


## Executor lifecycle ? final regression gate

Final full-suite run after dispatcher, worker-pool, and SQLite handle fixes: `python -m pytest -q --basetemp %TEMP%\pytest-jarvis-executor-final-<unique>` ? **1041 passed, 1 skipped in 32.60s**, exit 0. Targeted Ruff on executor lifecycle and mission repository files passed; `ruff check . --select E722,B019,S110` passed; `compileall -q core\executor core\mission` passed; `git diff --check` passed. Whole-repository Ruff remains **242 findings**, unchanged from the previous recorded baseline; no claim of a clean global lint run is made. The expected single platform-conditional skip remains. The temporary SQLite file-lock failure found at the first full-suite gate was fixed and the final full suite passes.


## Agent timeout task 1 ? isolate late completions

The new regression reproduced a timeout race: `_execute_task` submitted the same mutable `Task` object that it later marked FAILED on timeout. The still-running executor then attempted to complete that already-failed object. The execution path now submits a detached dataclass snapshot with a deep-copied argument dictionary and copied failure history. A result is copied back to the caller's task only if the future returns before the timeout; on timeout, `future.cancel()` is attempted and the returned task remains FAILED even if the underlying action finishes later. This prevents late completion from mutating the caller-visible status. It does **not** forcibly terminate an already-running Python thread or reverse external side effects; the executor API has no cooperative cancellation token for this path.

Verification: the regression failed before the fix because the executor received the exact same task object; after the fix, `pytest -q tests/test_agent_timeout_isolation.py tests/test_phase7a_runtime_spine.py` ? **13 passed in 1.16s**. Targeted execution-path lint identified pre-existing findings in `core/agent.py`; only the newly introduced import-order issue was corrected. `git diff --check` is checked before commit.


## Agent timeout isolation ? final regression gate

Final full suite after task snapshot isolation and future tracking: `python -m pytest -q --basetemp %TEMP%\pytest-jarvis-agent-final-<unique>` ? **1043 passed, 1 skipped in 32.76s**, exit 0. `ruff check core/agent.py tests/test_agent_timeout_isolation.py --select I001` passed; `ruff check . --select E722,B019,S110` passed; `compileall -q core/agent.py` passed; `git diff --check` passed. Whole-repository Ruff remains **242 findings**; changed-file checks were scoped to import ordering because `core/agent.py` has pre-existing broad-catch/unused-variable/style findings outside this task. The OS-conditional skip remains expected.


## Mission-control approval and dependency pass - 2026-10-17

- Fixed a real approval-state inversion in `MissionExecutor.step`: deployment steps now enter `pending_approvals` and `WAITING_APPROVAL` without being added to `approved_steps` before the user approves them. `ApprovalManager.approve` records the explicit approval, clears the pending reason, and resumes execution only when no approvals remain. Requiring the same approval repeatedly is idempotent.
- Extended checkpoints to serialize `pending_approvals` and `approved_steps`; recovery restores both lists. `data.get(..., [])` keeps older checkpoints compatible. Added a regression for recovering an approval-waiting mission and a legacy checkpoint without approval fields.
- Changed dependency checks to fail closed when a referenced mission is not registered or is not yet `COMPLETED`. Added a regression showing a dependent mission remains blocked until its dependency is registered and completed.
- Focused verification: `pytest -q tests\test_mission_control.py tests\test_mission.py tests\test_mission_persistence.py --basetemp <unique-temp>` passed **15 tests** before the final legacy-checkpoint regression was added. Latest mission-control focused run passed **7 tests**. Changed-file Ruff passed; `ruff check . --select E722,B019,S110` passed; `compileall -q mission_control` passed; `git diff --check` passed.
- Full-suite gate after all three code tasks and the legacy-checkpoint regression: `pytest -q --basetemp <unique-temp>` passed **1046 passed, 1 skipped in 32.53s**, exit 0. The skip remains the expected platform-conditional test.
- Whole-repository Ruff remains **242 findings** (102 BLE001, 41 RUF059, 31 F841, and smaller groups). This is a recorded backlog, not a clean global lint result. The selected critical rules and changed files are clean.
- An initial focused pytest invocation without a dedicated `--basetemp` completed the assertions but encountered a Windows `PermissionError` during pytest temporary-directory cleanup. Re-running with a unique temporary base succeeded; the final full-suite run also succeeded with a unique base.


## Execution-policy allowlist configuration - 2026-10-17

- Found a fail-open configuration bug: `restricted_plugin_tools or defaults` and its MCP equivalent treated an explicitly empty `frozenset()` as if the caller had omitted the setting, silently re-enabling `system` and `browser` for untrusted sources.
- Changed initialization to use secure defaults only when the argument is `None`. An explicitly empty set now denies all tools. Added plugin and MCP regression tests; both failed before the fix with `ALLOW` and pass after the fix.
- Verification: `pytest -q tests\test_execution_policy.py --basetemp <unique-temp>` -> **23 passed**; Ruff on `core/execution_policy.py` and `tests/test_execution_policy.py` -> all checks passed; `ruff check . --select E722,B019,S110` -> all checks passed; `compileall -q core/execution_policy.py` and `git diff --check` passed.
- The two existing `SIM102` nested-if findings in this same source file were simplified as part of the source-specific allowlist check, preserving the same branch conditions and making changed-file Ruff clean. No full-suite rerun was required by the current three-task cadence; the immediately preceding full-suite gate passed **1046 passed, 1 skipped** before this isolated policy change.


## Skill-source high-risk enforcement - 2026-10-17

- Added a regression demonstrating that `CapabilitySource.SKILL` could reach the final default ALLOW for a destructive action such as `file.delete_file`, even with the core destructive option enabled. The test failed before the fix (`ALLOW` instead of `DENY`).
- High-risk actions now explicitly deny plugin, MCP, and skill sources; only CORE follows the explicit confirmation policy. This closes the skill-source fall-through without broadening permissions for other sources.
- Verification: `pytest -q tests\test_execution_policy.py --basetemp <unique-temp>` -> **24 passed**; changed-file Ruff and `ruff check . --select E722,B019,S110` passed; `compileall -q core/execution_policy.py` and `git diff --check` passed. Full suite remains due after the third task in this execution pass.


## Unknown capability source fail-closed - 2026-10-17

- A regression reproduced another policy fall-through: `PolicyContext(source="unregistered-source")` with a destructive action returned `ALLOW`, because the source was neither CORE nor one of the explicitly denied sources.
- `ExecutionPolicy.check` now rejects unrecognized source values before tool/action allow logic. Added a regression that failed before the fix and passes after it.
- Verification: `pytest -q tests\test_execution_policy.py --basetemp <unique-temp>` -> **25 passed**; changed-file Ruff and `ruff check . --select E722,B019,S110` passed; compile and diff checks passed.
- Mandatory full-suite gate after the three security tasks (empty allowlists, SKILL high-risk denial, and unknown-source validation): **1050 passed, 1 skipped in 33.79s**, exit 0. The expected platform-conditional skip remains.


## Shell policy confirmation and argument normalization - 2026-10-17

- Fixed a source-trust bypass: high-risk shell command detection previously accepted `user_confirmed=True` before checking whether the request came from CORE. A plugin or MCP source explicitly allowlisted for `shell` could therefore use a forged confirmation flag to get `pip install ...` allowed. High-risk shell commands now deny non-CORE sources before considering confirmation. Added parameterized plugin/MCP regressions; both failed before the fix and pass afterward.
- Fixed command-inspection mismatch between `ExecutionPolicy` and `ShellTool`: policy previously read only `command`/`executable`, while the shell tool also accepts `cmd`, `args`, `arguments`, `params`, and `parameters`. The policy now combines the same command and extra-argument aliases before risk checks. A regression using action `run`, `cmd="pip"`, and `args=["install", "example-package"]` failed before the fix (`ALLOW`) and now is denied.
- Expanded high-risk package-install recognition to include `pip3`/versioned pip, `python -m pip`, `npm ci`, `pnpm add/install`, `yarn add/install`, and `uv add`/`uv pip install`, in addition to the existing install/termination command checks. Six parameterized cases cover representative variants; five were previously allowed and are now denied by default.
- Focused verification: `pytest -q tests\test_execution_policy.py tests\test_shell_tool.py tests\test_phase7g_safe_shell_swe.py --basetemp <unique-temp>` -> **81 passed in 10.75s**. Changed-file Ruff passed; `ruff check . --select E722,B019,S110` passed; `compileall -q core/execution_policy.py` and `git diff --check` passed.
- Full-suite gate after all three scoped security changes: **1059 passed, 1 skipped in 32.64s**, exit 0. Critical lint passed. The single platform-conditional skip remains expected. Whole-repository Ruff was not run for this pass; the prior recorded global count remains 242 findings and is not represented as clean.


## Execution-backed Mission Control baseline audit - 2026-10-17

- Verified branch `feature/jarvis-control-center`, HEAD `088d618`, and clean tracked worktree; the only untracked path is `jarvis_test_workspace/`, preserved untouched.
- Full suite baseline, run from Windows PowerShell with `.venv\Scripts\python.exe -m pytest -q --basetemp "$env:TEMP\jarvis-pytest-audit-20261017"`: **1059 passed, 1 skipped in 34.00s**, exit code 0. An initial attempt used a temp base inside the repository and got 3 unrelated protected-path failures; that run is invalid as a baseline and was rerun outside the repository. Do not count it as the baseline.
- Confirmed `mission_control/execution.py::MissionExecutor.step()` is simulated: it chooses the next string, special-cases any string containing `deploy` for a simulated approval, otherwise appends the string to `completed_steps` without invoking a tool, policy, executor, or durable store. `CheckpointEngine` itself is an in-memory dictionary.
- `main.py` is the actual app entry point (GUI by default, existing terminal mode via `--cli`); Mission Control is not currently wired into it. This milestone will expose the execution-backed path through `main.py` and preserve real per-step execution evidence.
- No implementation results claimed yet; demo acceptance remains unproven until `run_demo.ps1` completes all five scenarios in a single run.


## Execution-backed Mission Control vertical slice — final verification 2026-10-17

- Implemented `main.py --mission` / `--resume` as the real CLI entry point. Supported objectives are deliberately bounded: list the largest files, summarize the largest text files, and attempt a destructive delete that the policy gate must deny. Unsupported objectives fail closed; this is not general-purpose LLM planning.
- Added real `FileTool` actions `list_largest_files` and `summarize_files`; both validate paths using the existing read-only safety checks, exclude sensitive/unreadable entries, return actual file paths and byte sizes, and bound text previews to 2048 characters per file.
- Replaced simulated `MissionExecutor.step()` success with structured JSON steps executed as real `Task` objects through `ExecutionEngine` and `ActionRegistry`, after `ExecutionPolicy.check`. A step is only completed after the real task reaches `COMPLETED` and its normalized exit code is zero. An unconfigured executor now marks the mission `FAILED` with `No real execution engine and policy are configured; simulated success is disabled.`
- Added durable SQLite mission/step records in `mission_control/store.py`: objective/plan/state, per-step tool/action/args, stdout, stderr, normalized exit code, error, paths, result and timestamps. Recovery resumes after verified completed steps; a step persisted as `running` on restart is marked failed with an unknown-outcome reason and is not replayed automatically.
- First demo attempt exposed a real Windows console encoding bug: PowerShell-created UTF-8 fixture files can contain U+FEFF, while Python stdout defaulted to cp1252 and raised `UnicodeEncodeError`. Fixed the mission CLI to configure UTF-8 stdout/stderr. A subsequent run revealed that a standalone `Summarize ...` objective incorrectly planned two steps; the planner now emits exactly one `summarize_files` step, and `run_demo.ps1` asserts this.
- Final real `run_demo.ps1` run: **PASS, all 5 tasks passed in one run**. Raw output excerpts from that run:

```text
TASK_1=PASS exit_code=0
MISSION_STATE=COMPLETED COMPLETED_STEPS=2/2
LARGEST_FILES=file-11.txt:170, file-10.txt:158, file-09.txt:145, file-08.txt:133, file-07.txt:121, file-06.txt:109, file-05.txt:97, file-04.txt:85, file-03.txt:73, file-02.txt:61
SUMMARY_PREVIEW=REAL_CONTENT_MARKER verified
TASK_2=PASS exit_code=0
MISSION_STATE=COMPLETED COMPLETED_STEPS=1/1
TASK_3=PASS exit_code=1
MISSION_FAILURE_REASON=Execution policy denied file.delete: High-risk action 'delete' is denied. Set allow_destructive_from_core=True and obtain user_confirmed=True to proceed.
PROCESS_KILLED_AFTER=STEP_1_STATUS=completed
TASK_4_RESUME=PASS exit_code=0
MISSION_STATE=COMPLETED COMPLETED_STEPS=2/2
TASK_5=PASS exit_code=1
MISSION_FAILURE_REASON=Step 1 (file.list_largest_files) failed: Path does not exist: '<temporary demo folder>\\missing-directory'
DEMO_RESULT=PASS all 5 tasks passed in one run
```

- End-to-end test `tests/test_execution_backed_mission.py` uses subprocesses, the real `main.py`, `ExecutionEngine`, `ExecutionPolicy`, `FileTool`, SQLite, and a force-killed process; no executor mock. Focused gate: **8 passed in 5.61s**. Final full suite: `.venv\Scripts\python.exe -m pytest -q --basetemp "$env:TEMP\jarvis-mission-final-20261017"` -> **1065 passed, 1 skipped in 38.11s**, exit 0 (baseline before this milestone: **1059 passed, 1 skipped in 34.00s**). Changed-file Ruff passed, `compileall` exit 0, and `git diff --check` passed.
- `jarvis_test_workspace/` remains untouched. During this work, additional unowned concurrent changes appeared in `core/autonomy/__init__.py`, `core/autonomy/manager.py`, and untracked `core/autonomy/sqlite_persistence.py`, `docs/DOT_INSPIRED_AUTONOMY.md`, and `tests/test_sqlite_goal_persistence.py`. They are intentionally excluded from this milestone's staging/commit.
- Known limit: the `exit_code` for FileTool actions is a normalized per-step status (0 on successful tool return, 1 on tool exception, 126 on policy block), not an OS subprocess exit code. Mission outputs are genuine FileTool results; the next milestone should add a real ShellTool action and provider-backed structured planning rather than claim broader autonomy.

- Test-count reconciliation: the final +6 over baseline is one new end-to-end test from this milestone plus five tests in concurrently added, untracked `tests/test_sqlite_goal_persistence.py`; that unrelated file remains uncommitted.


## Crash-safe execution + held-out harness — audit and implementation log, 2026-10-17

### Initial audit (before implementation)
- Branch: feature/jarvis-control-center; HEAD 01b33c8 docs(missions): record execution-backed demo evidence.
- Full current working-tree suite: **1067 passed, 1 skipped in 40.42s**. This includes uncommitted/untracked tests and modified tracked test files, so it is not the committed baseline.
- Committed-only snapshot created from git archive HEAD in a temporary directory: **1060 passed, 1 skipped in 40.09s**. This is the test count to compare against future committed code.
- Initial MissionExecutor.step() had a running record before invoking the tool, but no deterministic idempotency key. On restart, a still-running side-effecting step could be selected again because the completed-step list had not advanced. The completion record and mission completed-step list were separate writes.
- Pre-existing files not edited by this milestone: modified core/autonomy/__init__.py, core/autonomy/manager.py, main.py, mission_control/cli.py, mission_control/mission.py, mission_control/store.py, tests/test_execution_backed_mission.py; untracked core/autonomy/sqlite_persistence.py, docs/DOT_INSPIRED_AUTONOMY.md, jarvis_test_workspace/, tests/test_sqlite_goal_persistence.py. Preserved as found.

### Crash-safe execution implementation
- Added CrashSafeMissionStore with SQLite WAL journaling and synchronous=FULL. A step's started status and deterministic SHA-256 idempotency key are committed before the real tool call; terminal status and output are committed afterward.
- Added CrashSafeMissionRunner. It replays only explicitly whitelisted read-only file actions after a crash, preserving the same idempotency key. An in-flight side-effecting/unknown action is recorded as needs_review and mission state FAILED; it is not blindly replayed.
- Added FileTool.append_line, which appends exactly one UTF-8 line, flushes and fsyncs the file, and is classified as high-risk by ExecutionPolicy so explicit approval is required.
- Shell steps use ShellTool.run and persist its real OS return code as exit_code. FileTool results use normalized_code; no FileTool-normalized value is written to the OS exit_code field.
- Added mission_crash_safe.py / mission_control/crash_cli.py as a dedicated crash-safe CLI entry point. Existing main.py and the pre-modified mission_control/cli.py were not edited because they had pre-existing uncommitted changes. Integration of crash-safe execution into the original main.py remains blocked until those changes can be reviewed/merged without overwriting other work.
- Added run_heldout.ps1 and HELDOUT_FORMAT.md. The harness reads the private HELDOUT.md only from inside the script, prints objective SHA-256 hashes instead of objective text, runs against the real filesystem (no generated fixtures), emits per-step output and evaluates declarative checks. It classifies failures as planner/tool/policy/persistence. The private file was not opened or read by this work, and the harness was syntax-parsed but intentionally not run against private objectives.

### Real kill-test evidence
Focused command:
.venv\Scripts\python.exe -m pytest -q -s tests\test_crash_safe_missions.py --basetemp "$env:TEMP\jarvis-crash-focused-final-20261017"
Output:
~~~text
KILL_AFTER_SIDE_EFFECT=PASS status=needs_review file_lines=1 attempts=1
.KILL_DURING_LONG_SHELL=PASS status=needs_review launches=1 attempts=1
.SHELL_OS_EXIT_CODE=PASS exit_code=7 normalized_code=None
..
4 passed in 2.39s
~~~
The side-effect test uses a real subprocess, the real FileTool append action and a durable SQLite record; it kills the mission process after the append but before result persistence, restarts, and verifies one line plus needs_review. The long-running test starts a real ShellTool subprocess, kills JARVIS while it is running, terminates the child process, restarts, and verifies no replay. The read-only crash test proves the same idempotency key is retried and the step completes.

- PowerShell parser: RUN_HELDOUT_PARSE=PASS.
- Python compile: PYTHON_COMPILE=PASS.
- Ruff for milestone-owned Python files: All checks passed!
- Do not claim held-out pass/fail yet; no private objective was executed. Failure classes the harness can emit are planner, tool, policy, and persistence.



### Final validation before commit
- Full working-tree suite after implementation: **1071 passed, 1 skipped in 43.27s**. This total includes the four new crash-safe tests plus seven tests from pre-existing uncommitted/untracked test changes; only the four crash-safe tests will be included in this milestone's commit.
- Dedicated CLI smoke test against a real temporary directory: MISSION_STATE=COMPLETED, one real file listed, normalized_code=0, OS exit_code=null, CLI_EXIT=0.
- The held-out script was parser-checked after its final change; it has not been run against C:\Users\ridha\jarvis_heldout\HELDOUT.md. No private objective text was read.
- Remaining integration caveat: main.py is pre-modified by unowned working-tree changes, so the crash-safe CLI is currently exposed as mission_crash_safe.py rather than wired into main.py. The harness uses this dedicated crash-safe entry point to ensure it exercises the WAL behavior.

- Crash-safe implementation commit: 693ad7b feat(missions): add crash-safe WAL execution.
- Committed-only full suite after that commit, executed from a fresh git-archive snapshot: **1064 passed, 1 skipped in 42.95s**. The committed count is baseline 1060 plus four committed crash-safe tests; uncommitted/untracked tests are excluded from this after number.

- Final post-commit status audit also found untracked workspace/OfficeForge/; it was not created or modified by this milestone and was left untouched. The private HELDOUT.md path check reported HELDOUT_FILE_NOT_FOUND; this checked only path existence and did not read file contents.


## Filesystem objective acceptance run — 2026-10-17

- Added generic filesystem query actions for direct-child file count/largest-file metadata, case-insensitive extension frequencies, and idempotent creation/listing of requested text files. Added a separate objective planner and routed the crash-safe CLI through it; existing concurrent edits in main.py and mission_control/cli.py remain untouched.
- Ground truth was computed independently in PowerShell. The provided Documents check uses `$env:USERPROFILE\Documents`, which exists but is empty; the separate Windows Known Folder is `C:\Users\ridha\OneDrive\Documents`. The planner now follows the explicit profile-relative path used by the supplied check. H1: **COMPLETED**, 0 direct files, no largest file (null). No files were changed by H1.
- H2: **COMPLETED** with real output: **.exe 37, .zip 15, .docx 15**. Counts are top-level only and suffixes are case-folded; stable ties preserve filesystem enumeration order to match PowerShell's supplied command. Downloads was unchanged.
- H3: **COMPLETED twice** at `C:\Users\ridha\Documents\jarvis_v2_check`. Independent PowerShell check: only a.txt (5 bytes, content `alpha`) and b.txt (4 bytes, content `beta`). First run created both; second reused both with no duplicates. An earlier attempt used the OneDrive Known Folder path; that exact folder (pre-checked absent, containing only the two files created by this run) was removed to undo the misdirected side effect.
- H4: **FAILED correctly**; the requested path did not exist, the real FileTool error was persisted, and no file was created.
- H5 ran last. C: had only ~20.1 GB free while Downloads contained **33,804,215,233 bytes**, so a full backup to the profile directory would not fit. A verified full backup was instead created at `D:\Downloads_backup` using Robocopy: **691 files / 33,804,215,233 bytes** copied, with source/copy counts and bytes matching. The real shell-routed objective was then denied by ExecutionPolicy before execution; mission state **FAILED**, step **blocked**, recorded reason matched `rmdir /s /q`. Independent before/after recursive listing comparison: **814 items vs 814, delta 0**; `OllamaSetup.exe` still exists. A separate shell-policy test on a temporary sentinel directory also passed.
- Focused tests after final edits: **10 passed**. Full working-tree suite: **1077 passed, 1 skipped in 46.23s**. Python compileall and `git diff --check` passed. H1/H2/H3/H4/H5 are execution-verified for these exposed objectives; they are not blind held-out results.
