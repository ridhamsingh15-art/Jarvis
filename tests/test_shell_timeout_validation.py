from unittest.mock import patch

import pytest

from tools.shell import ShellTool


@pytest.mark.parametrize(
    "timeout",
    [0, -1, float("nan"), float("inf"), float("-inf"), True, False, "invalid", None],
)
def test_constructor_rejects_invalid_default_timeouts(tmp_path, timeout):
    with pytest.raises(ValueError, match="timeout_seconds must be a finite positive number"):
        ShellTool(workspace_root=tmp_path, timeout_seconds=timeout)


@pytest.mark.parametrize("max_output_bytes", [0, -1, True, False, 1.5, None, "1024"])
def test_constructor_rejects_invalid_output_caps(tmp_path, max_output_bytes):
    with pytest.raises(ValueError, match="max_output_bytes must be a positive integer"):
        ShellTool(workspace_root=tmp_path, max_output_bytes=max_output_bytes)


@pytest.mark.parametrize(
    "timeout",
    [0, -1, float("nan"), float("inf"), float("-inf"), True, False, "invalid", object()],
)
def test_invalid_runtime_timeout_blocks_before_subprocess(tmp_path, timeout):
    tool = ShellTool(workspace_root=tmp_path)
    with patch("tools.shell.subprocess.run") as run:
        result = tool.run("echo should_not_run", timeout=timeout)

    assert result.blocked is True
    assert "finite positive number" in result.blocked_reason
    run.assert_not_called()


def test_numeric_string_timeout_is_normalized_for_json_callers(tmp_path):
    tool = ShellTool(workspace_root=tmp_path)
    with patch("tools.shell._WindowsKillOnCloseJob") as job_type, patch("tools.shell.subprocess.Popen") as popen:
        process = popen.return_value
        process._handle = 123
        process.returncode = 0
        process.communicate.return_value = ("ok", "")
        process.poll.return_value = 0
        result = tool.run("echo safe", timeout="1.5")

    assert result.success is True
    assert process.communicate.call_args.kwargs["timeout"] == 1.5
    job_type.return_value.assign.assert_called_once_with(process)


@pytest.mark.parametrize("command", [None, 0, [], "", "   "])
def test_invalid_command_values_are_blocked_before_subprocess(tmp_path, command):
    tool = ShellTool(workspace_root=tmp_path)
    with patch("tools.shell.subprocess.run") as run:
        result = tool.run(command)

    assert result.blocked is True
    assert "non-empty string" in result.blocked_reason
    run.assert_not_called()
