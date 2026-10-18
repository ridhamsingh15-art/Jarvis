from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from core.exceptions import ExecutionError, ValidationError
from core.registry import Registry
from core.task import Task
from core.validator import Validator
from mission_control.crash_safe import _verify_action_outcome, _verify_browser_dispatch
from tools.browser import BrowserTool, build_browser_target, normalize_http_url
from tools.file import FileTool
from tools.shell import ShellResult, ShellTool
from tools.windows import WindowsTool


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("example.com/path", "https://example.com/path"),
        ("HTTPS://Example.com/docs?q=ok", "https://Example.com/docs?q=ok"),
        ("http://localhost:8080/health", "http://localhost:8080/health"),
    ],
)
def test_browser_url_normalization_accepts_http_destinations(source: str, expected: str) -> None:
    assert normalize_http_url(source) == expected


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,hello",
        "ftp://example.com/download",
        "https://user:password@example.com/",
        "https://example.com:99999/",
        "https://bad_host.example/",
        "https://example.com/\r\nSet-Cookie: x",
        "https://example.com\\@attacker.test/",
        "https://",
        "https://256.256.256.256/",
    ],
)
def test_browser_url_normalization_rejects_unsafe_or_malformed_destinations(url: str) -> None:
    with pytest.raises(ExecutionError):
        normalize_http_url(url)


def test_browser_direct_call_rejects_bad_envelopes_and_unknown_arguments() -> None:
    browser = BrowserTool()
    with pytest.raises(ExecutionError, match="JSON object"):
        browser.execute("open_url", "https://example.com")
    with pytest.raises(ExecutionError, match="Unknown argument"):
        browser.execute("open_url", {"url": "https://example.com", "shell": "whoami"})

    with patch("webbrowser.open") as open_browser, pytest.raises(ExecutionError, match="Only HTTP and HTTPS"):
        browser.execute("open_url", {"url": "javascript:alert(1)"})
    open_browser.assert_not_called()


def test_browser_result_does_not_claim_page_load_or_content_was_verified() -> None:
    with patch("webbrowser.open", return_value=True) as open_browser:
        result = BrowserTool().execute("open_url", {"url": "example.com/docs"})
    open_browser.assert_called_once_with("https://example.com/docs")
    assert "request accepted" in result
    assert "not verified" in result.casefold()


def test_browser_target_builder_is_the_same_validation_boundary_used_by_verifier() -> None:
    assert build_browser_target("open_site", {"site": "github"}) == "https://github.com"
    with patch("mission_control.crash_safe._wait_for_process_images") as process_check:
        result = _verify_browser_dispatch("open_url", {"url": "ftp://example.com"})
    assert result["status"] == "failed"
    process_check.assert_not_called()


def test_file_tool_rejects_invalid_envelopes_without_touching_files(tmp_path) -> None:
    tool = FileTool()
    target = tmp_path / "must_not_exist.txt"

    with pytest.raises(ExecutionError, match="JSON object"):
        tool.execute("write_file", None)
    with pytest.raises(ExecutionError, match="Unknown argument"):
        tool.execute("write_file", {"path": str(target), "content": "x", "unexpected": True})
    with pytest.raises(ExecutionError, match="string"):
        tool.execute("read_file", {"path": 42})

    assert not target.exists()


def test_file_read_is_bounded_and_crash_safe_verifier_checks_the_bounded_output(tmp_path) -> None:
    from tools.file import _MAX_READ_CHARS, _READ_TRUNCATION_MARKER

    target = tmp_path / "large.txt"
    target.write_text("A" * (_MAX_READ_CHARS + 9000), encoding="utf-8")

    output = FileTool().execute("read_file", {"path": str(target)})
    assert output.startswith("A" * 100)
    assert output.endswith(_READ_TRUNCATION_MARKER)
    assert len(output) == _MAX_READ_CHARS + len(_READ_TRUNCATION_MARKER)

    verification = _verify_action_outcome(
        "file", "read_file", {"path": str(target)}, output
    )
    assert verification["status"] == "verified"
    assert "bounded_content_matches_disk" in verification["checks"]


def test_directory_listing_is_bounded_and_explicitly_marks_truncation(tmp_path) -> None:
    for index in range(225):
        (tmp_path / f"entry-{index:03}.txt").touch()

    output = FileTool().execute("list_directory", {"path": str(tmp_path)})
    assert "[JARVIS: listing truncated after 200 entries" in output
    assert output.count("\n      ") <= 200


def test_file_patch_rejects_non_string_match_or_replacement_before_mutation(tmp_path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("original text", encoding="utf-8")

    with pytest.raises(ExecutionError, match="Replacement target text"):
        FileTool().execute("patch_file", {"path": str(target), "old_text": 12, "new_text": "changed"})
    with pytest.raises(ExecutionError, match="Replacement text"):
        FileTool().execute("patch_file", {"path": str(target), "old_text": "original", "new_text": 123})

    assert target.read_text(encoding="utf-8") == "original text"


def test_shell_direct_call_requires_a_registered_action_and_command(tmp_path) -> None:
    tool = ShellTool(workspace_root=tmp_path)
    with pytest.raises(ExecutionError, match="Unknown argument"):
        tool.execute("run", {"command": "echo safe", "unexpected": "value"})
    with pytest.raises(ExecutionError, match="command"):
        tool.execute("run", {})
    with pytest.raises(ExecutionError, match="Action name"):
        tool.execute([], {})


def test_shell_direct_call_uses_validated_action_arguments_without_running_a_process(tmp_path) -> None:
    tool = ShellTool(workspace_root=tmp_path)
    fake_result = ShellResult(
        command="echo safe", return_code=0, stdout="safe", stderr="",
        timed_out=False, blocked=False,
    )
    tool.run = Mock(return_value=fake_result)

    output = tool.execute("run", {"command": "echo safe"})
    assert "safe" in output
    tool.run.assert_called_once_with("echo safe", cwd_override=None, timeout=None)


def test_windows_tool_accepts_only_allowlisted_string_app_names() -> None:
    windows = WindowsTool()
    with patch("tools.windows.subprocess.Popen") as popen:
        with pytest.raises(ExecutionError, match="Unknown argument"):
            windows.execute("open_app", {"app": "notepad", "command": "calc"})
        with pytest.raises(ExecutionError, match="string"):
            windows.execute("open_app", {"app": 7})
        with pytest.raises(ExecutionError, match="Unknown application"):
            windows.execute("open_app", {"app": "notepad; calc"})

    popen.assert_not_called()


def test_windows_launch_uses_fixed_mapping_and_does_not_claim_readiness() -> None:
    with patch("tools.windows.subprocess.Popen") as popen:
        result = WindowsTool().execute("open_app", {"app": "notepad"})
    popen.assert_called_once_with(["notepad"], shell=False)
    assert "request accepted" in result
    assert "not verified" in result.casefold()


def test_registry_validator_and_tool_schemas_agree_for_builtin_computer_tools(tmp_path) -> None:
    registry = Registry()
    for tool in (
        FileTool(workspace_root=tmp_path),
        ShellTool(workspace_root=tmp_path),
        BrowserTool(),
        WindowsTool(),
    ):
        registry.register(tool)

    validator = Validator(registry)
    valid = Task(tool="browser", action="open_url", args={"url": "https://example.com"})
    assert validator.validate(valid) is valid

    invalid = Task(
        tool="browser",
        action="open_url",
        args={"url": "https://example.com", "unexpected": "value"},
    )
    with pytest.raises(ValidationError, match="Unknown argument"):
        validator.validate(invalid)
