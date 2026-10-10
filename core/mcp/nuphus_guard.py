"""Guarded stdio MCP proxy for Nuphus desktop automation.

Only an explicit allow-list is exposed. Every state-changing tool call prompts
for local Windows confirmation before it is forwarded to Nuphus in strict mode.
High-risk browser execution, cookies, and file transfer tools are never exposed.
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

LOGGER = logging.getLogger("jarvis.nuphus_guard")
PROTOCOL_VERSION = "2024-11-05"

READ_ONLY_TOOLS = frozenset({
    "desktop_screen_size",
    "desktop_windows_list",
    "desktop_window_info",
    "desktop_perceive",
    "desktop_targets_list",
    "desktop_semantic_observe",
    "desktop_semantic_candidate",
    "desktop_verify_state",
    "browser_snapshot",
    "browser_extract",
    "browser_wait_for",
    "browser_list_downloads",
    "browser_list_tabs",
})

CONFIRMABLE_TOOLS = frozenset({
    "desktop_screenshot",
    "desktop_window_screenshot",
    "desktop_window_activate",
    "desktop_window_move",
    "desktop_window_resize",
    "desktop_mouse",
    "desktop_input",
    "desktop_clipboard_clean",
    "desktop_clipboard_write",
    "desktop_target_bind",
    "desktop_semantic_action",
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_press",
    "browser_scroll",
    "browser_screenshot",
    "browser_back",
    "browser_forward",
    "browser_close",
    "browser_new_tab",
    "browser_switch_tab",
})

ALLOWED_TOOLS = READ_ONLY_TOOLS | CONFIRMABLE_TOOLS
TOOL_DESCRIPTIONS = {
    "desktop_screen_size": "Read the desktop resolution.",
    "desktop_screenshot": "Capture the screen; local approval required.",
    "desktop_windows_list": "List visible windows with handles, titles, and bounds.",
    "desktop_window_activate": "Activate a chosen window; local approval required.",
    "desktop_window_screenshot": "Capture a chosen window; local approval required.",
    "desktop_window_move": "Move a window; local approval required.",
    "desktop_window_resize": "Resize a window; local approval required.",
    "desktop_window_info": "Inspect a window by handle.",
    "desktop_perceive": "Read visible UI text and controls using local OCR.",
    "desktop_mouse": "Use mouse position, movement, click, or scroll; approval required for changes.",
    "desktop_input": "Type text or press a shortcut in a selected window; approval required.",
    "desktop_targets_list": "List available application and window references.",
    "desktop_target_bind": "Bind a selected application/window; local approval required.",
    "desktop_semantic_observe": "Inspect UI accessibility elements in a window.",
    "desktop_semantic_candidate": "Read details for an observed UI candidate.",
    "desktop_semantic_action": "Perform a stable accessibility action; local approval required.",
    "desktop_verify_state": "Verify a window or UI postcondition without changing state.",
    "browser_navigate": "Navigate the browser to an HTTP(S) URL; approval required.",
    "browser_snapshot": "Read the current browser accessibility/DOM snapshot.",
    "browser_click": "Click a browser element; approval required.",
    "browser_type": "Type into a browser element; approval required.",
    "browser_press": "Press a browser key or shortcut; approval required.",
    "browser_scroll": "Scroll the browser page; approval required.",
    "browser_extract": "Extract readable text from the current browser page.",
    "browser_close": "Close the controlled browser; approval required.",
    "browser_back": "Navigate back in browser history; approval required.",
    "browser_forward": "Navigate forward in browser history; approval required.",
    "browser_wait_for": "Wait for a browser element state.",
    "browser_list_downloads": "List the browser download directory entries.",
    "browser_new_tab": "Open a new browser tab; approval required.",
    "browser_list_tabs": "List browser tabs with their URLs and titles.",
    "browser_switch_tab": "Switch to a browser tab; approval required.",
}


def _compact_schema(value: Any) -> Any:
    """Remove verbose vendor help text while retaining JSON Schema constraints."""
    if isinstance(value, dict):
        return {
            key: _compact_schema(child)
            for key, child in value.items()
            if key not in {"description", "title", "examples", "example"}
        }
    if isinstance(value, list):
        return [_compact_schema(item) for item in value]
    return value


SENSITIVE_KEYS = frozenset({
    "password", "passwd", "cookie", "cookies", "token", "secret",
    "credential", "authorization", "api_key", "apikey", "access_code",
})


def _nuphus_command() -> list[str]:
    """Find Nuphus without invoking a shell or trusting arbitrary arguments."""
    direct = shutil.which("nuphus-mcp")
    if direct and Path(direct).suffix.lower() not in {".cmd", ".bat", ".ps1"}:
        return [direct, "--confirm-write"]

    appdata = os.environ.get("APPDATA")
    node = shutil.which("node")
    if appdata and node:
        cli = Path(appdata) / "npm" / "node_modules" / "@nuphus" / "nuphus-mcp" / "bin" / "cli.js"
        if cli.is_file():
            return [node, str(cli), "--confirm-write"]

    raise RuntimeError(
        "Nuphus MCP was not found. Install @nuphus/nuphus-mcp globally and ensure Node.js is on PATH."
    )


def _redact(value: Any, key: str = "") -> Any:
    if any(sensitive in key.casefold() for sensitive in SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value[:20]]
    if isinstance(value, str) and len(value) > 240:
        return value[:240] + "… [truncated]"
    return value


_SHELL_MARKERS = ("powershell", "pwsh.exe", "cmd.exe", "command prompt", "windows terminal", "terminal.exe", "consolewindowclass", "conhost.exe", "wsl.exe")


def _strings_for_window_check(value: Any, key: str = "") -> list[str]:
    if isinstance(value, dict):
        picked: list[str] = []
        for child_key, child_value in value.items():
            if str(child_key).casefold() in {"title", "process_name", "class_name", "app_name", "process_path", "name", "window_title", "app_id"}:
                picked.extend(_strings_for_window_check(child_value, str(child_key)))
        return picked
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _strings_for_window_check(child)]
    return []


def _is_shell_window_info(info: dict[str, Any]) -> bool:
    values = _strings_for_window_check(info)
    joined = " ".join(values).casefold()
    return any(marker in joined for marker in _SHELL_MARKERS)


def _delete_key_is_forbidden(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Hard-block keyboard deletion shortcuts at the desktop-control boundary."""
    if tool_name == "desktop_input" and arguments.get("mode") == "hotkey":
        keys = arguments.get("keys") or []
        return any("delete" in str(key).casefold().replace(" ", "") for key in keys)
    if tool_name == "browser_press":
        return str(arguments.get("key", "")).casefold().strip() == "delete"
    return False


def _browser_navigation_is_forbidden(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Restrict browser navigation to ordinary HTTP(S) URLs without userinfo."""
    if tool_name != "browser_navigate":
        return False
    raw_url = arguments.get("url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        return True
    try:
        parsed = urlsplit(raw_url.strip())
        # Accessing .port validates the authority instead of accepting malformed ports.
        _ = parsed.port
        # Reject script/file/data/custom schemes and URLs that embed credentials.
        return (
            parsed.scheme.casefold() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        )
    except ValueError:
        return True


def _confirm_local(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Require a real, local Windows approval for all state-changing actions."""
    if os.name != "nt":
        # Fail closed: headless/non-Windows execution cannot approve a desktop write.
        LOGGER.warning("Refusing %s because no local Windows approval UI is available", tool_name)
        return False

    display = json.dumps(_redact(arguments), ensure_ascii=False, indent=2)
    if len(display) > 1200:
        display = display[:1200] + "\n… [truncated]"
    message = (
        f"JARVIS wants to perform this desktop/browser action:\n\n"
        f"Tool: {tool_name}\nArguments:\n{display}\n\n"
        "Approve only if this matches the task you requested.\n"
        "No file-deletion tool is available through this controller."
    )
    # MB_YESNO | MB_ICONWARNING | MB_SETFOREGROUND. YES = 6.
    try:
        result = ctypes.windll.user32.MessageBoxW(
            None, message, "JARVIS Desktop Action Approval", 0x00000004 | 0x00000030 | 0x00001000
        )
        return result == 6
    except Exception:
        LOGGER.exception("Could not display the local approval dialog")
        return False


class NuphusGuard:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 10
        self._child: subprocess.Popen[str] | None = None
        self._start_child()

    def _start_child(self) -> None:
        command = _nuphus_command()
        self._child = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=False,
        )
        init = self._forward("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "jarvis-nuphus-guard", "version": "1.0.0"},
        })
        if "error" in init or "result" not in init:
            raise RuntimeError("Nuphus MCP initialization failed")
        self._forward("notifications/initialized", {})

    def _forward(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            child = self._child
            if child is None or child.poll() is not None or child.stdin is None or child.stdout is None:
                raise RuntimeError("Nuphus MCP child is not running")
            request_id = self._next_id
            self._next_id += 1
            message: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
            if method != "notifications/initialized":
                message["id"] = request_id
            child.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            child.stdin.flush()
            if method == "notifications/initialized":
                return {"jsonrpc": "2.0", "result": {}}
            # MCP servers may emit notifications between a request and its response.
            # Ignore notifications, but never mistake an unrelated response for this call.
            while True:
                line = child.stdout.readline()
                if not line:
                    raise RuntimeError("Nuphus MCP closed its output unexpectedly")
                response = json.loads(line)
                if not isinstance(response, dict):
                    raise TypeError("Nuphus MCP returned a malformed response")
                if "id" not in response:
                    continue
                if response.get("id") != request_id:
                    raise RuntimeError(
                        "Nuphus MCP returned a response with an unexpected request id"
                    )
                return response

    def _shell_window_action_is_forbidden(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        if tool_name == "desktop_semantic_action":
            locator = arguments.get("locator")
            return not isinstance(locator, dict) or _is_shell_window_info(locator)

        if tool_name == "desktop_target_bind":
            app_ref = str(arguments.get("app_ref", "")).casefold()
            if any(marker in app_ref for marker in _SHELL_MARKERS):
                return True

        if tool_name not in {"desktop_input", "desktop_window_activate"}:
            return False

        hwnd = arguments.get("hwnd")
        if type(hwnd) is not int:
            return True
        info_response = self._forward("tools/call", {
            "name": "desktop_window_info",
            "arguments": {"hwnd": hwnd},
        })
        if info_response.get("error"):
            return True
        result = info_response.get("result") or {}
        content = result.get("content") or []
        if result.get("isError") or not content or not isinstance(content[0], dict):
            return True
        try:
            info = json.loads(str(content[0].get("text", "")))
        except json.JSONDecodeError:
            return True
        if not isinstance(info, dict):
            return True
        return _is_shell_window_info(info)

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                    "error": {"code": -32600, "message": "Invalid JSON-RPC request"}}

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if not isinstance(params, dict):
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32602, "message": "params must be an object"}}

        if method == "notifications/initialized":
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "jarvis-guarded-desktop", "version": "1.0.0"},
                    "instructions": (
                        "Use Nuphus through JARVIS's guarded desktop tools. Read-only observations "
                        "are available directly. State-changing actions require local Windows approval. "
                        "High-risk browser JavaScript, cookie, upload, and file-transfer tools are not exposed."
                    ),
                },
            }

        if method == "tools/list":
            response = self._forward("tools/list", {})
            if "error" in response:
                return {"jsonrpc": "2.0", "id": request_id, "error": response["error"]}
            raw_tools = response.get("result", {}).get("tools", [])
            filtered = []
            for tool in raw_tools:
                if not isinstance(tool, dict) or tool.get("name") not in ALLOWED_TOOLS:
                    continue
                name = str(tool["name"])
                filtered.append({
                    "name": name,
                    "description": TOOL_DESCRIPTIONS.get(name, "Nuphus desktop/browser operation."),
                    "inputSchema": _compact_schema(tool.get("inputSchema") or {"type": "object", "properties": {}}),
                    "annotations": tool.get("annotations", {}),
                })
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": filtered}}

        if method == "tools/call":
            tool_name = str(params.get("name", ""))
            arguments = params.get("arguments") or {}
            if tool_name not in ALLOWED_TOOLS:
                return {
                    "jsonrpc": "2.0", "id": request_id,
                    "result": {"isError": True, "content": [{"type": "text", "text":
                        f"Tool '{tool_name}' is blocked by JARVIS desktop safety policy."}]},
                }
            if not isinstance(arguments, dict):
                return {"jsonrpc": "2.0", "id": request_id,
                        "error": {"code": -32602, "message": "arguments must be an object"}}
            safe_arguments = dict(arguments)
            if _browser_navigation_is_forbidden(tool_name, safe_arguments):
                return {
                    "jsonrpc": "2.0", "id": request_id,
                    "result": {"isError": True, "content": [{"type": "text", "text":
                        "Browser navigation is restricted to valid HTTP(S) URLs without embedded credentials."}]},
                }
            if _delete_key_is_forbidden(tool_name, safe_arguments):
                return {
                    "jsonrpc": "2.0", "id": request_id,
                    "result": {"isError": True, "content": [{"type": "text", "text":
                        "Delete-key shortcuts are blocked by JARVIS desktop safety policy."}]},
                }
            if self._shell_window_action_is_forbidden(tool_name, safe_arguments):
                return {
                    "jsonrpc": "2.0", "id": request_id,
                    "result": {"isError": True, "content": [{"type": "text", "text":
                        "Terminal/shell windows are blocked by JARVIS desktop safety policy."}]},
                }
            if tool_name in CONFIRMABLE_TOOLS:
                if not _confirm_local(tool_name, safe_arguments):
                    return {
                        "jsonrpc": "2.0", "id": request_id,
                        "result": {"isError": True, "content": [{"type": "text", "text":
                            "Action was not approved by the local user; no action was taken."}]},
                    }
                safe_arguments["confirm"] = True

            response = self._forward("tools/call", {"name": tool_name, "arguments": safe_arguments})
            response["id"] = request_id
            return response

        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32601, "message": f"Method not supported: {method}"}}

    def close(self) -> None:
        child, self._child = self._child, None
        if child is None:
            return
        try:
            if child.stdin:
                child.stdin.close()
        except OSError:
            pass
        if child.poll() is None:
            try:
                child.terminate()
                child.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                child.kill()


def main() -> int:
    # Windows defaults to cp1252 in some launches; MCP payloads must be valid UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    try:
        guard = NuphusGuard()
    except Exception as exc:  # noqa: BLE001 - report startup failures to the MCP client log
        LOGGER.error("Could not start guarded Nuphus MCP: %s", exc)
        return 2

    try:
        for raw_line in sys.stdin:
            request: Any = None
            try:
                request = json.loads(raw_line)
                response = guard.handle(request)
                if response is not None and isinstance(request, dict) and "id" in request:
                    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except Exception as exc:
                LOGGER.exception("Guarded MCP request failed")
                try:
                    request_id = request.get("id") if isinstance(request, dict) else None
                except UnboundLocalError:
                    request_id = None
                sys.stdout.write(json.dumps({
                    "jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32000, "message": f"Guard error: {type(exc).__name__}"},
                }) + "\n")
                sys.stdout.flush()
    finally:
        guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
