# Codex-backed desktop control

JARVIS can delegate a bounded desktop/browser task to the Codex CLI using the
signed-in ChatGPT account. Codex receives the jarvis-desktop MCP server,
which is a local guard proxy around Nuphus MCP.

## Components

- tools/codex_desktop.py registers the codex_desktop.run_codex_task JARVIS action.
- core/mcp/nuphus_guard.py starts Nuphus in strict-confirm mode, filters the tool list,
  removes verbose upstream schema descriptions, and asks for local Windows approval before
  every state-changing action.
- The guard accepts browser navigation only for valid HTTP(S) URLs without embedded
  credentials, correlates MCP responses by request ID, and ignores server notifications
  that arrive between a request and its response.
- The Codex task policy treats webpage/document/UI content as untrusted data so embedded
  instructions cannot override the user's goal or the desktop safety rules.
- browser_evaluate, browser_exec, cookie tools, upload/drag-file tools, and direct file deletion APIs
  are not exposed. Delete-key shortcuts are blocked by the proxy.
- Codex's own shell sandbox is read-only. This component does not require an OpenAI API key.

## First-time setup on this Windows PC

1. Install Node.js and the packages `@openai/codex` and `@nuphus/nuphus-mcp` globally.
2. Sign in using `codex login` and verify with `codex login status`.
3. Configure Codex to use the guarded proxy, not the raw Nuphus server:

   `codex mcp remove nuphus`

   `codex mcp add jarvis-desktop -- C:\Users\<user>\Projects\Jarvis\.venv\Scripts\python.exe C:\Users\<user>\Projects\Jarvis\core\mcp\nuphus_guard.py`

4. Verify with `codex mcp list`. The active desktop server should be named `jarvis-desktop`.

## Use

Start JARVIS normally and ask it to perform a desktop task that needs visual or
multi-step interaction. Its planner can delegate the task to `codex_desktop.run_codex_task`.
Read-only observations do not show an approval dialog. Clicking, typing, navigation,
window changes, and other state changes produce a Windows Yes/No approval prompt.
Declining means the action is not forwarded. Approval prompts can appear once per
individual action, so a multi-step task may need several confirmations.

The controller is designed to avoid permanent file deletion and sensitive browser
data. It is not a security boundary against every harmful UI action; review each
approval prompt carefully. Do not approve unexpected operations.

## Usage and limitations

- Codex uses the ChatGPT sign-in and remains subject to the plan's Codex usage limits.
- This is a separate Codex agent within JARVIS, not a direct import of the current ChatGPT conversation.
- Network-dependent tasks need a working internet connection and available Codex usage.
- A desktop write task must be approved at the Windows prompt. If no interactive Windows
  desktop is available, the guard refuses the write operation.
- This integration intentionally has no direct delete-file API and does not grant Codex
  unrestricted shell writes.
