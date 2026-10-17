# Audit-Derived Reliability Tasks

## Verified baseline (2026-10-17)
- Branch: `feature/jarvis-control-center`; HEAD: `c720084` (`fix(swe): harden repository analysis`).
- Full suite: `1031 passed, 1 skipped in 33.86s` (exit 0), run with the project `.venv` and a temp directory outside the repository.
- Whole-repository Ruff: `275 findings`; top groups include `BLE001` 103, `RUF059` 41, `F841` 32, `S110` 25, `RUF022` 15, `SIM102` 12, and `UP035` 46 (Ruff's statistics output reports categories; counts overlap only if the same finding has multiple rules, so do not sum blindly).
- One skip is a Windows-specific shell-variable-expansion test guarded by `skipif(os.name != "nt")`; it is expected on non-Windows platforms and is not a failing test.
- Worktree contains pre-existing edits in `core/applications/installer.py` and `core/applications/permissions.py`, plus untracked `jarvis_test_workspace/`. These were inspected and are intentionally excluded from audit commits; do not overwrite, stage, or remove them.

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
