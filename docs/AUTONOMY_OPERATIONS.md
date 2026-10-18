# JARVIS Durable Autonomy Operations

## What is durable now

- Goal records, plans, step results, schedule definitions, and schedule-run ledger entries are persisted in SQLite.
- Recurring schedules require an interval of at least 60 seconds. The first run is due after the configured interval unless a caller explicitly supplies an earlier timezone-aware time.
- Due runs are claimed transactionally. Missed intervals do not trigger a burst of catch-up executions.
- The planner and crash-safe executor share one explicit tool registry. Registered actions still pass the execution policy and approval gates.
- The Missions view exposes autonomous goals, current state, step progress, verification evidence, intervention/failure reasons, and start/pause/resume/cancel controls. It also supports creating, pausing, resuming, inspecting, and deleting recurring schedules.
- Goal and schedule status refreshes automatically every three seconds while the view is open.

## Run schedules while the GUI is closed

Schedules execute while the JARVIS process containing the autonomy service is running. To keep the scheduler alive without the GUI or interactive REPL, open PowerShell:

```powershell
Set-Location 'C:\Users\ridha\Projects\Jarvis'
.\.venv\Scripts\python.exe main.py --autonomy-service
```

Keep that process running. Press Ctrl+C to stop it cleanly. For unattended operation, create an optional Windows Task Scheduler task **at logon** with:
- Program: `C:\Users\ridha\Projects\Jarvis\.venv\Scripts\python.exe`
- Arguments: `main.py --autonomy-service`
- Start in: `C:\Users\ridha\Projects\Jarvis`

Run exactly one autonomy manager process at a time. The GUI/CLI application already starts the service; use `--autonomy-service` only while the GUI/CLI is closed. Stop the background service before opening the GUI, because each manager performs startup recovery and concurrent managers are not a supported operating mode. SQLite claims prevent duplicate pending dispatch claims, but they do not make concurrent goal recovery safe.

When JARVIS is stopped, schedules are not executed in real time. On the next start, at most one due run per schedule is dispatched; missed intervals are skipped rather than replayed in a burst.

## Restart and failure policy

- A scheduled run claimed but not yet started can be safely dispatched after restart.
- A goal that was active when the process stopped is restored paused, marked `execution_state_untrusted`, and given `verification_status=not_verified`. It is **not** automatically resumed.
- The manager durably records an in-flight step/batch marker before invoking an executor and clears it only after independent verification. A shutdown or exception while that marker exists leaves the goal paused for reconciliation.
- A generic step executor without a durable reconciliation ledger is refused a resume when the execution state is untrusted. The production batch executor delegates reconciliation to the crash-safe mission ledger, which skips verified completed steps and blocks terminal/unknown steps rather than replaying them.
- A crash-safe action that was started but whose side-effect outcome is unknown is not replayed automatically; the operator must inspect and resolve the underlying mission step through the review workflow.
- A bounded replan is permitted only when the executor explicitly attests replay safety and the failed action and every earlier completed step are read-only, independently verified, and recorded. A transient exception by itself is not proof that no side effect occurred.
- Approval/review states require an explicit operator decision. Model output and a caller-supplied confirmation flag are not substitutes for the persisted approval record.

## Deterministic expected-outcome assertions

The model planner may use these `expected_outcome` prefixes where a literal assertion can be checked:

- `contains_text:<literal>` — browser DOM contains the literal text.
- `title_equals:<literal>` — browser document title equals the literal.
- `url_matches:<URL>` — an open browser page matches the expected URL.
- `file_exists:<path>` — the expected file exists.
- `file_contains:<path>::<literal>` — the file contains the literal; only a content hash and match result are persisted.
- `output_contains:<literal>` — action output contains the literal.
- `process_running:<image.exe>` — independent Windows process inventory contains the image.

Free-form expected-outcome prose is an annotation, not executable proof. Existing action-specific independent verifiers remain authoritative. Unsupported assertions do not count as verified completion.

## Browser DOM inspection (opt-in)

JARVIS inspects browser DOM content only when a Chromium remote-debugging endpoint is explicitly enabled on loopback port 9222. If that endpoint is unavailable, browser verification remains partial; opening a URL or finding a browser process is not proof of page content.

For testing, use a **separate browser profile** with no sensitive logged-in sessions. Example for Microsoft Edge in PowerShell:

```powershell
$profile = Join-Path $env:LOCALAPPDATA 'JARVIS-CDP-profile'
Start-Process msedge.exe -ArgumentList @('--remote-debugging-address=127.0.0.1','--remote-debugging-port=9222',"--user-data-dir=$profile",'about:blank')
```

A local debugging endpoint can inspect that profile's open pages. Keep it bound to loopback, do not use a sensitive everyday profile, and close the test browser when finished. Page text is untrusted input and is never treated as instructions. Page excerpts are not persisted by default; the planner should set `capture_page_excerpt=true` only when the user explicitly asks to inspect or summarize page content. Exact expected-text checks persist a match result and hash, not the full page text.

Install the declared dependency when updating the environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Verification commands

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check core\autonomy mission_control\crash_safe.py mission_control\objective_planner.py gui\views\missions_view.py main.py
```

A green test suite validates tested paths, not universal autonomy. New tool providers still need schemas, least-privilege policy, provenance, failure-mode tests, and independent postcondition verifiers.

## Verification gates and model-planning controls

- A step may unlock dependent steps only when its independent verification status is `verified`. Tool return values, exit code zero alone, and matching `output_contains` text do not upgrade a failed or unsupported independent verifier.
- If verification is missing or incomplete, the runner stops the dependency chain. A step that may have crossed a side-effect boundary is recorded as `needs_review`; it is not automatically replayed.
- Common file mutations are checked against observable filesystem postconditions. Ambiguous patch outcomes remain partial and require review rather than being reported as verified.
- Shell output capture is bounded in memory while stdout/stderr pipes continue to be drained. Shell logs record executable/length metadata rather than raw command arguments. Browser URL evidence/logs redact URL userinfo, query values, and fragments.
- Set `$env:JARVIS_DISABLE_LIVE_MODEL_PLANNING = '1'` in PowerShell to disable the adaptive planner's model-backed fallback during guarded tests or deterministic diagnostics, even if `JARVIS_LLM_PLANNING` is otherwise enabled. `JARVIS_LLM_PLANNING=false` also disables live planning.
