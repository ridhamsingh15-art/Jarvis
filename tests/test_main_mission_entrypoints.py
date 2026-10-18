from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from mission_control.crash_store import CrashSafeMissionStore

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _main(db: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "main.py"), "--mission-db", str(db), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
    )


def test_main_cli_lists_shows_and_abandons_crash_safe_needs_review(tmp_path: Path) -> None:
    step = json.dumps({"tool": "shell", "action": "run", "args": {"command": "echo safe"}})
    db = tmp_path / "missions.sqlite3"
    store = CrashSafeMissionStore(db)
    store.create_mission("main-review", "review objective", [step])
    store.begin_step(mission_id="main-review", step_index=0, tool="shell", action="run", args={"command": "echo safe"}, idempotency_key="main-review-key", side_effecting=True, started_at="test-start")
    store.mark_needs_review("main-review", 0, "needs_review: synthetic setup reason for CLI routing test")

    listed = _main(db, "--needs-review")
    assert listed.returncode == 0 and "main-review" in listed.stdout
    shown = _main(db, "--show-needs-review", "main-review")
    assert shown.returncode == 0 and "synthetic setup reason" in shown.stdout
    resolved = _main(db, "--resolve-needs-review", "main-review", "--step", "1", "--resolution", "abandon")
    assert resolved.returncode == 0 and "MISSION_STATE=ABANDONED" in resolved.stdout
    assert CrashSafeMissionStore(db).step("main-review", 0)["status"] == "abandoned"


def test_gui_context_receives_custom_mission_db(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    import core.model_manager as model_manager_module
    import gui
    import main as jarvis_main

    custom_db = str(tmp_path / "custom-missions.sqlite3")
    args = SimpleNamespace(
        needs_review=False, show_needs_review=None, resolve_needs_review=None,
        mission=None, resume=False, models=False, mission_db=custom_db,
        cli=False, autonomy_service=False,
    )
    captured = {}
    monkeypatch.setattr(jarvis_main, "setup_logging", lambda: None)
    monkeypatch.setattr(jarvis_main, "parse_args", lambda: args)
    monkeypatch.setattr(
        jarvis_main, "load_config",
        lambda: SimpleNamespace(provider="gemini", fallback_providers=()),
    )
    monkeypatch.setattr(
        model_manager_module, "ModelManager",
        lambda _config: SimpleNamespace(startup_health_check=lambda: None),
    )
    monkeypatch.setattr(
        jarvis_main, "build_agent",
        lambda: {"agent": object(), "autonomy_service": None},
    )
    monkeypatch.setattr(
        gui, "launch_gui",
        lambda _agent, config_ctx: captured.update(config_ctx=config_ctx),
    )

    jarvis_main.main()

    assert captured["config_ctx"]["mission_db"] == custom_db
