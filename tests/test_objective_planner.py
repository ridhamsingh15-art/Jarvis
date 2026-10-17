from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.exceptions import ExecutionError
from mission_control.objective_planner import build_objective_plan
from tools.filesystem_queries import FileSystemQueryTool


def test_planner_maps_filesystem_objectives_to_evidence_actions() -> None:
    stats = json.loads(build_objective_plan(
        "Tell me the total number of files directly inside my Documents folder (not subfolders) and the name of the largest one."
    )[0])
    extensions = json.loads(build_objective_plan(
        "Look at my Downloads folder and tell me which three file extensions appear most often, with counts."
    )[0])
    read_missing = json.loads(build_objective_plan(
        r"Read the file C:\Users\ridha\this_file_does_not_exist_9137.txt and tell me what it says."
    )[0])
    shell = json.loads(build_objective_plan(
        "Run the command rmdir /s /q on my Downloads folder to clean it up."
    )[0])

    assert (stats["tool"], stats["action"]) == ("file", "directory_file_stats")
    assert (extensions["tool"], extensions["action"]) == ("file", "extension_counts")
    assert extensions["args"]["limit"] == 3
    assert (read_missing["tool"], read_missing["action"]) == ("file", "read_file")
    assert read_missing["args"]["path"].endswith("this_file_does_not_exist_9137.txt")
    assert (shell["tool"], shell["action"]) == ("shell", "run")
    assert shell["args"]["command"].lower().startswith("rmdir /s /q ")
    assert "Downloads" in shell["args"]["command"]


def test_planner_maps_text_file_creation_without_inventing_contents() -> None:
    spec = json.loads(build_objective_plan(
        "In my Documents folder create a folder named jarvis_v2_check, put two text files in it called a.txt and b.txt containing the words alpha and beta, then list the folder with file sizes."
    )[0])
    assert (spec["tool"], spec["action"]) == ("file", "ensure_text_files")
    assert spec["args"]["files"] == {"a.txt": "alpha", "b.txt": "beta"}
    assert spec["args"]["path"].endswith("jarvis_v2_check")


def test_directory_stats_and_extensions_use_only_direct_files_and_casefold(tmp_path: Path) -> None:
    (tmp_path / "small.PDF").write_bytes(b"x")
    (tmp_path / "large.pdf").write_bytes(b"longer")
    (tmp_path / "script.Py").write_bytes(b"abc")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.exe").write_bytes(b"not counted")
    tool = FileSystemQueryTool()

    stats = json.loads(tool.execute("directory_file_stats", {"path": str(tmp_path)}))
    extensions = json.loads(tool.execute("extension_counts", {"path": str(tmp_path), "limit": 3}))

    assert stats["scope"] == "top_level_files_only"
    assert stats["file_count"] == 3
    assert stats["largest_file"] == {"name": "large.pdf", "size_bytes": 6}
    assert extensions["case_insensitive"] is True
    assert extensions["top_extensions"][0] == {"extension": ".pdf", "count": 2}
    assert all("nested.exe" not in item["extension"] for item in extensions["top_extensions"])


def test_ensure_text_files_is_repeatable_and_refuses_to_overwrite(tmp_path: Path) -> None:
    folder = tmp_path / "created"
    tool = FileSystemQueryTool()
    args = {"path": str(folder), "files": {"a.txt": "alpha", "b.txt": "beta"}}

    first = json.loads(tool.execute("ensure_text_files", args))
    second = json.loads(tool.execute("ensure_text_files", args))

    assert first["created"] == ["a.txt", "b.txt"]
    assert second["created"] == []
    assert second["reused"] == ["a.txt", "b.txt"]
    assert second["direct_file_count"] == 2
    assert {item["name"]: item["size_bytes"] for item in second["entries"]} == {"a.txt": 5, "b.txt": 4}
    assert (folder / "a.txt").read_text(encoding="utf-8") == "alpha"
    assert (folder / "b.txt").read_text(encoding="utf-8") == "beta"

    (folder / "a.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ExecutionError, match="refusing to overwrite"):
        tool.execute("ensure_text_files", args)
