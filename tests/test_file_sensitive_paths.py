from pathlib import Path

import pytest

from core.exceptions import ExecutionError
from tools.file import FileTool, _is_sensitive_read_path, _validate_path


@pytest.mark.parametrize(
    "relative_path",
    [
        ".ENV",
        ".env.production",
        ".env-local",
        "config/PRIVATE.PEM",
        "keys/server.P12",
        ".ssh/id_ed25519",
        ".aws/credentials",
        ".azure/profile.json",
        ".config/gcloud/application_default_credentials.json",
        "AppData/Roaming/Microsoft/Credentials/token.bin",
        "workspace/.git-credentials",
        "config/.npmrc",
    ],
)
def test_sensitive_read_paths_are_blocked_case_insensitively(tmp_path: Path, relative_path: str):
    assert _is_sensitive_read_path((tmp_path / relative_path).resolve()) is True


def test_ordinary_files_are_not_mistaken_for_credentials(tmp_path: Path):
    assert _is_sensitive_read_path((tmp_path / "README.md").resolve()) is False
    assert _is_sensitive_read_path((tmp_path / "config" / "settings.json").resolve()) is False
    assert _is_sensitive_read_path((tmp_path / "src" / "keyboard.py").resolve()) is False


def test_read_open_and_directory_listing_reject_sensitive_paths(tmp_path: Path):
    secret = tmp_path / ".env.production"
    secret.write_text("TOKEN=must-not-be-read\n", encoding="utf-8")
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "id_ed25519").write_text("PRIVATE KEY", encoding="utf-8")
    tool = FileTool()

    for action, args in (
        ("read_file", {"path": str(secret)}),
        ("open_file", {"path": str(secret)}),
        ("list_directory", {"path": str(ssh_dir)}),
        ("read_file", {"path": str(ssh_dir / "id_ed25519")}),
    ):
        with pytest.raises(ExecutionError, match="protected directory"):
            tool.execute(action, args)


def test_sensitive_files_cannot_be_renamed_copied_or_moved_to_bypass_read_guards(tmp_path: Path):
    secret = tmp_path / ".env"
    secret.write_text("API_TOKEN=must-not-leak\n", encoding="utf-8")
    destination = tmp_path / "renamed.txt"
    copied = tmp_path / "copied.txt"
    moved = tmp_path / "moved.txt"
    tool = FileTool()

    for action, args in (
        ("rename", {"path": str(secret), "new_name": destination.name}),
        ("copy", {"path": str(secret), "dest": str(copied)}),
        ("move", {"path": str(secret), "dest": str(moved)}),
    ):
        with pytest.raises(ExecutionError, match="protected directory"):
            tool.execute(action, args)

    assert secret.read_text(encoding="utf-8") == "API_TOKEN=must-not-leak\n"
    assert not destination.exists()
    assert not copied.exists()
    assert not moved.exists()


def test_workspace_scoped_file_tool_blocks_writes_outside_root(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    tool = FileTool(workspace_root=workspace)

    with pytest.raises(ExecutionError, match="outside workspace"):
        tool.execute("write_file", {"path": str(outside), "content": "must not write"})
    with pytest.raises(ExecutionError, match="outside workspace"):
        tool.execute("copy", {"path": "inside.txt", "dest": str(outside)})
    assert not outside.exists()

def test_workspace_scoped_file_tool_resolves_relative_writes_inside_root(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = FileTool(workspace_root=workspace)
    tool.execute("write_file", {"path": "inside.txt", "content": "allowed"})
    assert (workspace / "inside.txt").read_text(encoding="utf-8") == "allowed"

def test_project_test_sources_are_protected_from_mutation():
    project_root = Path(__file__).resolve().parents[1]
    protected_test = project_root / "tests" / "test_execution_policy.py"
    assert protected_test.is_file()
    tool = FileTool()
    with pytest.raises(ExecutionError, match="protected directory"):
        tool.execute("delete", {"path": str(protected_test)})
    assert protected_test.is_file()
    with pytest.raises(ExecutionError, match="protected directory"):
        _validate_path(project_root / "jarvis_session_test.txt")


def test_workspace_scoped_move_cannot_move_protected_project_source(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    protected = project_root / "tests" / "test_execution_policy.py"
    destination = project_root / ".jarvis_test_workspace" / "audit-move-regression.py"
    assert protected.is_file()
    moved = []

    def record_move(source, dest):
        moved.append((source, dest))
        return str(dest)

    # Never perform the move in this regression test; only observe whether validation
    # incorrectly allows the protected source to reach shutil.move().
    monkeypatch.setattr("tools.file.shutil.move", record_move)
    tool = FileTool(workspace_root=project_root)

    with pytest.raises(ExecutionError, match="protected directory"):
        tool.execute("move", {"path": str(protected), "dest": str(destination)})

    assert moved == []
    assert protected.is_file()
    assert not destination.exists()
