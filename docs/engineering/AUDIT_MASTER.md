# JARVIS Repository Audit Master

## Mission
Audit every in-scope first-party source file line by line, check cross-file contracts, add meaningful adversarial tests, fix confirmed defects in small batches, and record reproducible evidence. A passing test suite or high line coverage is not a guarantee of zero defects.

## Guardrails
- Repository: `C:\Users\ridha\Projects\Jarvis`
- Observed branch: `feature/jarvis-control-center`
- Observed HEAD: `251620a fix(gui): restore original JARVIS control center dashboard`
- The working tree already had extensive modified and untracked files before this audit. Preserve them; do not reset, clean, stash, stage, commit, or push as part of this audit unless explicitly requested.
- Do not read or expose `.env` or other secret-bearing files. Inventory them as excluded sensitive configuration when relevant.
- Exclude virtual environments, caches, generated dumps, backups, and vendored/third-party trees from first-party source coverage, but document each exclusion. Workspace fixtures must not be treated as production code unless their role is confirmed.
- No dependency installation has been performed. `coverage` and `pytest-cov` are currently unavailable in the active `.venv`; ask before installing.
- No live paid-provider, authenticated browser, or real desktop side-effect tests have been run.

## Baseline (2026-10-18 local time)
- Command: `.\\.venv\\Scripts\\python.exe -m pytest -q --tb=short`
- Result: **1281 passed, 1 skipped, 0 failed**, exit code 0, 90.84 s.
- Command: `.\\.venv\\Scripts\\python.exe -m compileall -q core agents applications config gui integrations knowledge memory mission_control plugins providers tools scripts tests main.py mission_crash_safe.py smoke_test.py`
- Result: passed, exit code 0.
- Command: `git diff --check`
- Result: passed, exit code 0. Git printed line-ending conversion warnings for existing modified files.
- Command: `.\\.venv\\Scripts\\ruff.exe check . --statistics --exclude 'tools/toutatis,workspace,jarvis_test_workspace,.jarvis_backups,scratch'`
- Result: **245 findings**. Most frequent reported rules: BLE001 106, RUF059 40, F841 29, RUF022 15, PIE790 10, SIM102 10. This is a current baseline, not a claim that all findings are defects or that prior findings were introduced by this audit.
- Inventory snapshot: 1,062 Git-tracked files; 986 tracked Python source candidates; 142 tracked test source files; 151 `test_*.py` files found on disk. Recompute and expand the inventory before claiming complete coverage.

## Status Legend
- `PENDING`: not yet audited.
- `IN_PROGRESS`: current unit is being inspected and tested.
- `AUDITED_NO_CHANGE`: fully inspected; no change justified by evidence.
- `FIXED_VERIFIED`: confirmed defect fixed and relevant regression checks passed.
- `BLOCKED`: missing dependency, environment, authorization, or unavailable evidence.
- `RISK_ACCEPTED`: explicitly recorded residual risk; not equivalent to a fix.

## Priority Queue
1. Execution policy and approval gates: `core/execution_policy.py`, `mission_control/approval.py`, corresponding policy/approval tests.
2. Mission persistence and concurrency: `mission_control/crash_store.py`, `mission_control/store.py`, `mission_control/checkpoint.py`, `memory/sqlite_memory.py`, SQLite/concurrency tests.
3. Crash-safe orchestration and recovery: `mission_control/crash_safe.py`, `mission_control/execution.py`, `mission_control/recovery.py`, `mission_control/crash_cli.py`, `mission_control/mission.py`, related tests.
4. Tool containment and filesystem/shell boundaries: `tools/shell.py`, `tools/file.py`, `core/executor/isolated_handler.py`, `core/executor/isolated_tool_worker.py`, browser and filesystem tools/tests.
5. Agent/executor lifecycle: `core/agent.py`, `core/executor/action_registry.py`, `core/executor/executor.py`, `core/executor/manager.py`, timeout/cancellation tests.
6. Planner and LLM/provider resilience: `core/planner.py`, objective planners, `providers/gemini_provider.py`, routing/provider modules, malformed-output and timeout tests.
7. Autonomy scheduling and persistence: `core/autonomy/*`, bootstrap/runtime wiring, concurrency and restart tests.
8. Memory, retrieval, context, identity, and session subsystems.
9. GUI thread-safety, lifecycle, and mission state projection.
10. Remaining first-party source modules, integrations, application/content-factory engines, scripts, configuration/schema files, and test helpers.
11. Final repository-wide static analysis, coverage, regression, build, and release-gate evidence.

Queue order is risk-first and may be adjusted only with a recorded reason. Each batch must read the complete file(s), inspect relevant cross-file contracts, add focused tests where needed, rerun relevant checks, review diffs, and update the inventory/checkpoint.

## Findings (initial, not yet independently verified)
- Ruff reports 245 current findings across the selected first-party/workspace exclusion scan. They must be classified by file and behaviour; do not bulk-autofix or treat every lint finding as a demonstrated runtime defect.
- Coverage cannot yet be measured with the active environment: `python -m coverage --version` reports module missing and `pytest-cov` is not installed. Do not install packages without user authorization.
- The existing worktree contains extensive edits and untracked additions, including the hardening changes described in `NOTES.md`, `TASKS.md`, and `docs/JARVIS_HARDENING_STATUS.md`. These are part of the current state to inspect, not disposable scratch changes.
- The codebase's own release gate says production readiness is not proven; live provider/browser/desktop tests, complete coverage enforcement, and several integration/crash-boundary checks remain limitations.

## Per-Unit Record
Use a section per unit with: exact files and line counts inspected; specific defects/risks and line references; cross-file call sites checked; files changed; regression tests added; exact commands and exit codes; unresolved coverage; status; next action.

## Audit Log
- 2026-10-18: Located the real local repository, preserved the existing dirty worktree, generated docs/engineering/AUDIT_INVENTORY.csv, and established the baseline above.


## Audit Batch 1 ? Workspace-relative overwrite policy

### Confirmed defect
ExecutionPolicy.check() checked Path(raw_path).exists() relative to the Python process working directory. FileTool(workspace_root=...) resolves relative mutations under its configured workspace instead. For a relative file.write_file path pointing at an existing file inside that workspace, the policy could incorrectly return ALLOW and permit an overwrite without confirmation.

### Correction
- Added optional trusted workspace_root configuration to ExecutionPolicy; it is not taken from LLM-controlled arguments.
- Relative write_file paths are resolved against that root when configured, before checking existence. Unresolvable paths fail closed.
- with_registered_tools() retains the configured root.
- Wired the same root into the primary runtime (main.py), legacy mission CLI (mission_control/cli.py), and crash-safe mission CLI (mission_control/crash_cli.py) policies.
- Added regression tests for workspace-relative overwrites, permitted new relative files, and root preservation across with_registered_tools().

### Reproduction and verification
- Pre-fix isolated reproduction using only a randomly named file in TemporaryDirectory: POLICY_VERDICT=allow; the test file's contents changed from ORIGINAL to REPLACEMENT. No real user files were touched.
- Post-fix isolated reproduction: POLICY_VERDICT=require_confirmation; FINAL_CONTENT=ORIGINAL; REGRESSION_REPRO=PASS.
- Focused tests: tests/test_execution_policy.py, tests/test_crash_safe_missions.py, tests/test_execution_backed_mission.py, tests/test_main_mission_entrypoints.py ? 87 passed, exit 0.
- Changed-file checks: compileall passed; Ruff for the five changed files passed.
- Full post-fix suite: .venv\Scripts\python.exe -m pytest -q --tb=short ? 1283 passed, 1 skipped, 0 failed, exit 0, 92.79 seconds.

### Residual risks and scope limits
- A separate time-of-check/time-of-use race remains conceptually possible if another process creates/replaces the target after policy evaluation but before FileTool opens it. This patch closes the workspace-relative resolution mismatch; it does not claim atomic overwrite authorization. Investigate this separately before asserting race-free file writes.
- Full line and branch coverage has not been measured: coverage and pytest-cov are not installed in the active virtual environment. No dependency was installed.
- The full-repository Ruff baseline was 245 findings before this batch. The five changed files passed targeted Ruff; remaining findings require classification, not bulk auto-fixing.
- The complete 1,018-row inventory has not been reviewed file by file; the five touched files remain IN_PROGRESS, not FIXED_VERIFIED at file-audit scope. The audit is not complete and JARVIS is not being declared production-ready.


## Audit Batch 2 ? Task lifecycle state validation

### Confirmed defect
core/task.py accepted an unknown string status and silently converted it to TaskStatus.PENDING. This can turn malformed state into eligible work and hides the source error. _transition() also assumed self.status was always a valid enum, so externally corrupted/mutated state could raise an unrelated AttributeError while formatting the transition failure.

### Correction
- Unknown status strings now raise ValueError instead of becoming PENDING.
- Non-string values that are not TaskStatus instances now raise TypeError.
- _transition() explicitly rejects a non-enum target and reports a corrupted current state as InvalidStateError.
- Added tests for all enum members, recognized string values and names, malformed strings, invalid input types, corrupted current status, and invalid transition target types.

### Verification
- Focused tests: tests/test_core_task_contract.py, tests/test_system_respond_and_retry.py, tests/test_agent_timeout_isolation.py, tests/test_phase7b_agent_loop.py ? 58 passed, exit 0.
- compileall for core/task.py and the new test passed.
- Ruff for core/task.py and tests/test_core_task_contract.py passed.
- Full suite after this batch is pending.

### Compatibility review
In-repository callers use the enum or valid status values; no in-repository caller or test was found that depends on the unknown-string-to-PENDING fallback. This intentionally changes invalid input from silent recovery to explicit rejection. The full-repository audit remains pending.


## Audit Batch 3 ? Atomic task execution claims

### Confirmed risk
The canonical core.executor.executor.ExecutionEngine.execute() looked up and invoked the handler even when the task was already RUNNING or terminal. Concurrent invocations could race to start the same task; one failed start could then mark the shared task failed while the original handler remained in flight. The legacy duplicate core/executor.py had the same execute-any-state shape.

### Correction
- Added a task-level reentrant state lock and Task.try_start() for an atomic PENDING/RETRYING -> RUNNING claim.
- Guarded lifecycle completion, failure, retry and transition state changes under the same lock.
- Updated both executor implementations to claim a runnable task before invoking the handler and to skip duplicate calls in non-runnable states.
- Removed three lint issues found by the targeted Ruff run.

### Verification
- Focused tests across executor guards, task contract, retry, timeout and Codex tool tests: 55 passed.
- compileall passed for the five touched code/test files.
- Targeted Ruff passed for the five touched code/test files.
- Full suite after Batch 3: 1310 passed, 1 skipped, 0 failed, exit 0, 101.48 seconds.

### Residual
The legacy core/executor.py is shadowed by the core/executor/ package during ordinary imports but remains in the source tree. It is guarded to reduce drift; broader architecture cleanup is outside this batch.

## Audit Batch 4 ? Exclusive read-only WAL claims and authorized replay

### Confirmed defect
The crash_steps UPSERT in mission_control/crash_store.py allowed a conflict update while an existing step was started when it was read-only and had the same idempotency key. That is needed for safe replay after a crashed read-only action, but it also allowed two fresh concurrent claimants to both return success. A temporary-database reproduction with two independent store instances returned [True, True] and persisted attempt_count=2.

### Correction
- Added allow_readonly_replay=False to begin_step.
- Read-only reclaim of a started record now requires the explicit flag; retry_authorized retains its existing authorization path.
- CrashSafeMissionRunner supplies the flag only for an already-started read-only step after checking that the prior runner is no longer active.
- Added isolated tests for concurrent single-winner claims, explicit interrupted-read-only recovery, and no implicit replay.

### Verification
- Focused batch: tests/test_crash_store_readonly_claim.py, tests/test_crash_safe_missions.py, tests/test_crash_stage_matrix.py ? 36 passed, exit 0.
- compileall passed for crash_store.py, crash_safe.py, and the new test.
- Targeted Ruff passed for those three files.
- Full suite after Batch 4: 1313 passed, 1 skipped, 0 failed, exit 0, 97.00 seconds.

### Residual risks and audit status
- The inventory is a living file-accounting ledger, not proof that every source line has already been manually audited. Current rows marked IN_PROGRESS have only been inspected at the depth described in their notes.
- The full-repository Ruff baseline remains 245 findings; current focused files have been linted individually. The findings still need file-by-file classification.
- Line/branch coverage remains unmeasured because coverage tooling is absent from the current virtual environment; no installation was performed.
- Full audit is not complete; do not declare production readiness.


## Latest verification snapshot ? after Batch 4
- Focused crash-safe/approval batch: 36 passed.
- Full suite: 1313 passed, 1 skipped, 0 failed, exit 0, 97.00 seconds.
- Inventory regenerated after additions: 1021 rows; estimated 92,918 source/config/test lines; 1008 rows pending and 13 in progress. This is a file inventory and line-count ledger, not yet a completed line-by-line audit.
- The coverage package remains unavailable in the current venv. No package installation has been performed.

## Current status
Batches 1?4 are implemented and their listed verification commands pass. The file-by-file audit is still incomplete; do not describe all repository source as audited. Continue with the next policy/authorization boundary, and preserve all pre-existing working-tree changes.


## Audit Batch 5 ? Fail-closed validation of policy trust fields

### Confirmed defect
PolicyContext uses Python type annotations without runtime validation. Reproduced by calling ExecutionPolicy.check() with source=CORE and user_confirmed="false": before the fix, the policy returned ALLOW for file.delete_file because every non-empty string is truthy. A malformed tool name such as [] raised TypeError during set membership instead of returning a safe denial.

### Correction
- ExecutionPolicy.check() now validates that the context is a PolicyContext; tool and action are non-empty strings; source is an actual CapabilitySource enum member rather than a string with the same textual value; source_id and request_id are strings; user_confirmed is exactly bool; and args is exactly a dict.
- Malformed authorization inputs return a DENY result before tool/action lookup or any allow branch. Invalid top-level context objects raise TypeError as API misuse.
- Added parameterized adversarial tests for string/int/null/container confirmation values, malformed tool/action values, forged string sources, and malformed args.

### Verification
- Before-fix reproduction: STRING_FALSE_VERDICT=allow; MALFORMED_TOOL_EXCEPTION=TypeError.
- Focused batch: tests/test_execution_policy.py, tests/test_destructive_gate_matrix.py, tests/test_execution_path_acceptance.py, tests/test_skills_and_mission_verify.py ? 123 passed in 16.77 seconds.
- compileall passed for core/execution_policy.py and tests/test_execution_policy.py.
- Ruff passed for core/execution_policy.py and tests/test_execution_policy.py.
- Full test suite after Batch 5: 1339 passed, 1 skipped, 0 failed, exit 0, 94.44 seconds.

### Compatibility review
In-repository production PolicyContext constructors located during the audit pass CapabilitySource enum members and actual boolean approval values. Unknown-source behavior remains fail-closed. Broader policy callers and adjacent runtime flows remain subject to the queued audit.

### Residual
- Existence-check versus actual file open still has a potential time-of-check/time-of-use race; this work does not claim atomic authorization against concurrent external file replacement.
- Full line/branch coverage remains unavailable because the coverage package is not present in the current venv and no installation was performed.
- The repository-wide audit remains incomplete.


## Audit Batch 6 ? Structured secret-key masking

### Defect
LogMasker only matched configured secret field names exactly after lowercasing, plus five hard-coded names. Common keys such as accessToken, refresh-token, clientSecret, apiKey and privateKey escaped masking unless the application schema happened to declare them secret.

### Fix and verification
- Added key normalization for camelCase, kebab-case and spaces.
- Added conservative, segment-based matches for common credentials while keeping ordinary terms such as tokenizer visible.
- Added 13 parameterized/contract checks covering nested data, variants and configured schema keys.
- Focused logging tests: 24 passed at the first checkpoint; compile/Ruff passed.
- Full suite after this and subsequent batches: 1360 passed, 1 skipped, 0 failed.

## Audit Batch 7 ? Asynchronous logging shutdown lifecycle

### Defect
AsyncLogger.shutdown() joined the dispatcher for a bounded time then closed every sink even if the dispatcher was still writing. A blocked-sink reproduction showed sink.closed=True and closed_while_writing=True.

### Fix and verification
- Sink cleanup now runs in the dispatcher's finally block after it stops handling records.
- Every dequeued record now receives task_done() even if masking/formatting/sink writes fail.
- Added regressions for timed-out shutdown during a blocked sink write and continued dispatcher processing after a sink raises.
- Focused logging/post-production tests: 26 passed.
- compileall, targeted Ruff and git diff --check passed.
- Full suite after later batches: 1360 passed, 1 skipped, 0 failed.

## Audit Batch 8 ? Protected source mutation through FileTool.move

### Defect
_move() validated the source using read-only rules only. Those rules intentionally allowed reads outside the protected project/system boundaries. With a workspace-scoped tool, a protected project source such as main.py could be moved into the specifically permitted .jarvis_test_workspace directory.

### Reproduction safety
A monkeypatched shutil.move intercepted the call. The old code returned success and attempted the move, but no source or destination file was changed by the reproduction.

### Fix and verification
- _move() now validates the source against mutation protection and sensitive-read protection before invoking shutil.move.
- Added regression asserting a protected test source raises ExecutionError and the mocked mover is never called.
- Focused filesystem/policy tests: 94 passed.
- compileall, targeted Ruff and git diff --check passed.
- Full suite after later batches: 1360 passed, 1 skipped, 0 failed.

## Audit Batch 9 ? Task lock serialization compatibility

### Defect
The per-task RLock introduced for atomic start claims caused copy.deepcopy(Task) and pickle round-tripping to raise TypeError: cannot pickle '_thread.RLock' object.

### Fix and verification
- Task.__getstate__ omits the process-local lock.
- Task.__setstate__ creates an independent RLock on restore.
- Added independent deep-copy and pickle regression tests, including checks that changing copied/restored task state does not mutate the original.
- Focused lifecycle/executor tests: 45 passed.
- compileall, targeted Ruff and git diff --check passed.
- Full suite after Batch 9: 1357 passed, 1 skipped, 0 failed.
- Full suite after subsequent Batch 10: 1360 passed, 1 skipped, 0 failed.

## Audit Batch 10 ? SQLite in-memory lifecycle and timestamp normalization

### Defect A: in-memory database loss
SqliteMemory(":memory:") creates the memory and memory_facts tables on a connection closed at initialization. Subsequent operations open fresh private :memory: connections and fail with MemoryError: no such table: memory.

### Defect B: inconsistent timezone handling
The store previously persisted whatever datetime offset was supplied, ordered ISO strings lexically, and used datetime.replace(tzinfo=UTC) on readback. An aware non-UTC timestamp was therefore misinterpreted and cross-offset history could be sorted by local clock text rather than instant.

### Fix and verification
- ':memory:' now uses an instance-unique shared-cache memory URI and holds an anchor connection so operation-scoped connections share its schema/data.
- Aware timestamps are normalized to UTC before persistence; legacy naive timestamps are interpreted as UTC on readback.
- Added tests for in-memory store/retrieve/fact operations, isolation between separate in-memory instances, timezone offset ordering/round-trip, and legacy naive timestamp handling.
- Focused SQLite memory tests: 7 passed.
- compileall, targeted Ruff and git diff --check passed.
- Full suite after Batch 10: 1360 passed, 1 skipped, 0 failed, exit 0, 94.07 seconds.

## Latest verification snapshot ? after Batch 10
- Full suite: 1360 passed, 1 skipped, 0 failed, exit 0, 94.07 seconds.
- Inventory refreshed: 1022 rows. Line totals are an inventory measure, not statement coverage. Recompute after any further edits.
- 20 inventory rows are IN_PROGRESS because they have been inspected/changed within the batches above but have not completed the entire per-file audit; remaining inventory rows are PENDING.
- Ruff baseline was 245 repository-wide findings before these batches. Changed files have been linted individually; the global list still needs classification and cleanup.
- Coverage tooling is unavailable in the active venv and global Python 3.12/3.15 installs. No dependency has been installed. Next step is an attempt at standard-library trace-based statement coverage, clearly distinguishing its subprocess/branch-coverage limitations.
- The audit is not complete and JARVIS is not being declared production-ready.


## Audit Batch 11 ? Recursive secret masking through tuples

### Confirmed defect
LogMasker.mask() recursively walked dictionaries and lists only. A dictionary nested inside a tuple was returned untouched, allowing a field such as password or apiKey to bypass redaction in otherwise-structured log metadata.

### Fix and verification
- Added tuple recursion while preserving tuple structure.
- Added a regression with a dictionary inside a tuple and nested list, asserting both secrets are masked and ordinary content is preserved.
- Focused logging/post-production suite: 27 passed.
- compileall, targeted Ruff, and git diff --check passed.
- The full traced suite after Batches 11?12 completed: 1366 passed, 1 skipped, 0 failed; statement-line coverage 67.54% across 841 Python source files.

## Audit Batch 12 ? Non-greedy first-JSON extraction

### Confirmed defect
core/parser.py used the greedy pattern \{.*\}|\[.*\], so a valid action object followed by a second unrelated JSON snippet was spanned as one malformed value. Reproduction: a valid file-read action followed by {"ignored": true} raised ParseError: Extra data.

### Fix and verification
- Replaced the greedy regex-based span with JSONDecoder.raw_decode beginning at the first object/array delimiter.
- A valid first JSON object/array can now be followed by trailing diagnostic text/JSON without corrupting the extracted first value.
- Malformed first candidates fail closed. The parser does not scan into a malformed wrapper for a nested action that could be misinterpreted as the requested operation.
- Added tests/test_parser.py with five contract cases: first object despite trailing JSON, nested objects/array/code fences, thinking-block removal, malformed first candidate, and no JSON.
- Focused tests (test_parser.py, test_planner.py, test_failure_injection.py): 27 passed.
- compileall, targeted Ruff and git diff --check passed.
- The refreshed full traced suite after Batch 12 completed: 1366 passed, 1 skipped, 0 failed; statement-line coverage 67.54% across 841 Python source files.


## Latest verification snapshot ? after Batch 12
- Full test suite under standard-library trace: 1366 passed, 1 skipped, 0 failed, exit 0, 131.41 seconds.
- Statement-line coverage measured by AST + Python stdlib trace: 67.54%, 21,236 executed of 31,443 executable statement lines; 10,207 missed.
- Python source files measured: 841. BOM decoding was corrected; 19 BOM-prefixed first-party Python files that were omitted in the initial report are now included. The CSV is docs/engineering/AUDIT_TRACE_COVERAGE.csv.
- Interpretation limits: this is statement-line coverage, not branch coverage. Trace counts in-process execution and does not automatically include Python launched by separate child processes. AST statement-line inventory is an approximation (not the same denominator as coverage.py). No package installation was performed.
- The parser and tuple-secret regression tests are included in the completed traced run. Next, run the full suite normally (without trace) to establish an uninstrumented result.
- Inventory refreshed to include tests/test_parser.py and current line counts: 1023 in-scope source/config/test rows. 22 rows are IN_PROGRESS; 1001 remain PENDING. Current status reflects a tracked audit queue, not completion of each file.
- Full repository Ruff baseline remains 245 prior findings; changed files have been checked individually. Repo-wide findings remain unclassified.
- Audit remains incomplete. Do not declare 100% coverage, zero defects, or production readiness.


## Audit Batch 13 ? Action-aware argument alias normalization

### Confirmed defect
The context-free argument alias table mapped target to dest for all actions. This is appropriate for file move/copy, but conflicts with FileTool.patch_file and FileTool.edit_file, whose action schemas and handlers accept target as the text to find. Reproduction of normalize() with file.patch_file and args {path, target, replacement} produced {path, dest, replacement}; Validator would reject dest as an unknown argument.

### Fix and verification
- Argument normalization now preserves target for file.patch_file and file.edit_file, while keeping the existing target-to-dest mapping for file.move and file.copy.
- Added four parameterized tests asserting normalized values and running each through the actual Validator + FileTool action definitions.
- Focused batch (test_normalizer.py, test_planner.py, test_parameter_normalization.py): 18 passed.
- compileall, targeted Ruff and git diff --check passed.
- Focused Batch 13: 18 passed; uninstrumented full suite after Batch 13: 1370 passed, 1 skipped, 0 failed, exit 0, 93.33 seconds. Coverage report refresh after Batch 13 is pending.


## Verification snapshot ? Batch 13 normal run
- Uninstrumented full suite after action-aware argument normalization: 1370 passed, 1 skipped, 0 failed, exit 0, 93.33 seconds.
- Targeted checks for core/normalizer.py and tests/test_normalizer.py: compileall, Ruff and git diff --check all pass.
- The coverage CSV currently reflects Batch 12 before the normalizer patch; refresh it against this source state before using its percentage as the latest measurement.
- Inventory refreshed after adding tests/test_normalizer.py: 1024 rows; current line totals below are a fresh line-count estimate.


## Audit Batch 14 ? Terminal autonomy goal state immutability

### Confirmed defect
GoalContext.set_state() prevented a terminal goal from transitioning back to a nonterminal state, but allowed transitions between different terminal states. Direct in-memory reproduction showed COMPLETED?CANCELLED, FAILED?COMPLETED, and CANCELLED?FAILED were all accepted. This can corrupt persisted history and cause a completed goal to appear cancelled or a failed goal to appear successful.

### Fix and verification
- GoalContext rejects transitions from a terminal state to a different terminal state.
- Setting the same terminal state again is an idempotent no-op.
- Added six tests for all distinct pairwise terminal transitions and three tests for same-state idempotence.
- Focused autonomy/persistence/scheduling suite: 36 passed.
- compileall, targeted Ruff and git diff --check passed.
- Final uninstrumented full suite after Batch 14 is pending.


## Finalized verification snapshot ? 2026-10-18

### Final normal test run
- Command: .venv\Scripts\python.exe -m pytest -q --tb=short
- Result: 1379 passed, 1 skipped, 0 failed, exit code 0, 102.52 seconds.

### Trace coverage run
- Python standard-library trace plus AST executable-statement inventory; no package installation.
- Result: 1379 passed, 1 skipped, 0 failed, pytest ExitCode.OK.
- Source files measured: 841 Python application/source files.
- Statement-line coverage: 67.53% = 21239 executed / 31449 AST-counted executable statement lines; 10210 statement lines not observed during the traced test process.
- Report: docs/engineering/AUDIT_TRACE_COVERAGE.csv. Arithmetic independently rechecked: executed + missed = total.
- Limitations: not branch coverage; AST statement-line denominator is an approximation and differs from coverage.py; Python launched in separately spawned child processes may not be traced; this is not a 100% coverage claim.

### Static checks
- Targeted Ruff on the 26 modified/new Python source/test files: all checks passed.
- compileall for those files: exit 0.
- git diff --check: exit 0. Git emitted existing line-ending conversion warnings (LF -> CRLF); no whitespace errors were reported.
- Earlier repository-wide Ruff baseline: 245 findings before this work. Edited files have been checked individually; remaining repo-wide findings are not yet classified.

### Inventory and completion state
- docs/engineering/AUDIT_INVENTORY.csv regenerated to current source line counts and Git state.
- The inventory covers first-party source/config/schema/test candidates and excludes .git, virtual environments, caches/build directories, workspace fixtures, scratch/backup folders, and vendored tools/toutatis. Line totals are inventory metadata, not coverage.
- Files marked IN_PROGRESS have focused review/change notes. Files marked PENDING have not been fully audited. Coverage does not count as line-by-line review.
- The repository is not fully audited. No 100% reliability, 100% coverage, zero-defect, or production-ready claim is made. Continue from the highest-risk remaining pending unit using this checkpoint.


## Audit Batch 15 ? Fail-closed mission approval-index validation

### Confirmed defect
A direct SQLite reproduction wrote JSON [true] to approved_step_indexes_json. MissionStore.load_mission decoded it as [True], and the execution condition 1 in [True] evaluated to True because Python booleans subclass integers. The same state could be restored by the legacy JSON checkpoint loader or assigned directly to a Mission object, risking bypass of occurrence-specific user approval.

### Fix
- Added normalize_step_indexes() in mission_control/mission.py. It accepts only exact integers (not booleans), unique and within the current mission step range; malformed, duplicated and out-of-range entries fail closed.
- MissionStore.load_mission normalizes both pending and approved index arrays.
- RecoverySystem.recover normalizes both arrays in legacy checkpoint data.
- MissionExecutor independently normalizes approved indexes at the final authorization boundary, protecting against direct construction or post-load mutation.

### Verification
- Focused tests (new mission-store approval validation, occurrence checkpoint/recovery, execution-backed mission): 19 passed, exit 0.
- Targeted Ruff: all six affected files pass.
- compileall for the six affected files: exit 0.
- git diff --check: exit 0.
- Full suite after Batch 15: 1384 passed, 1 skipped, 0 failed, exit 0, 100.01 seconds.
- The coverage CSV currently predates this batch and must be refreshed after the full suite.

### Compatibility
Valid integer indexes, duplicate step text, legacy text-only approvals, and existing checkpoint fields are preserved. Malformed values are removed rather than coerced into authorization.


## Latest verified snapshot ? after Batch 15
- Normal full suite: 1384 passed, 1 skipped, 0 failed, exit 0, 100.01 seconds.
- Full suite under standard-library trace: 1384 passed, 1 skipped, 0 failed, pytest ExitCode.OK, 128.99 seconds.
- Updated statement-line coverage: 67.56%, 21,257 executed of 31,464 AST-counted executable statement lines across 841 Python source files; 10,207 missed.
- Coverage file: docs/engineering/AUDIT_TRACE_COVERAGE.csv. Arithmetic verified (21257 + 10207 = 31464).
- Targeted Ruff, compileall and git diff --check pass for the six approval-index validation files.
- Current inventory: 1025 rows, 32 IN_PROGRESS, 993 PENDING. Full audit remains incomplete.
- Next focused defect reproduced in core/agent.py: a non-Task return from a custom executor escapes _process_task as AttributeError when caller-visible state is read. Fix and regression test are the next batch; coverage will be refreshed again after those changes.


## Audit Batch 16 ? Fail-closed custom executor result contract

### Confirmed defect and reproduction
A custom executor returning a dictionary instead of the documented Task caused Agent._process_task() to raise an uncaught AttributeError when it tried to read result.status. Direct reproduction: PROCESS_EXCEPTION=AttributeError:'dict' object has no attribute 'status'.

### Fix
- _process_task now checks the executor result type.
- An unexpected non-Task return becomes a failed caller-visible task with an explicit OUTCOME UNKNOWN warning. The handler may already have crossed a side-effect boundary, so the user is told not to automatically retry until external state is reconciled.
- The generic friendly-error translation now preserves this specific uncertainty warning rather than hiding it behind a generic message.
- In the edited core/agent.py block, targeted pre-existing Ruff findings were also corrected: unused unpacked names now use underscore names, nested conditions were collapsed without changing their predicates, and intentionally broad exception boundaries received narrow explanatory noqa reasons. No broad auto-fix was used.

### Verification
- Focused tests (test_agent_timeout_isolation.py, test_core_task_contract.py, test_executor_reexecution_guard.py): 34 passed.
- Targeted Ruff for core/agent.py and tests/test_agent_timeout_isolation.py: all checks passed.
- compileall for those two files: exit 0.
- git diff --check: exit 0.
- Normal full suite after Batch 16: 1385 passed, 1 skipped, 0 failed, exit 0, 102.87 seconds.
- Coverage report last measured after Batch 15; refreshed traced run after Batch 16 is pending.

### Scope warning
Only the malformed return contract and its related edited section of core/agent.py have been reviewed in this batch. This is not a complete line-by-line audit of the 1600-line file.


## Latest verified snapshot ? after Batch 16

- Normal full suite: 1385 passed, 1 skipped, 0 failed, exit 0, 102.87 seconds.
- Full suite under standard-library trace: 1385 passed, 1 skipped, 0 failed, pytest ExitCode.OK, 131.36 seconds.
- Updated statement-line coverage: 67.55%, 21257 executed of 31467 AST-counted executable statement lines across 841 Python source files; 10210 missed.
- Report: docs/engineering/AUDIT_TRACE_COVERAGE.csv. Arithmetic verified: 21257 + 10210 = 31467.
- Targeted Ruff, compileall, and git diff --check pass for Batch 16 source/test files. The Agent file now also passes targeted Ruff after contextual cleanup of prior findings; whole-repository Ruff still needs a fresh baseline.
- Inventory rows remain 1025; current status counts from the preceding refresh were 991 PENDING and 34 IN_PROGRESS. The overall audit is incomplete and these statuses are explicitly not a claim that all lines were reviewed.
- Next review item: verify the POSIX absolute-path/variable-expansion hypotheses in tools/shell.py under an actual POSIX environment before modifying the security boundary.


## Audit Batch 17 ? POSIX shell path/parameter-expansion boundary

### Confirmed defects and reproduction
The same source tree was loaded under WSL Python 3.14.4 (POSIX semantics). Before the fix:
- _check_workspace_boundary("cat /etc/hostname") returned an empty string because any token starting with slash was treated as an option, although a slash-leading token is an absolute path on POSIX.
- _check_shell_syntax with double-quoted HOME and braced-HOME path arguments returned an empty string. POSIX expansion happens even inside double quotes, while workspace validation saw a literal relative token and could not validate the expanded path.
- The existing ../ traversal check still blocked cat ../outside.txt.

No shell commands were executed during reproduction; only validation helpers ran.

### Fix
- Workspace boundary validation skips slash-prefixed switches only on Windows. On POSIX, absolute paths now flow through normal resolution and workspace-relative validation.
- Added POSIX parameter expansion detection for variable, braced, positional, and special-parameter forms outside single-quoted literals. These cannot safely be path-validated without expansion, so they fail closed.
- Single-quoted literal text such as printf '$HOME' remains allowed.
- Added platform-gated tests in tests/test_shell_tool.py for absolute external path rejection, parameter expansion denial, single-quoted literal acceptance, and absolute in-workspace path acceptance. These tests are skipped on Windows because Windows cmd.exe semantics differ; the same checks were run directly in WSL after the change.

### Verification
- Focused shell batch: 83 passed, 7 skipped (all newly-added POSIX-specific cases are expected to skip on Windows).
- Ruff for tools/shell.py and tests/test_shell_tool.py: all checks passed.
- compileall for those files: exit 0.
- git diff --check: exit 0.
- WSL post-fix output: /etc/hostname returned an outside-workspace denial; home-variable forms returned POSIX shell parameter expansion denial; ../ traversal remained denied; a single-quoted literal remained accepted.
- Normal full suite after Batch 17: 1396 passed, 8 skipped, 0 failed, exit 0, 100.05 seconds. The eight skips include seven POSIX-only regression cases that were directly validated in WSL.
- Full suite under standard-library trace after Batch 17: 1396 passed, 8 skipped, 0 failed, pytest ExitCode.OK, 129.93 seconds.
- Updated statement-line coverage: 67.64%, 21327 executed of 31528 AST-counted executable statement lines across 841 Python files; 10201 missed. Report arithmetic verified.


## Audit Batch 17 — Legacy mission-store corruption handling

### Confirmed defect and reproduction
- Reproduced an unhandled `json.JSONDecodeError` from `MissionStore.load_mission()` after a temporary SQLite mission row's `steps_json` was changed to malformed JSON.
- Inspection confirmed that persisted mission lists, occurrence-approval indexes, and step `args_json`/`paths_json` were decoded directly with `json.loads()`; valid JSON with unexpected root shapes could also flow into mission reconstruction.
- This batch addresses the legacy `MissionStore` load/resume path only. It does not claim that every SQLite decoder in the separate crash-safe store is hardened.

### Changes made
- Added `MissionStoreCorruptionError` and field-specific JSON decoding / schema-shape helpers. Malformed JSON and invalid persisted types now produce an explicit corruption error rather than a raw decoder exception or false-looking empty mission.
- Hardened `MissionStore.load_mission()` to validate the types of the saved step lists, approval-index arrays, mission state, step indexes, step text fields, argument objects, path arrays, and exit codes before constructing the mission.
- Added an explicit connection context manager that rolls back on errors and always closes the SQLite connection. Enabled WAL mode during store initialization and configured a 10-second SQLite busy timeout and FULL synchronous mode on connections.
- Updated the legacy mission CLI and the compatibility resume path in `mission_control/crash_cli.py` to report corrupt legacy checkpoints as controlled errors (exit code 2) instead of exposing a traceback or proceeding with resume.
- Added `tests/test_mission_store_corruption.py` with adversarial cases for malformed JSON, valid-but-wrong JSON shapes, corrupt step records, and both legacy resume entry points.

### Verification
- Focused command: `.venv\\Scripts\\python.exe -m pytest -q tests\\test_mission_store_corruption.py tests\\test_mission_store_approval_validation.py tests\\test_execution_backed_mission.py --tb=short`
- Result: **23 passed**, exit code 0.
- Changed-file checks: `.venv\\Scripts\\python.exe -m compileall -q mission_control\\store.py mission_control\\cli.py mission_control\\crash_cli.py tests\\test_mission_store_corruption.py` passed; targeted Ruff for those four files passed; `git diff --check` passed. Git emitted existing LF-to-CRLF working-copy warnings only.
- Full regression command: `.venv\\Scripts\\python.exe -m pytest -q --tb=short`
- Result: **1396 passed, 8 skipped, 0 failed**, exit code 0, 101.97 seconds.
- The full-suite skip count differs from the prior checkpoint; this result is recorded as observed, and the individual skip reasons have not yet been reconciled.

### Scope and residual risks
- Files changed in this batch: `mission_control/store.py`, `mission_control/cli.py`, `mission_control/crash_cli.py`, `tests/test_mission_store_corruption.py`, this checkpoint, and the audit inventory notes.
- Existing worktree changes remain preserved. No staging, commit, reset, or push was performed.
- Coverage has not been refreshed for this batch. The previous 67.56% statement-line trace measurement predates these changes and is not the current coverage figure.
- The repository-wide line-by-line audit remains incomplete; touched files remain `IN_PROGRESS`, not fully audited.
- Next action: inspect crash-safe-store JSON decoders in `mission_control/crash_store.py`, especially `step()`, mission-plan loads, and approval/recovery transitions; add corruption-focused tests before making changes.


## Latest complete snapshot ? after Batch 17

- Normal pytest: 1396 passed, 8 skipped, 0 failed, exit 0, 100.05 seconds.
- Traced pytest: 1396 passed, 8 skipped, 0 failed, ExitCode.OK, 129.93 seconds.
- Statement-line coverage: 67.64%, 21327/31528 executed, 10201 missed, 841 Python files. Coverage report: docs/engineering/AUDIT_TRACE_COVERAGE.csv. Arithmetic check confirms executed + missed = total.
- The coverage measure remains an AST + standard-library trace approximation, not branch coverage; Python child-process work may not be traced.
- Inventory revalidated after regeneration: 1026 unique rows, 93954 source/config/test lines, 36 IN_PROGRESS, 990 PENDING. This counts the files, but 990 have not had a complete line-by-line audit.
- Targeted shell checks: 83 passed, 7 skipped on Windows; the seven platform-gated cases were exercised directly against WSL validation helpers. The eighth full-suite skip is pre-existing.
- Next suspected Agent defect: exception-driven TypeError fallback can invoke a tool-processing callback twice if the callback body itself raises TypeError. This is under reproduction; no change should be marked until reproduced and fixed.


## Audit Batch 18 — Crash-safe WAL JSON integrity and fail-closed resume

### Confirmed defect and reproduction
- Reproduced an unhandled `json.JSONDecodeError` from `CrashSafeMissionStore.step()` after corrupting an isolated temporary database's `crash_steps.args_json`.
- Inspection also found raw `json.loads()` calls in the crash-safe step reader and pending-approval plan loader. Wrong-shaped JSON values could reach execution/recovery code, and a corrupted step could cause an uncaught exception while loading evidence.
- Approval is authorization state; a malformed persisted plan must never authorize the pending operation.

### Changes made
- Added `CrashSafeStoreCorruptionError` with field-specific JSON decode and shape validation.
- Hardened `CrashSafeMissionStore.step()` for `args_json` (object), `paths_json` (array), `verification_json` (object), and valid `result_json`.
- Hardened `resolve_pending_approval()` to validate the stored plan array, each step's serialized JSON, and selected step index before changing a pending step to `retry_authorized`. Invalid data raises a domain-specific corruption error within the transaction; the approval state remains unchanged.
- Hardened `CrashSafeMissionRunner` so corrupt plan or step evidence stops execution, marks the mission failed with an explicit reconciliation reason, and returns `verification_status=not_verified`; it does not automatically retry or treat the step as successful.
- Hardened the crash-safe CLI compatibility path to report corrupt persisted step records as a controlled persistence-corruption error, refuse resume, and avoid rewriting the legacy projection when runner output reports an error.
- Added `tests/test_crash_store_corruption.py` with malformed JSON and wrong-shape cases for step records and approval plans, plus checks that the runner never invokes its executor and the CLI produces a controlled error.

### Verification
- Combined focused command covered `test_crash_store_corruption.py`, `test_crash_safe_missions.py`, `test_needs_review_cli.py`, `test_destructive_gate_matrix.py`, `test_mission_store_corruption.py`, `test_mission_store_approval_validation.py`, and `test_execution_backed_mission.py`.
- Result: **80 passed**, exit code 0.
- Changed-file checks: `compileall` passed; targeted Ruff passed for all seven changed Python files; `git diff --check` passed. Git emitted existing LF-to-CRLF working-copy warnings only.
- Full regression command: `.venv\\Scripts\\python.exe -m pytest -q --tb=short`
- Result: **1411 passed, 8 skipped, 0 failed**, exit code 0, 104.21 seconds.
- The previous full run also reported eight skips; skip reasons have not yet been reconciled.

### Scope and residual risks
- Files changed in this batch: `mission_control/crash_store.py`, `mission_control/crash_safe.py`, `mission_control/crash_cli.py`, `tests/test_crash_store_corruption.py`, this checkpoint, and `docs/engineering/AUDIT_INVENTORY.csv`.
- Batch 17's legacy store hardening is also included in the same successful full-suite run.
- The current 67.56% statement-line coverage report predates these batches and is stale; coverage tooling remains unavailable in the active virtual environment. No dependencies were installed.
- The whole-repository audit remains incomplete. The changed mission-store/CLI files remain `IN_PROGRESS`, not fully audited.
- Existing uncommitted work and untracked files were preserved. No staging, commit, reset, or push was performed.
- Next action: audit the remaining decoding and recovery boundaries across the crash-safe mission and autonomy persistence stack, starting with `mission_control/recovery.py` and `core/autonomy/sqlite_persistence.py`, while maintaining the same corrupt-state fail-closed contract.
