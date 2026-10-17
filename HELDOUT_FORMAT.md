# Held-out harness input format

The private input belongs outside the repository at C:\Users\ridha\jarvis_heldout\HELDOUT.md. Do not copy it into the repo or commit it. run_heldout.ps1 is the only code intended to read that file; it reports SHA-256 objective hashes rather than echoing objectives.

Use one case per heading:

~~~markdown
## case-id-01
Objective: List the 10 largest files in my Downloads folder and summarize them
Check: state=COMPLETED
Check: steps>=1
Check: completed_steps>=1
Check: all_steps_completed=true
Check: stdout_contains=some expected output fragment
~~~

Supported checks:
- state=COMPLETED (or another exact mission state)
- steps>=N / step_count>=N
- completed_steps>=N
- all_steps_completed=true
- step_status=completed (all returned steps must match)
- stdout_contains=<literal> / stdout_regex=<regex>
- stderr_empty=true
- os_exit_code=N (real shell process code only)
- normalized_code=N (normalized tool result only)
- path_exists=<path>

The harness runs objectives against the real filesystem and uses a persistent database under %LOCALAPPDATA%\JARVIS. It does not generate fixtures, modify the private file, or special-case objective wording. The current planner intentionally supports only its implemented objective grammar; unsupported objectives are reported as planner failures.
