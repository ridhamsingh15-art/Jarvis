from pathlib import Path

import pytest

from tools.shell import ShellTool


def test_relative_cwd_override_resolves_from_workspace_root(tmp_path: Path):
    workspace = tmp_path / "workspace"
    subdirectory = workspace / "subdirectory"
    subdirectory.mkdir(parents=True)
    tool = ShellTool(workspace_root=workspace)

    assert tool._resolve_cwd("subdirectory") == subdirectory.resolve()


def test_relative_cwd_override_cannot_traverse_outside_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    tool = ShellTool(workspace_root=workspace)

    assert tool._resolve_cwd("../outside") is None
    assert tool._resolve_cwd(str(outside)) is None


def test_relative_symlink_cwd_override_cannot_escape_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace / "outside-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Directory symlinks unavailable in this environment: {type(exc).__name__}")

    tool = ShellTool(workspace_root=workspace)
    assert tool._resolve_cwd("outside-link") is None
