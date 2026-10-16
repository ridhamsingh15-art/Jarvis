from pathlib import Path

from tools.shell import ShellTool


def test_shell_blocks_unresolvable_absolute_path_instead_of_skipping_check(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside_path = tmp_path / "outside.txt"
    tool = ShellTool(workspace_root=workspace)
    original_resolve = Path.resolve

    def fail_for_outside_path(path, *args, **kwargs):
        if str(path).casefold() == str(outside_path).casefold():
            raise RuntimeError("simulated symlink loop")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_for_outside_path)
    result = tool.run(f"type {outside_path}")

    assert result.blocked is True
    assert "could not safely resolve" in result.blocked_reason.casefold()
    assert "simulated symlink loop" not in result.blocked_reason
