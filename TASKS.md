# Audit-Derived Reliability Tasks

## Historical verified baseline (2026-10-17; superseded by current hardening pass)
- Branch: `feature/jarvis-control-center`; HEAD: `c720084` (`fix(swe): harden repository analysis`).
- Full suite: `1031 passed, 1 skipped in 33.86s` (exit 0), run with the project `.venv` and a temp directory outside the repository.
- Whole-repository Ruff: `275 findings`; top groups include `BLE001` 103, `RUF059` 41, `F841` 32, `S110` 25, `RUF022` 15, `SIM102` 12, and `UP035` 46 (Ruff's statistics output reports categories; counts overlap only if the same finding has multiple rules, so do not sum blindly).
- One skip is a Windows-specific shell-variable-expansion test guarded by `skipif(os.name != "nt")`; it is expected on non-Windows platforms and is not a failing test.
- Worktree contains pre-existing edits in `core/applications/installer.py` and `core/applications/permissions.py`, plus untracked `jarvis_test_workspace/`. These were inspected and are intentionally excluded from audit commits; do not overwrite, stage, or remove them.

Current hardening verification is recorded in [`docs/JARVIS_HARDENING_STATUS.md`](docs/JARVIS_HARDENING_STATUS.md); the current wired entry points and mission architecture are in [`docs/ARCHITECTURE_CURRENT.md`](docs/ARCHITECTURE_CURRENT.md).

## Checklist
- [x] **Bound identity prompt cache to the manager instance:** replace the class-level `lru_cache` on `IdentityManager.build_planner_prompt` with a bounded per-instance cache; add regression coverage for cache hits and eviction; run identity tests and targeted Ruff.
- [x] **Remove bare exception handlers from environment probing:** replace the two bare `except:` clauses in `scripts/evaluate_intelligence.py` with the expected subprocess/OS exception types; compile the script and run relevant evaluation tests.
- [x] **Make best-effort failures observable without leaking exception payloads:** replace production `except Exception: pass` sites reported by Ruff `S110` with safe debug diagnostics that log only exception type, and remove the broad swallowed cleanup exception in `tests/test_second_pass_routing.py`; verify targeted `S110` and focused affected tests.
- [x] **Remove private storage access from image asset ingestion:** expose `ProjectManager.get_asset_absolute_path()` through its existing asset-manager facade, use it in `AssetPipeline`, and assert the resolved asset path in the image pipeline test.
- [x] **Final regression gate:** run the complete test suite, full Ruff statistics, `git diff --check`, compile checks, and review the final staged diff; record actual outcomes in `NOTES.md`.

## Scope guard
The remaining Ruff findings are an audit backlog, not permission for blind auto-fixes. Broad exception handling and unused-variable findings require per-call-site review; only change them when behavior can be preserved and verified. Third-party content and the untracked local benchmark workspace must not be modified as part of this pass.

## Next execution pass ? executor lifecycle
- [x] **Preserve queued work during dispatcher shutdown:** add a regression proving a dequeued task is re-enqueued if shutdown begins before a worker accepts it; make dispatch assignment and shutdown mutually exclusive.
- [x] **Cancel and join executor workers on shutdown:** have worker shutdown cooperatively cancel its active context, ensure pending assignments receive a terminal callback, add bounded worker joins without losing references to still-alive threads, and test cancellation plus timeout behavior.
- [x] **Close every path-backed SQLite connection:** track per-thread SQLite handles and close them safely from `SqliteMissionRepository.close()`; verify the multi-thread repository regression and SQLite persistence tests.
- [x] **Full regression gate and commit:** run executor/runtime focused tests, the complete pytest suite, targeted Ruff, compileall and diff check; update NOTES with actual output and commit only the scoped lifecycle changes.

## Next execution pass ? Agent timeout isolation
- [x] **Prevent late executor completion from mutating timed-out tasks:** execute a detached task snapshot, copy terminal results back only when the future finishes within its timeout, and cancel futures when possible after timeout.
- [x] **Track execution futures through Agent shutdown:** prevent submit/close races, cancel queued futures during close, and ensure completed futures are removed from tracking.
- [x] **Regression gate:** test late completion after timeout, Agent close with queued/running work, run focused Agent tests plus the full suite, Ruff, compileall and diff check; record any non-cooperative running-tool limitation.


## Next execution pass - mission approval correctness
- [x] **Make deploy approval genuinely pending until explicit approval:** have the executor register pending approval without pre-approving the step; make approval manager updates idempotent; cover the real approval round-trip with regressions.
- [x] **Verify and document:** run focused mission-control tests, relevant Ruff and compile checks, inspect diff, update NOTES with actual results, and commit only scoped files if all checks pass.
- [x] **Preserve approval state through recovery:** checkpoint and restore pending and approved steps, with backward-compatible defaults for older checkpoints and a crash-recovery regression.
- [x] **Fail closed on unresolved mission dependencies:** treat missing dependency IDs as blocked rather than silently skipping them; test that registration of the dependency allows the mission to proceed later.


## Next execution pass - execution policy configuration
- [x] **Honor explicitly empty plugin/MCP allowlists:** distinguish `None` (use secure defaults) from an empty set (deny every tool), and add regressions for both sources.
- [x] **Verify and document:** run policy tests, changed-file Ruff, critical policy lint, compile checks and diff review; record actual results and commit only scoped files.


## Next execution pass - skill-source risk enforcement
- [x] **Deny high-risk actions from skill-originated requests:** ensure SKILL cannot fall through the high-risk policy branch and inherit an implicit allow; add regression coverage.
- [x] **Verify and document:** run execution-policy tests, changed-file Ruff, critical lint, compile and diff checks; document and commit the scoped fix.


## Next execution pass - unknown source fail-closed
- [x] **Reject unrecognized capability source values:** deny invalid source labels before any tool/action allow logic; add a regression for a destructive request from an unknown source.
- [x] **Verify and document:** run policy tests, full suite after this third task, changed-file Ruff, critical lint, compile and diff checks; record outcomes and commit scoped files.


## Next execution pass - shell policy confirmation boundary
- [x] **Prevent untrusted shell sources from reusing core confirmation:** when plugin/MCP requests reach a high-risk shell command, deny them even if `user_confirmed=True`; add regressions for both sources.
- [x] **Verify and document:** run execution-policy and shell tests, then the full suite after the third task; run changed-file Ruff, critical lint, compile and diff checks, and commit only scoped files.
- [x] **Normalize every supported shell argument alias before policy evaluation:** include `cmd`/`args` and equivalent aliases, so the policy evaluates the same effective command as `ShellTool`; add a regression using action `run`.
- [x] **Recognize package-manager install variants as high-risk shell commands:** cover `pip3`, `python -m pip`, `npm ci`, `pnpm add`, `yarn add`, and `uv add` while preserving existing destructive-command decisions.


## Execution-backed Mission Control vertical slice — 2026-10-17
- [x] Build one CLI-reachable mission flow that converts a supported objective into explicit tool/action/argument steps; no free-form step may be marked complete without a real tool result.
- [x] Route each step through the existing `ExecutionPolicy` before invoking a real registered tool; persist per-step status, stdout/result, paths, error and exit code in durable storage.
- [x] Make restart behavior explicit: recover only verified successful steps, and fail a running/in-flight step cleanly with a persisted reason rather than assuming it completed.
- [x] Add `run_demo.ps1`, `DEMO.md` with five real tasks, and a full end-to-end test using the real executor and a real tool (no mocked executor); the full demo passed with all five tasks in one run.
- [x] Record baseline and each failure/fix in `NOTES.md`; next capability milestone recorded below.


## Next milestone — model-driven, dependency-aware mission planning
- [x] Add provider-backed structured planning for objectives not handled by the bounded deterministic fast path; validate the entire plan, reject unsupported/malformed/unsafe actions, and expose only capabilities actually registered by the crash-safe execution engine.
- [x] Add stable step IDs, dependency graph validation/topological ordering, bounded output references (for example, `{"$ref":"discover.result.files.0.path"}`), persisted-result resolution, and runtime type checks before invoking dependent tools.
- [x] Add a reusable local-model evaluation harness and varied cases for filesystem inspection, multi-step result use, browser lookup, app launch, and ambiguous requests. The harness measures plan validity, tool-sequence accuracy, unsupported-request handling, and latency without executing generated plans.
- [x] Implement one bounded model-driven replan after an eligible failure, only when the prior plan contains replay-safe filesystem actions and the failure is not policy/approval/unknown-side-effect related. Preserve prior verified evidence in goal metadata, omit raw file contents (store a digest for read-file results), and require every replacement plan to pass the same registered-tool/schema/dependency validation.
- [x] Add durable independent postcondition checks for supported filesystem actions (`read_file`, `list_directory`, `list_largest_files`, `summarize_files`, `directory_file_stats`, `extension_counts`, `list_directory_details`, and `ensure_text_files`). Persist per-step verification evidence and expose mission-level `verified`/`partial`/`not_verified`; actions without an independent verifier are explicitly not reported as independently verified.
- [x] Add a Mission Control GUI page for persisted mission/step evidence, verification status, legacy and crash-safe pending approvals, explicit approve/reject controls, resume, and needs-review retry/abandon actions. Approval is a durable, separate action; execution requires a second explicit resume confirmation. Preserve the configured execution policy and fail closed when the registry/policy is unavailable.
- [x] Add independent Windows process-inventory verification for supported desktop app launches. Browser actions validate the HTTP(S) destination and independently confirm a supported browser process; when local Chromium DevTools Protocol is enabled at `127.0.0.1:9222`, the verifier checks that the requested URL is present in an open page. Without that endpoint, status remains `partial`.
- [x] Expand local-model evaluation to 16 cases covering filesystem tasks, browser/desktop requests, unsupported capabilities, ambiguous destructive requests, and two model-generated recovery alternatives. The report is `evaluation/model_planner_eval_20261017_extended.json`; planning-only evaluation did not execute any generated actions.
- [x] Extend the crash-safe engine and model capability manifest to include additional explicitly registered tools. New registered tools require explicit operator approval by default; arbitrary/unregistered actions and model self-authorization remain blocked. The planner and execution schema are deliberately retained as safety boundaries rather than bypassed.
- [x] Add deterministic browser page-content/title/URL checks through the explicitly enabled loopback CDP inspection channel. Arbitrary natural-language `expected_outcome` prose remains unsupported as proof; only deterministic assertions and action-specific verifiers can establish verified completion.
- [x] Exercise end-to-end recovery with controlled failures, persisted evidence, a replacement mission, and final-state checks across filesystem/browser tool families. The 16-case local-model benchmark remains planning-only; live-model execution reliability is not inferred from it.
- [ ] Expand autonomy only through capability providers with explicit schemas, provenance, execution policies, approval rules, and independent verifiers. Do not enable arbitrary shell/code or bypass the validated plan schema as a shortcut to “general-purpose” behavior.


## Crash-safe mission execution + held-out harness — 2026-10-17
- [x] Add a durable write-ahead step record with deterministic idempotency key before tool invocation; persist verified output afterward, separating OS `exit_code` from tool `normalized_code` in the new crash-safe CLI path.
- [x] On recovery, re-run only explicitly idempotent read-only actions; fail/needs-review side-effecting steps left `started` with a recorded unknown-outcome reason.
- [x] Add real subprocess kill tests after a side effect but before result persistence, and during a long-running step; assert exactly-once-or-flagged semantics.
- [x] Add `run_heldout.ps1` that reads `C:\Users\ridha\jarvis_heldout\HELDOUT.md` only inside the script, hashes objectives, runs the real crash-safe CLI against the real filesystem, evaluates adjacent declarative checks, and reports failure classes without special-casing objective text. Syntax-checked only; private objectives intentionally not run.
- [x] Preserve unrelated working-tree changes and `jarvis_test_workspace/`; report held-out as unverified until the user runs it with their private file. Historical blocker resolved in the current working tree: `main.py` now delegates mission execution to the crash-safe runner with an explicit workspace boundary and verification-aware exit semantics.


## Autonomy integration hardening — 2026-10-17
- [x] Add a whole-plan executor contract so the durable Mission Control runner is invoked once per autonomous goal, rather than once per step with the full mission repeated.
- [x] Validate persisted plan/mission metadata and align each returned tool/action result with the corresponding planned step.
- [x] Require independently verified mission and step outcomes before the crash-safe autonomy adapter can return success; block automatic replanning when partial work is known to have occurred.
- [x] Add unit regressions and a real two-step autonomous-goal integration test using SQLite goal persistence and the real crash-safe mission runner.
- [x] Finish the full regression gate and record the exact result in NOTES: 1148 passed, 1 skipped; Ruff/critical lint, compileall, and diff checks passed.
- [x] Complete deterministic browser page-content/title/URL and supported expected-outcome verification; arbitrary free-form semantic prose remains explicitly unsupported.
- [ ] Inject controlled failures after a verified step and prove safe recovery/final-state correctness across multiple capability families.
- [x] Add durable scheduled goals/background execution with pause/disable, missed-run handling, single-run locking, and startup reconciliation; covered by `core/autonomy/scheduling.py` and scheduling regression tests.
- [x] Inject the same explicit registered-tool registry into model planning and crash-safe execution; schemas are manifest-derived and additional registered tools remain confirmation-gated. Provenance/verification requirements still apply to future provider types.
- [x] Share one explicit registered-tool capability registry between autonomy planning and execution; keep model-generated shell execution disabled.
- [x] Preserve approval/reconciliation as a durable paused goal state instead of incorrectly turning WAITING_APPROVAL/NEEDS_REVIEW/RECOVERY_REQUIRED into a terminal goal failure; require explicit resume after operator resolution.


## Durable autonomy milestone — 2026-10-17
- [x] Durable recurring goal schedules with SQLite ledger, atomic due/pending claims, pause/disable/delete, missed-run coalescing, and startup reconciliation.
- [x] Add a background autonomy service mode (`main.py --autonomy-service`) so schedules can continue while the GUI is closed; document optional Windows Task Scheduler setup without installing it automatically.
- [x] Connect goal and schedule lifecycle controls to Mission Control GUI with auto-refreshing progress, verification evidence, intervention reasons, and explicit start/pause/resume/cancel controls.
- [x] Inspect Chromium DOM through opt-in loopback CDP and add deterministic browser text/title/URL plus file/output/process expected-outcome assertions; default page excerpts are not persisted.
- [x] Inject a real read-only failure after a verified step, replan using persisted evidence under a distinct mission ID, and verify final state.
- [x] Inject a cross-family file/browser failure and assert uncertain browser actions are not automatically replayed.
- [x] Final full regression suite and post-final-edit lint/compile/diff gate: 1161 passed, 1 skipped; Ruff, critical lint, compileall, CLI help, and diff checks passed.
- [x] Keep free-form semantic prose from being treated as proof. Deterministic assertions and action-specific independent verifiers decide verified completion; future action families must add their own verifiers. Browser DOM inspection remains opt-in and requires local CDP enablement.


## Trustworthy execution-state recovery follow-up — 2026-10-17
- [x] Persist in-flight step/batch markers before executor invocation; only clear markers after independently verified results are durably recorded.
- [x] Mark active goals untrusted on restart and when stopping/pausing during an in-flight action; refuse generic executor replay without a durable reconciliation ledger.
- [x] Route production recovery through the crash-safe mission ledger and prove that an explicit resume does not replay a terminal side-effecting browser failure.
- [x] Require an explicit replay-safety attestation before bounded replanning; distinguish known policy denial from uncertain side-effect outcomes.
- [x] Add regression tests for unverified results, restart reconciliation, generic plan replay after intervention, and cross-tool-family no-replay recovery.
- [x] Final validation: 1163 passed, 1 skipped; scoped Ruff, critical lint, compileall, CLI-help smoke test, and `git diff --check` passed.

## 2026-10-17 hardening follow-up

- [x] Unify `JARVIS_DISABLE_LIVE_MODEL_PLANNING` with the adaptive planner's live-model gate and add a regression test.
- [x] Harden quoted/path-qualified nested-shell detection and ensure inline Python commands with quoted/absolute interpreter paths enter the approval policy.
- [x] Remove filename-based exceptions that allowed project-root mutations of `test_*` and `jarvis_session_test*` paths.
- [x] Strip sensitive environment variables before launching Codex CLI and ensure the GUI Missions view uses the configured mission database.
- [x] Require independent verification before dependent steps can execute or a mission can return success; uncertain side effects enter `needs_review`.
- [x] Add independent postcondition checks for common file mutations and prevent `output_contains` from overriding failed or unsupported independent verification.
- [x] Bound subprocess stdout/stderr capture while continuing to drain pipes; redact URL userinfo/query values and shell command arguments from logs.
- [x] Final verification: **1,203 passed, 1 skipped**; scoped Ruff, compileall, smoke test, CLI help, and `git diff --check` passed. Full Ruff comparison found zero new tracked-file signatures (11 new signatures are confined to existing untracked workspace/vendor files). No commit/push was performed.
