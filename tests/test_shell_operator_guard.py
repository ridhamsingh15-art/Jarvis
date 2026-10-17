import os
from unittest.mock import patch

import pytest

from tools.shell import ShellTool, _check_shell_syntax


@pytest.mark.parametrize(
    "command",
    [
        "echo safe & echo injected",
        "echo safe && python -c \"print('injected')\"",
        "git status | more",
        "echo safe > output.txt",
        "type < input.txt",
        "echo safe; echo injected",
        "echo `whoami`",
        "echo $(whoami)",
        "python -c \"print($(whoami))\"",
        "powershell -Command \"Write-Output unsafe\"",
        "cmd.exe /c echo unsafe",
        "echo unterminated \"quote",
        "echo first\necho second",
    ],
)
def test_shell_command_chaining_and_nested_interpreters_are_rejected(command: str):
    assert _check_shell_syntax(command), command


def test_safe_commands_and_quoted_arguments_remain_supported():
    assert _check_shell_syntax("echo hello") == ""
    assert _check_shell_syntax("pytest -q tests") == ""
    assert _check_shell_syntax('python -c "print(\'a; b & c > d\')"') == ""
    assert _check_shell_syntax('python -c "import os; print(os.environ.get(\'TOKEN\', \'NOT_FOUND\'))"') == ""


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe variable expansion is Windows-specific")
@pytest.mark.parametrize("command", ["echo %PATH%", 'python -c "print(\"%USERPROFILE%\")"', "echo !TOKEN!"])
def test_windows_environment_expansion_is_rejected(command: str):
    assert "variable expansion" in _check_shell_syntax(command)


def test_shell_never_starts_a_chained_command(tmp_path):
    tool = ShellTool(workspace_root=tmp_path)
    with patch("tools.shell.subprocess.run") as run:
        result = tool.run("echo safe & echo must_not_execute")

    assert result.blocked is True
    assert "separators" in result.blocked_reason
    run.assert_not_called()


def test_nested_interpreter_is_blocked_before_subprocess_start(tmp_path):
    tool = ShellTool(workspace_root=tmp_path)
    with patch("tools.shell.subprocess.run") as run:
        result = tool.run('powershell -Command "Remove-Item important.txt"')

    assert result.blocked is True
    assert "nested command interpreters" in result.blocked_reason
    run.assert_not_called()
