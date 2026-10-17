# JARVIS AIOS security model

## Assets to protect

- Provider credentials in the local `.env` file and process environment.
- Browser authentication state, passwords, private keys and local user data.
- Source code, tests, memory/knowledge databases and application configuration.
- Local desktop sessions and any remote MCP/federation credentials.

## Trust boundaries

1. **Model output is untrusted.** The model proposes tool/action/arguments; the registry, validator and execution policy decide whether the request may run.
2. **First-party local actions are not equivalent to external actions.** Plugin and MCP sources have restricted tool sets; they must not inherit the local agent's permissions.
3. **Desktop actions pass through a separate guard.** The Codex agent is instructed to use only `jarvis-desktop`. High-risk browser JavaScript, cookie access, uploads and file-transfer tools are not exposed. State-changing desktop/browser tools require a local Windows approval dialog; shell windows and Delete-key shortcuts are blocked. Browser navigation is restricted to valid HTTP(S) URLs without embedded credentials, MCP responses are correlated by request ID, and page/UI content is treated as untrusted input.
4. **Remote MCP is opt-in.** The intended default bind address is loopback. A non-loopback bind requires TLS configuration and authentication. Do not expose it to a public network without a separate deployment review.
5. **Federation is experimental.** It uses TLS transport and authenticated/encrypted payload mechanisms; peers, key distribution, rotation and endpoint trust still require operational controls before production use.

## Files and shell

The file tool resolves paths and enforces protected-path checks. Sensitive credential/browser-auth paths are blocked, including for `open_file`. The shell tool uses `shell=False`, a constrained command allowlist, bounded timeouts/output, workspace checks and filtered environment variables. Simple `echo`, `dir`, `type` and `cat` commands are handled internally rather than routed through a command interpreter.

**Important residual risk:** running `pytest` or other development tools executes code from the workspace. This shell allowlist is not an OS-level sandbox. Do not run tests, plugins, model-generated patches or downloaded source from an untrusted repository under your primary Windows account. Use Windows Sandbox/VMs or a restricted account for untrusted code.

## Secrets

- The local `.env` file is plain text at rest. It is git-ignored, but a local user or malware with access to your profile can still read it.
- Process environment values take precedence over `.env`; the dotenv loader does not overwrite existing keys.
- Configuration diagnostics show credential state as `PRESENT`/`ABSENT`, not actual values.
- Shell subprocess environments filter common API keys, tokens, passwords, authorization, private-key, cookie and interpreter-injection variables.
- Do not paste API keys, browser cookies, OAuth tokens or recovery codes into prompts, logs or source files. Rotate any secret that is accidentally exposed.

## Cloud versus local processing

When `JARVIS_MODE=local`, the router is intended to restrict model execution to the local provider. In hybrid/assistant/developer modes, configured cloud providers may receive prompts over HTTPS. A configured Gemini key plus the default hybrid mode may cause Gemini to be selected even if Ollama is installed. Set `JARVIS_MODE=local` when local-only processing is required.

Local desktop automation also launches a separate Codex CLI agent authenticated with the user's account. It is not the same thing as this ChatGPT conversation, and account usage/policies still apply.

## Security verification performed

The current maintenance pass added regression tests for sensitive-file opening, shell command restrictions, environment filtering, timeout validation, dotenv precedence and invalid numeric configuration. The full pytest suite passed locally on October 10, 2026; see the root README for the recorded count.

## Remaining risks and operational requirements

- The local approval dialog depends on an interactive Windows session; do not run write-enabled desktop automation unattended.
- UI approval is not a proof that an action is harmless. Verify the target window, action and outcome.
- Secrets in memory/process environments remain accessible to same-user processes and debuggers.
- Dependencies need continuous vulnerability scanning and controlled updates.
- Remote MCP/federation require key rotation, audit retention, rate limiting, deployment-specific network rules and incident response.
- Security guarantees have not been independently audited or penetration-tested.
