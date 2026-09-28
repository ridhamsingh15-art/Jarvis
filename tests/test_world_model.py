"""
Tests for the World Model subsystem.

Covers:
  - WorkspaceRegistry: register, duplicate check, remove, find_by_path
  - GitMonitor: detects Jarvis repo (the actual workspace)
  - ProcessMonitor: runs without error (psutil optional)
  - WorldSnapshot: assembles a valid WorldState
  - WorldState.format_for_prompt: contains useful info
  - WorldManager: end-to-end snapshot + context injection
  - Executive Brain integration: world state injected as system note
"""
import os
import pytest
from unittest.mock import MagicMock, patch

from core.world.manager import WorldManager
from core.world.workspace import WorkspaceRegistry
from core.world.git_monitor import GitMonitor
from core.world.process_monitor import ProcessMonitor
from core.world.window_monitor import WindowMonitor
from core.world.observers import WorldObservers
from core.world.snapshot import WorldSnapshot
from core.world.models import (
    ActiveMissionRef,
    GitStatus,
    GitRepoStatus,
    ProcessInfo,
    ProcessStatus,
    RegisteredWorkspace,
    WindowInfo,
    WindowFocusState,
    WorldState,
)
from core.world.exceptions import (
    WorkspaceAlreadyRegisteredError,
    WorkspaceNotFoundError,
)
from core.world.browser_monitor import BrowserMonitor
from core.cognition.context import ShortTermContext

# Path to the actual Jarvis workspace (always exists in this test env)
JARVIS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# WorkspaceRegistry
# ---------------------------------------------------------------------------

class TestWorkspaceRegistry:
    def test_register_valid_path(self):
        registry = WorkspaceRegistry()
        ws = registry.register(JARVIS_ROOT, "Jarvis")
        assert ws.path == JARVIS_ROOT
        assert ws.name == "Jarvis"
        assert ws.id.startswith("ws_")

    def test_register_detects_language(self):
        registry = WorkspaceRegistry()
        ws = registry.register(JARVIS_ROOT, "Jarvis")
        # Jarvis is a Python project
        assert ws.language == "Python"

    def test_register_duplicate_raises(self):
        registry = WorkspaceRegistry()
        registry.register(JARVIS_ROOT, "First")
        with pytest.raises(WorkspaceAlreadyRegisteredError):
            registry.register(JARVIS_ROOT, "Second")

    def test_register_nonexistent_path_raises(self):
        registry = WorkspaceRegistry()
        with pytest.raises(WorkspaceNotFoundError):
            registry.register("/does/not/exist")

    def test_remove(self):
        registry = WorkspaceRegistry()
        ws = registry.register(JARVIS_ROOT, "Jarvis")
        registry.remove(ws.id)
        assert registry.get(ws.id) is None

    def test_remove_unknown_raises(self):
        registry = WorkspaceRegistry()
        with pytest.raises(WorkspaceNotFoundError):
            registry.remove("ws_nonexistent")

    def test_find_by_path_exact(self):
        registry = WorkspaceRegistry()
        ws = registry.register(JARVIS_ROOT, "Jarvis")
        found = registry.find_by_path(JARVIS_ROOT)
        assert found is not None
        assert found.id == ws.id

    def test_find_by_path_subpath(self):
        registry = WorkspaceRegistry()
        ws = registry.register(JARVIS_ROOT, "Jarvis")
        subpath = os.path.join(JARVIS_ROOT, "core")
        found = registry.find_by_path(subpath)
        assert found is not None

    def test_list(self):
        registry = WorkspaceRegistry()
        registry.register(JARVIS_ROOT, "Jarvis")
        assert len(registry.list()) == 1


# ---------------------------------------------------------------------------
# GitMonitor
# ---------------------------------------------------------------------------

class TestGitMonitor:
    def test_detects_jarvis_repo(self):
        monitor = GitMonitor()
        ws = RegisteredWorkspace(
            id="ws_test",
            path=JARVIS_ROOT,
            name="Jarvis",
        )
        status = monitor.observe(ws)
        # Jarvis is a git repo
        assert status is not None
        assert status.current_branch != ""
        assert status.repo_path != ""

    def test_non_repo_returns_none(self):
        """Test that a path outside any git repo returns None.
        Uses os.path.splitdrive root (e.g., C:\\) which is never a git repo."""
        import sys
        # Use the drive root (e.g., C:\) — never a git repo
        drive = os.path.splitdrive(JARVIS_ROOT)[0] + os.sep
        monitor = GitMonitor()
        ws = RegisteredWorkspace(id="ws_drive", path=drive, name="drive_root")
        result = monitor.observe(ws)
        assert result is None

    def test_observe_all_returns_list(self):
        monitor = GitMonitor()
        ws = RegisteredWorkspace(id="ws_test", path=JARVIS_ROOT, name="Jarvis")
        results = monitor.observe_all([ws])
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# ProcessMonitor
# ---------------------------------------------------------------------------

class TestProcessMonitor:
    def test_observe_does_not_raise(self):
        monitor = ProcessMonitor()
        result = monitor.observe()
        assert isinstance(result, list)  # May be empty if psutil not installed

    def test_returns_process_info_objects(self):
        monitor = ProcessMonitor()
        result = monitor.observe()
        for item in result:
            assert isinstance(item, ProcessInfo)
            assert item.pid > 0


# ---------------------------------------------------------------------------
# WorldState.format_for_prompt
# ---------------------------------------------------------------------------

class TestWorldStateFormat:
    def test_empty_state_has_header(self):
        state = WorldState(captured_at="2026-01-01T00:00:00Z")
        prompt = state.format_for_prompt()
        assert "## Current World State" in prompt

    def test_active_workspace_in_prompt(self):
        ws = RegisteredWorkspace(id="ws_1", path="/projects/jarvis", name="Jarvis", language="Python")
        state = WorldState(
            captured_at="2026-01-01T00:00:00Z",
            active_workspace=ws,
        )
        prompt = state.format_for_prompt()
        assert "Jarvis" in prompt
        assert "Python" in prompt

    def test_git_status_in_prompt(self):
        git = GitStatus(
            workspace_id="ws_1",
            repo_path="/projects/jarvis",
            current_branch="main",
            is_dirty=True,
            status=GitRepoStatus.DIRTY,
            modified_files=["core/world/manager.py"],
        )
        state = WorldState(captured_at="", git_statuses=[git])
        prompt = state.format_for_prompt()
        assert "main" in prompt
        assert "dirty" in prompt

    def test_active_mission_in_prompt(self):
        mission = ActiveMissionRef(mission_id="m1", title="Ramayana Ep1", progress=45.0)
        state = WorldState(captured_at="", active_missions=[mission])
        prompt = state.format_for_prompt()
        assert "Ramayana Ep1" in prompt
        assert "45%" in prompt


# ---------------------------------------------------------------------------
# WorldSnapshot
# ---------------------------------------------------------------------------

class TestWorldSnapshot:
    def _make_snapshot_engine(self):
        registry = WorkspaceRegistry()
        registry.register(JARVIS_ROOT, "Jarvis")

        observers = WorldObservers(
            git_monitor=GitMonitor(),
            process_monitor=ProcessMonitor(),
            window_monitor=WindowMonitor(),
        )
        return WorldSnapshot(registry, observers)

    def test_capture_returns_world_state(self):
        engine = self._make_snapshot_engine()
        state = engine.capture()
        assert isinstance(state, WorldState)
        assert len(state.registered_workspaces) == 1
        assert state.captured_at != ""

    def test_capture_includes_git_for_jarvis(self):
        engine = self._make_snapshot_engine()
        state = engine.capture()
        # Jarvis is a git repo — git statuses should be populated
        assert len(state.git_statuses) > 0
        assert state.git_statuses[0].current_branch != ""


# ---------------------------------------------------------------------------
# WorldManager
# ---------------------------------------------------------------------------

class TestWorldManager:
    def test_create_default(self):
        manager = WorldManager.create_default()
        assert manager is not None

    def test_register_and_snapshot(self):
        manager = WorldManager.create_default()
        manager.register_workspace(JARVIS_ROOT, "Jarvis")
        state = manager.snapshot()
        assert isinstance(state, WorldState)
        assert len(state.registered_workspaces) == 1

    def test_snapshot_for_prompt_is_string(self):
        manager = WorldManager.create_default()
        manager.register_workspace(JARVIS_ROOT, "Jarvis")
        prompt = manager.snapshot_for_prompt()
        assert isinstance(prompt, str)
        assert "World State" in prompt

    def test_remove_workspace(self):
        manager = WorldManager.create_default()
        ws = manager.register_workspace(JARVIS_ROOT, "Jarvis")
        manager.remove_workspace(ws.id)
        assert manager.list_workspaces() == []

    def test_push_browser_tabs(self):
        manager = WorldManager.create_default()
        manager.push_browser_tabs([
            {"url": "https://github.com", "title": "GitHub", "is_active": True, "domain": "github.com"}
        ])
        tab = manager._browser_monitor.get_active_tab()
        assert tab is not None
        assert tab.domain == "github.com"


# ---------------------------------------------------------------------------
# Context injection integration
# ---------------------------------------------------------------------------

class TestWorldContextIntegration:
    def test_world_state_injected_into_context(self):
        manager = WorldManager.create_default()
        manager.register_workspace(JARVIS_ROOT, "Jarvis")

        ctx = ShortTermContext()
        prompt_block = manager.snapshot_for_prompt()
        ctx.inject_system_note(prompt_block)

        notes = ctx.get_system_notes()
        assert len(notes) == 1
        assert "World State" in notes[0]

    def test_executive_brain_uses_world_manager(self):
        """Verify ExecutiveBrain accepts world_manager and injects world state."""
        from core.executive.manager import ExecutiveBrain
        from unittest.mock import MagicMock

        mock_llm = MagicMock()
        mock_registry = MagicMock()
        mock_event_bus = MagicMock()

        world_manager = MagicMock()
        world_manager.snapshot_for_prompt.return_value = "## Current World State\nBranch: main"

        brain = ExecutiveBrain(
            llm_client=mock_llm,
            registry=mock_registry,
            event_bus=mock_event_bus,
            world_manager=world_manager,
        )

        ctx = ShortTermContext()
        with patch.object(brain._reasoning_manager, "deliberate", return_value=MagicMock()):
            brain.plan("Continue my coding session.", ctx)

        # World state should have been injected
        notes = ctx.get_system_notes()
        assert any("World State" in n for n in notes)
        world_manager.snapshot_for_prompt.assert_called_once()
