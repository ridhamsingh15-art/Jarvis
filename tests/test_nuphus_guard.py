import io
import threading
from types import SimpleNamespace

import pytest

import core.mcp.nuphus_guard as guard_module
from core.mcp.nuphus_guard import (
    ALLOWED_TOOLS,
    READ_ONLY_TOOLS,
    NuphusGuard,
)


def _guard_without_child():
    guard = object.__new__(NuphusGuard)
    guard._lock = None
    guard._next_id = 10
    guard._child = None
    return guard


def test_dangerous_browser_tools_are_not_exposed():
    assert "browser_evaluate" not in ALLOWED_TOOLS
    assert "browser_exec" not in ALLOWED_TOOLS
    assert "browser_cookies_get" not in ALLOWED_TOOLS
    assert "browser_cookies_set" not in ALLOWED_TOOLS
    assert "browser_upload" not in ALLOWED_TOOLS
    assert "browser_drag_files" not in ALLOWED_TOOLS


def test_desktop_observation_tools_are_read_only():
    assert "desktop_screen_size" in READ_ONLY_TOOLS
    assert "desktop_windows_list" in READ_ONLY_TOOLS
    assert "desktop_semantic_observe" in READ_ONLY_TOOLS


def test_write_tools_require_local_confirmation(monkeypatch):
    guard = _guard_without_child()
    monkeypatch.setattr(guard_module, "_confirm_local", lambda name, args: False)

    def inspect_only(method, params):
        if params.get("name") == "desktop_window_info":
            return {"result": {"content": [{"text": '{"title":"Notepad","process_name":"notepad.exe","class_name":"Notepad"}'}]}}
        raise AssertionError("write must not be forwarded")

    monkeypatch.setattr(guard, "_forward", inspect_only)
    result = guard.handle({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "desktop_input", "arguments": {"mode": "type", "hwnd": 5, "text": "hello"}},
    })
    assert result["result"]["isError"] is True
    assert "not approved" in result["result"]["content"][0]["text"]


def test_approved_write_is_forwarded_with_strict_confirm(monkeypatch):
    guard = _guard_without_child()
    observed = {}

    def approve(name, args):
        observed["approval"] = (name, args)
        return True

    def forward(method, params):
        observed["forward"] = (method, params)
        return {"jsonrpc": "2.0", "id": 10, "result": {"content": [{"type": "text", "text": "ok"}]}}

    monkeypatch.setattr(guard_module, "_confirm_local", approve)
    monkeypatch.setattr(guard, "_forward", forward)
    result = guard.handle({
        "jsonrpc": "2.0",
        "id": 19,
        "method": "tools/call",
        "params": {"name": "browser_navigate", "arguments": {"url": "https://example.com"}},
    })
    assert observed["approval"][0] == "browser_navigate"
    assert observed["forward"][0] == "tools/call"
    assert observed["forward"][1]["arguments"]["confirm"] is True
    assert result["id"] == 19
    assert result["result"]["content"][0]["text"] == "ok"


def test_blocked_tool_fails_closed_without_forwarding(monkeypatch):
    guard = _guard_without_child()
    monkeypatch.setattr(guard, "_forward", lambda *args: (_ for _ in ()).throw(AssertionError("must not forward")))
    result = guard.handle({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "browser_evaluate", "arguments": {"script": "alert(1)"}},
    })
    assert result["result"]["isError"] is True
    assert "blocked" in result["result"]["content"][0]["text"]


def test_tool_discovery_returns_only_allowlisted_tools(monkeypatch):
    guard = _guard_without_child()
    monkeypatch.setattr(guard, "_forward", lambda *args: {
        "jsonrpc": "2.0",
        "id": 10,
        "result": {"tools": [
            {"name": "desktop_screen_size"},
            {"name": "browser_evaluate"},
            {"name": "desktop_input"},
        ]},
    })
    result = guard.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
    names = {x["name"] for x in result["result"]["tools"]}
    assert names == {"desktop_screen_size", "desktop_input"}


def test_delete_key_shortcuts_are_blocked_without_prompt_or_forward(monkeypatch):
    guard = _guard_without_child()
    monkeypatch.setattr(
        guard_module, "_confirm_local",
        lambda *args: (_ for _ in ()).throw(AssertionError("must not ask approval")),
    )
    monkeypatch.setattr(guard, "_forward", lambda *args: (_ for _ in ()).throw(AssertionError("must not forward")))
    result = guard.handle({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "desktop_input",
            "arguments": {"mode": "hotkey", "hwnd": 5, "keys": ["Shift", "Delete"]},
        },
    })
    assert result["result"]["isError"] is True
    assert "Delete-key shortcuts are blocked" in result["result"]["content"][0]["text"]


def test_shell_windows_are_blocked_even_if_approved(monkeypatch):
    guard = _guard_without_child()
    monkeypatch.setattr(
        guard_module, "_confirm_local",
        lambda *args: (_ for _ in ()).throw(AssertionError("shell action must not prompt")),
    )

    def shell_info(method, params):
        assert params["name"] == "desktop_window_info"
        return {"result": {"content": [{"text":
            '{"title":"Administrator: cmd.exe","process_name":"powershell.exe","class_name":"ConsoleWindowClass"}'
        }]}}

    monkeypatch.setattr(guard, "_forward", shell_info)
    result = guard.handle({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {"name": "desktop_input", "arguments": {"mode": "type", "hwnd": 123, "text": "del important.txt"}},
    })
    assert result["result"]["isError"] is True
    assert "Terminal/shell windows are blocked" in result["result"]["content"][0]["text"]


def test_drag_and_semantic_execute_tools_are_not_exposed():
    assert "desktop_mouse_drag" not in ALLOWED_TOOLS
    assert "desktop_semantic_execute" not in ALLOWED_TOOLS


def test_forward_rejects_unexpected_response_id():
    guard = _guard_without_child()
    guard._lock = threading.Lock()
    guard._child = SimpleNamespace(
        poll=lambda: None,
        stdin=io.StringIO(),
        stdout=io.StringIO('{"jsonrpc":"2.0","id":999,"result":{}}'),
    )

    with pytest.raises(RuntimeError, match="unexpected request id"):
        guard._forward("tools/list", {})


def test_forward_ignores_notifications_until_matching_response():
    guard = _guard_without_child()
    guard._lock = threading.Lock()
    guard._child = SimpleNamespace(
        poll=lambda: None,
        stdin=io.StringIO(),
        stdout=io.StringIO(
            '{"jsonrpc":"2.0","method":"notifications/progress","params":{"progress":1}}\n'
            '{"jsonrpc":"2.0","id":10,"result":{"tools":[]}}'
        ),
    )

    response = guard._forward("tools/list", {})

    assert response["id"] == 10
    assert response["result"] == {"tools": []}


@pytest.mark.parametrize("url", [
    "file:///tmp/test",
    "https://example.com:bad/",
    "https://account@example.com/",
])
def test_browser_navigation_rejects_unsafe_url_without_forwarding(url, monkeypatch):
    guard = _guard_without_child()
    monkeypatch.setattr(
        guard_module, "_confirm_local",
        lambda *args: (_ for _ in ()).throw(AssertionError("invalid URL must not prompt")),
    )
    monkeypatch.setattr(
        guard, "_forward",
        lambda *args: (_ for _ in ()).throw(AssertionError("invalid URL must not be forwarded")),
    )

    result = guard.handle({
        "jsonrpc": "2.0",
        "id": 22,
        "method": "tools/call",
        "params": {"name": "browser_navigate", "arguments": {"url": url}},
    })

    assert result["result"]["isError"] is True
    assert "valid HTTP(S) URLs" in result["result"]["content"][0]["text"]
