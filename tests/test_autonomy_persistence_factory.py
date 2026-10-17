from __future__ import annotations

from dataclasses import replace

import pytest

from config.config import JarvisConfig, load_config
from core.autonomy import InMemoryGoalPersistence
from core.autonomy.factory import create_goal_persistence
from core.autonomy.sqlite_persistence import SQLiteGoalPersistence


def test_load_config_reads_autonomy_persistence_settings(monkeypatch, tmp_path):
    database = tmp_path / "goals.sqlite3"
    monkeypatch.setenv("JARVIS_AUTONOMY_PERSISTENCE", "sqlite")
    monkeypatch.setenv("JARVIS_AUTONOMY_DB", str(database))

    config = load_config()

    assert config.autonomy_persistence_backend == "sqlite"
    assert config.autonomy_db_path == str(database)


def test_factory_creates_configured_sqlite_store(tmp_path):
    database = tmp_path / "nested" / "goals.sqlite3"
    config = replace(
        JarvisConfig(),
        autonomy_persistence_backend="sqlite",
        autonomy_db_path=str(database),
    )

    store = create_goal_persistence(config)

    assert isinstance(store, SQLiteGoalPersistence)
    assert database.exists()
    assert store.path == database.resolve()


def test_factory_keeps_memory_backend_available(tmp_path):
    config = replace(
        JarvisConfig(),
        autonomy_persistence_backend="memory",
        autonomy_db_path=str(tmp_path / "must-not-exist.sqlite3"),
    )

    store = create_goal_persistence(config)

    assert isinstance(store, InMemoryGoalPersistence)
    assert not (tmp_path / "must-not-exist.sqlite3").exists()


def test_factory_rejects_unknown_backend():
    config = replace(JarvisConfig(), autonomy_persistence_backend="remote-magic")

    with pytest.raises(ValueError, match="expected 'sqlite' or 'memory'"):
        create_goal_persistence(config)


@pytest.mark.asyncio
async def test_manager_factory_persists_created_goals(tmp_path):
    from unittest.mock import MagicMock

    from core.autonomy import DAGGoalScheduler, DefaultGoalEvaluator, DefaultGoalPlanner
    from core.autonomy.factory import create_autonomous_goal_manager
    from core.events.bus import EventBus

    database = tmp_path / "manager-goals.sqlite3"
    config = replace(
        JarvisConfig(),
        autonomy_persistence_backend="sqlite",
        autonomy_db_path=str(database),
    )
    logger = MagicMock()
    manager = create_autonomous_goal_manager(
        planner=DefaultGoalPlanner(),
        scheduler=DAGGoalScheduler(),
        evaluator=DefaultGoalEvaluator(),
        event_bus=EventBus(logger),
        logger=logger,
        config=config,
    )

    created = manager.create_goal("Persist this goal")
    loaded = SQLiteGoalPersistence(database).get_goal(created.id)

    assert loaded is not None
    assert loaded.description == "Persist this goal"
    assert loaded.id == created.id
