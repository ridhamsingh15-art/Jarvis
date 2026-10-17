from __future__ import annotations

import os
import re
from pathlib import Path

from core.agent import Agent
from mission_control.crash_store import CrashSafeMissionStore


def test_supported_gui_mission_objective_uses_crash_safe_runner(tmp_path: Path, monkeypatch) -> None:
    temp_root = Path(os.environ["TEMP"]).resolve()
    assert tmp_path.resolve().is_relative_to(temp_root), "GUI mission test must stay under TEMP"
    data_dir = tmp_path / "sample-folder"
    data_dir.mkdir()
    (data_dir / "real.txt").write_text("GUI_CRASH_SAFE_MARKER", encoding="utf-8")
    db = tmp_path / "gui-missions.sqlite3"
    monkeypatch.setenv("JARVIS_MISSION_DB", str(db))
    agent = object.__new__(Agent)

    tasks = agent._handle_mission(
        f"List the 10 largest files in {data_dir} and summarize them", context_str="",
    )
    assert len(tasks) == 1 and tasks[0].tool == "system" and tasks[0].action == "respond"
    message = tasks[0].args["message"]
    match = re.search(r"Mission (gui-[0-9a-f]+): COMPLETED", message)
    assert match, message
    mission = CrashSafeMissionStore(db).mission(match.group(1))
    steps = CrashSafeMissionStore(db).steps(match.group(1))
    assert mission and mission["state"] == "COMPLETED"
    assert [step["action"] for step in steps] == ["list_largest_files", "summarize_files"]
    assert all(step["status"] == "completed" for step in steps)
    assert "GUI_CRASH_SAFE_MARKER" in message
