# Execution-backed Mission Control demo

Run from Windows PowerShell at the repository root:

```powershell
.\run_demo.ps1
```

The script uses a disposable folder under `$env:TEMP`, the real `main.py --mission` entry point, the real `FileTool`, `ExecutionEngine`, and `ExecutionPolicy`, and a SQLite database. It does not touch `jarvis_test_workspace/`.

## Five real tasks and pass conditions

1. **List the 10 largest files and summarize them.** The mission planner emits two structured steps. Both must execute through the registered FileTool actions, return exit code 0, and persist stdout plus exact file paths and sizes.
2. **Summarize largest files as a standalone objective.** The planner must turn the objective into a real `summarize_files` tool step and persist text previews for the fixture's text files.
3. **Reject a destructive delete.** The existing `ExecutionPolicy` must block `file.delete` before tool execution; the mission and step record must preserve the denial reason and nonzero policy exit code.
4. **Kill and restart a real mission process.** `run_demo.ps1` starts a two-step mission, waits for the first step's durable checkpoint, force-kills the Python process, then launches `main.py --resume`. The second step must run and the mission must reach `COMPLETED` with both steps verified.
5. **Record a real tool failure.** Listing a missing directory must end `FAILED`, with the missing-path error, stderr and exit code persisted in SQLite.

## Evidence and recovery rules

- Mission steps are JSON task specifications, not arbitrary descriptive strings.
- A step is complete only after `ExecutionEngine.execute(Task(...))` returns `TaskStatus.COMPLETED` and the tool's exit code is zero.
- Each step stores tool/action/arguments, status, stdout, stderr, exit code, error, paths and timestamps.
- A restart resumes after the last verified completed step. If SQLite shows a step was still `running` when the process disappeared, recovery changes it to `FAILED` with an explicit unknown-outcome reason and does not replay it automatically.
- Destructive actions are not auto-approved. A policy decision other than `ALLOW` prevents the tool from running.

The CLI supports the bounded objective forms implemented in `mission_control/cli.py`; this is a deterministic vertical slice, not general-purpose natural-language planning yet.
