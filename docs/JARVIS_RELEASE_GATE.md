# JARVIS Production-Readiness Release Gate

**Current disposition: NOT PROVEN PRODUCTION-READY.** This gate is evidence-based; a green unit-test suite alone is insufficient. Every critical row below must have a dated, reproducible passing result for the release candidate. Any `unknown`, `partial`, or missing evidence blocks the production-ready claim.

## Required gates

| Gate | Required evidence | Pass condition |
|---|---|---|
| Automated regression | `.venv\Scripts\python.exe -m pytest -q` | Zero failures; all skips explained and accepted |
| Hardened-module lint | `.venv\Scripts\ruff.exe check` on the CI hardened-module list, including executor containment modules and tests | Zero new findings; existing baseline exceptions documented |
| Runtime wiring | `smoke_test.py`, `main.py --help`, `mission_crash_safe.py --help`, `python -m mission_control.cli --help`, `compileall` | All exit successfully and smoke test confirms no unrequested external/state-changing action |
| Action containment | Exact reachable-entrypoint/action matrix plus `ExecutorManager.registration_audit()` for every instantiated manager | Every side-effecting action is isolated or has a separately reviewed equivalent hard-containment contract; no unreviewed `legacy-uncontained` registrations |
| Verification integrity | False-success tests per action family; inspect real postconditions, not just handler output | No step/mission is reported verified unless independent evidence matches the declared postcondition; unsupported/ambiguous verification fails closed |
| Crash recovery | Crash-stage matrix: before handler, during handler, after side effect/before persistence, after persistence/before finalization, and restart | Uncertain side effects become `needs_review`; no blind replay; attempts and real side-effect counts match expectations |
| Adversarial authorization | Malformed plans/arguments, untrusted confirmation-shaped fields, path/workspace escapes, nested shells, duplicate actions, timeout/worker failures | Denials happen before prohibited side effects; durable approval does not bypass policy/workspace checks |
| Local provider | `scripts/controlled_live_acceptance.py --check provider` against local Ollama | Expected marker returned and provider identity/model recorded; no cloud credentials or external network required |
| Browser/desktop integration | Run `--check browser` and `--check desktop` separately in a controlled session | Independent observable effect and cleanup evidence recorded; test side effects are identified and reconciled |
| Codex CLI/provider integration | Version/help/health checks plus a controlled end-to-end task in a disposable workspace | Actual task result independently verified; no edits outside disposable workspace; auth/model/config captured without recording secrets |
| Cloud providers | Provider-specific controlled integration test | **Do not invoke a paid endpoint until the user explicitly authorizes that usage.** Without authorization, mark `NOT RUN ? authorization required`, never passed |
| Release candidate | Re-run gates on exact candidate revision and archive logs/results | All required gates pass; known limitations and residual risks signed off; no unreviewed dirty-tree changes in the release artifact |

## Safe command set (PowerShell, repository root)

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check main.py tools\shell.py tools\file.py core\execution_policy.py core\skills_runtime.py core\context_budget.py core\bootstrap\bootstrapper.py core\autonomy\manager.py core\autonomy\sqlite_persistence.py core\executor\manager.py core\executor\isolated_handler.py core\executor\isolated_tool_worker.py mission_control\crash_safe.py mission_control\crash_store.py mission_control\crash_cli.py mission_control\execution.py mission_control\mission.py tests\test_executor_containment_contract.py tests\test_isolated_handler.py
.\.venv\Scripts\python.exe -m compileall -q core mission_control tools providers
.\.venv\Scripts\python.exe smoke_test.py
.\.venv\Scripts\python.exe main.py --help
.\.venv\Scripts\python.exe mission_crash_safe.py --help
.\.venv\Scripts\python.exe -m mission_control.cli --help
.\.venv\Scripts\python.exe scripts\controlled_live_acceptance.py --check provider
```

Browser and desktop live checks are intentionally separate because they open UI/processes. Run them only when a human can inspect the resulting session and cleanup. Never use a live test against real user data or a production account when a disposable workspace/local endpoint suffices.

## Current known blockers

- Generic two-argument `ExecutorManager.register_action` calls remain backward-compatible and are reported as `legacy-uncontained`; all registrations must be migrated, removed, or individually justified before a production release.
- `side_effecting=True` rejects raw callbacks and requires `IsolatedToolHandler`, but process isolation is not an OS security sandbox and does not itself verify outcomes.
- Live local Ollama/browser/desktop checks were previously observed passing. Codex Desktop CLI and cloud-provider end-to-end tasks are not yet verified. No paid provider may be used without explicit authorization.
- Browser visual/page-state verification beyond the local loopback test, richer desktop interaction, exhaustive crash-boundary fault injection, and whole-process mission deadlines remain open.
- A timeout is `OUTCOME UNKNOWN`; recovery must reconcile external state and must not automatically replay an uncertain side effect.

Do not call JARVIS production-ready until these blockers are closed or explicitly accepted by the responsible release owner with documented compensating controls.
