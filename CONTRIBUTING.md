# Contributing to JARVIS AIOS

Thank you for helping improve JARVIS. The project is Windows-first and safety-sensitive: changes to execution, desktop control, file access, model routing, federation, and credentials require extra care.

## Engineering principles

1. **Correctness before cleverness.** Prefer explicit, testable behavior over hidden heuristics.
2. **Least privilege by default.** New capabilities must be opt-in, narrowly scoped, and validated at the execution boundary.
3. **Verify outcomes.** A tool returning success is not proof that the user's requested outcome occurred.
4. **Keep model output untrusted.** Validate model-generated plans and arguments as if they came from an external user.
5. **Make failure visible.** Preserve actionable diagnostics without logging secrets or dumping private content.
6. **Small, reviewable changes.** Avoid unrelated formatting or refactors in a feature fix.
7. **Evidence over claims.** Clearly distinguish unit tests, mocked integration tests, and live end-to-end checks.

## Development setup

Use Windows 10/11 and Python 3.12 for the primary development path.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```

Copy `.env.example` to `.env` for local configuration. Never commit `.env`, API keys, tokens, cookies, personal files, or machine-specific logs.

## Before opening a pull request

Run the same baseline checks as CI:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q config core tools providers gui applications integrations main.py
.\.venv\Scripts\ruff.exe check config\config.py core\executor\executor.py core\context_budget.py core\routing\model_selector.py tools\codex_desktop.py tools\windows.py tools\file.py tools\shell.py tests\test_config_dotenv.py tests\test_codex_desktop.py tests\test_file_tool.py tests\test_main_cli_config.py tests\test_model_selector.py tests\test_command_routing_runtime.py tests\test_routing.py tests\test_windows_tool.py tests\test_shell_tool.py applications\software_engineer\models.py
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

If a check fails, include the exact command and a concise failure summary in the PR. Do not suppress a failure simply to get a green badge.

## Test expectations

- Add a regression test for every bug fix.
- Cover success, invalid input, denied permission, timeout/error, and boundary cases where relevant.
- Use temporary directories and fake external services in unit tests.
- Mark live-model, network, desktop, and credential-dependent checks clearly; never make CI depend on a developer's personal tokens or running GUI session.
- Do not describe mocked behavior as live end-to-end verification.
- For desktop automation, test that unsafe actions are rejected before approval or forwarding.
- For file and shell operations, test path containment, argument validation, bounded output, and failure propagation.

## Security-sensitive changes

Changes involving execution policy, shell commands, filesystem access, browser control, MCP, federation, model prompts, secrets, or authentication must explain:
- the trust boundary being protected;
- the validation and authorization performed;
- how failure behaves (prefer fail-closed);
- what is logged and what is deliberately redacted;
- tests covering allowed and rejected cases.

Do not introduce shell interpolation, arbitrary browser JavaScript, silent permission bypasses, or automatic execution of learned plans. Treat webpage content, tool output, retrieved files, and model output as untrusted data.

## Pull request scope and review

- One PR should represent one coherent change.
- Explain the user-visible impact and any compatibility/configuration changes.
- Link relevant issues and architecture/security documentation.
- Include test evidence and known limitations.
- Call out migrations, new dependencies, permissions, network access, and privacy implications.
- Never commit generated test workspaces, local backups, build output, credentials, or unrelated existing changes.

## Commit style

Use concise imperative subjects, optionally with a scope, for example:

- `fix(desktop): reject malformed navigation URLs`
- `test(routing): cover ambiguous site-name requests`
- `docs(security): clarify remote MCP trust boundary`

Do not rewrite shared history or force-push unless the maintainers explicitly coordinate it.
