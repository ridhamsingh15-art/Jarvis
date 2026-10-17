from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_control.objective_planner import build_objective_plan
from tools.filesystem_queries import FileSystemQueryTool
from tools.known_folders import known_folder_path


@pytest.mark.parametrize("name", ["documents", "desktop", "downloads"])
def test_known_folder_override_uses_redirected_temporary_directory(monkeypatch, tmp_path: Path, name: str) -> None:
    temp_root = Path(__import__("os").environ["TEMP"]).resolve()
    assert tmp_path.resolve().is_relative_to(temp_root), "known-folder test must stay under TEMP"
    redirected = tmp_path / "OneDriveRedirect" / name
    redirected.mkdir(parents=True)
    (redirected / "sample.txt").write_text("redirected content", encoding="utf-8")
    monkeypatch.setenv(f"JARVIS_KNOWN_FOLDER_{name.upper()}", str(redirected))

    assert known_folder_path(name) == redirected.resolve()
    if name in {"documents", "desktop"}:
        objective = f"How many files are in my {name.title()} and what is the largest file?"
        step = json.loads(build_objective_plan(objective)[0])
        assert Path(step["args"]["path"]) == redirected.resolve()
        result = json.loads(FileSystemQueryTool().execute(step["action"], step["args"]))
        assert result["directory"] == str(redirected.resolve())
        assert result["file_count"] == 1
        assert result["largest_file"] == {"name": "sample.txt", "size_bytes": len("redirected content")}
    else:
        step = json.loads(build_objective_plan("Show the top 3 most common file extensions in Downloads")[0])
        assert Path(step["args"]["path"]) == redirected.resolve()
        result = json.loads(FileSystemQueryTool().execute(step["action"], step["args"]))
        assert result["directory"] == str(redirected.resolve())
        assert result["top_extensions"] == [{"extension": ".txt", "count": 1}]
