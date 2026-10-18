"""Configuration-aware factories for autonomy infrastructure."""
from __future__ import annotations

from typing import TYPE_CHECKING

from config.config import JarvisConfig, load_config
from core.events.bus import EventBus
from core.telemetry import AsyncLogger

from .interfaces import IGoalEvaluator, IGoalPersistence, IGoalPlanner, IGoalScheduler
from .persistence import InMemoryGoalPersistence
from .sqlite_persistence import SQLiteGoalPersistence
from .step_executor import IGoalStepExecutor

if TYPE_CHECKING:
    from .manager import AutonomousGoalManager


def create_goal_persistence(config: JarvisConfig | None = None) -> IGoalPersistence:
    """Create the configured goal store.

    SQLite is the default for durable application runs. Tests can continue to
    inject ``InMemoryGoalPersistence`` directly, or select it explicitly with
    ``JARVIS_AUTONOMY_PERSISTENCE=memory``.
    """
    settings = config or load_config()
    backend = settings.autonomy_persistence_backend.strip().lower()
    if backend == "sqlite":
        return SQLiteGoalPersistence(settings.autonomy_db_path)
    if backend in {"memory", "in-memory", "inmemory"}:
        return InMemoryGoalPersistence()
    raise ValueError(
        "Unsupported autonomy persistence backend "
        f"{settings.autonomy_persistence_backend!r}; expected 'sqlite' or 'memory'."
    )



def create_autonomous_goal_manager(
    *,
    planner: IGoalPlanner,
    scheduler: IGoalScheduler,
    evaluator: IGoalEvaluator,
    event_bus: EventBus,
    logger: AsyncLogger,
    config: JarvisConfig | None = None,
    step_executor: IGoalStepExecutor | None = None,
) -> AutonomousGoalManager:
    """Build a goal manager with the persistence backend selected by config.

    Dependencies remain explicit so callers can supply their application's
    planner, scheduler, evaluator, event bus, and logger without hidden globals.
    """
    from .manager import AutonomousGoalManager

    return AutonomousGoalManager(
        planner=planner,
        scheduler=scheduler,
        persistence=create_goal_persistence(config),
        evaluator=evaluator,
        event_bus=event_bus,
        logger=logger,
        step_executor=step_executor,
    )
