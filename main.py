"""
Jarvis — Local AI Operating System.

Entry point that wires up all components and launches the
PySide6 desktop GUI by default, or the terminal REPL with --cli.
"""

import argparse
import logging
import sys

from config.config import load_config
from core.agent import Agent
from core.planner import Planner
from core.registry import Registry
from core.task import TaskStatus
from core.validator import Validator
from memory.memory_manager import MemoryManager
from memory.sqlite_memory import SqliteMemory
from tools.base_tool import BaseTool
from tools.browser import BrowserTool
from tools.file import FileTool
from tools.windows import WindowsTool

logger = logging.getLogger(__name__)

def setup_logging() -> None:
    """Configure structured logging for the framework."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )


def build_agent() -> dict:
    """Wire up all components and return agent + context.

    Returns a dict with:
        agent: Fully constructed Agent instance.
        config: JarvisConfig (for display purposes).
        registry: Registry (for read-only tool listing).
        memory: SqliteMemory (for read-only memory browsing).
        model_name: Display string for the current model.
        memory_backend: Display string for the memory backend.
        tool_count: Number of registered tools.

    Dependency graph:
        Config → LLMClient, SqliteMemory
        WindowsTool + BrowserTool + FileTool → Registry
        LLMClient + Registry → Planner
        Registry → Validator
        Registry → Executor
        SqliteMemory → MemoryManager
        Planner + Validator + Executor + MemoryManager → Agent
    """
    config = load_config()

    # Tools
    windows_tool = WindowsTool()
    browser_tool = BrowserTool()
    file_tool = FileTool()

    # Registry
    registry = Registry()
    registry.register(windows_tool)
    registry.register(browser_tool)
    registry.register(file_tool)

    # Memory
    sqlite_memory = SqliteMemory(config.memory_db_path)
    memory_manager = MemoryManager(sqlite_memory)

    from config.model_config import ModelRouterConfig
    from core.executor.action_registry import ActionRegistry
    from core.executor.executor import ExecutionEngine
    from core.model_router import ModelRouter
    from providers.fallback_manager import FallbackManager
    from providers.health_monitor import HealthMonitor
    from providers.provider_factory import ProviderFactory
    from providers.provider_registry import ProviderRegistry
    from providers.selection_policy import WeightedScorePolicy
    
    logger.info("Selected provider: %s", config.provider)
    logger.info("Selected model: %s", config.model)
    
    provider_config = {
        "default_model": config.model,
        "default_embedding_model": config.model,
        "timeout_seconds": config.request_timeout,
        "max_retries": config.max_retries,
        "retry_backoff_seconds": config.retry_backoff_seconds,
    }
    if config.provider == "ollama":
        provider_config["base_url"] = config.ollama_host
        
    provider = ProviderFactory.create_provider(config.provider, config=provider_config)
    health_monitor = HealthMonitor()
    provider_registry = ProviderRegistry(health_monitor)
    provider_registry.register(provider)
    
    gateway = ModelRouter(
        config=ModelRouterConfig(prefer_local=True),
        registry=provider_registry,
        selection_policy=WeightedScorePolicy(health_monitor),
        fallback_manager=FallbackManager(),
        health_monitor=health_monitor,
    )
    
    action_registry = ActionRegistry()

    # Bridge tool actions into the ActionRegistry so the ExecutionEngine
    # can resolve action names (e.g. "search_google") to tool handlers.
    for tool_name in registry.list_tools():
        tool = registry.get(tool_name)
        if tool is not None:
            for action_name in tool.get_actions():
                # Closure factory avoids late-binding capture of loop variables
                def _make_handler(t: BaseTool, a: str):
                    def handler(_context, **kwargs):
                        return t.execute(a, kwargs)
                    return handler
                action_registry.register(action_name, _make_handler(tool, action_name))
                logger.debug("Bridged action: %s.%s", tool_name, action_name)

    action_count = sum(
        len(t.get_actions())
        for t in (registry.get(name) for name in registry.list_tools())
        if t is not None
    )
    logger.info("Registered %d tool actions into executor", action_count)

    from unittest.mock import MagicMock

    from core.cognition.classifier import IntentClassifier
    from core.cognition.context import ShortTermContext
    from core.cognition.manager import CognitiveManager
    from core.cognition.reflection import CognitiveReflection
    from core.cognition.router import CognitiveRouter
    from core.events.bus import EventBus
    from core.telemetry.levels import LogLevel
    from core.telemetry.logger import AsyncLogger
    
    planner = Planner(gateway, registry)
    validator = Validator(registry)
    executor = ExecutionEngine(action_registry)

    dummy_masker = MagicMock()
    dummy_masker.mask.side_effect = lambda x: x
    async_logger = AsyncLogger(level=LogLevel.INFO, masker=dummy_masker, outputs=[])
    event_bus = EventBus(logger=async_logger)
    classifier = IntentClassifier(gateway=gateway)
    router = CognitiveRouter()
    context = ShortTermContext()
    reflection = CognitiveReflection(event_bus=event_bus)
    cognitive_manager = CognitiveManager(
        classifier=classifier,
        router=router,
        reflection=reflection,
        context=context,
        event_bus=event_bus
    )

    agent = Agent(
        planner,
        validator,
        executor,
        memory=memory_manager,
        cognitive_manager=cognitive_manager,
    )

    return {
        "agent": agent,
        "config": config,
        "registry": registry,
        "memory": sqlite_memory,
        "model_name": config.model,
        "memory_backend": "SQLite",
        "tool_count": len(registry.list_tools()),
    }


def display_results(tasks: list) -> None:
    """Display task results to the user.

    Args:
        tasks: List of completed Task objects.
    """
    for task in tasks:
        if task.status == TaskStatus.COMPLETED:
            print(f"  [OK] {task.result}")
        elif task.status == TaskStatus.FAILED:
            print(f"  [FAIL] {task.error}")
        else:
            status_display = task.status.value if hasattr(task.status, 'value') else str(task.status)
            print(f"  [?] {task.tool}.{task.action} -- {status_display}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments with a ``cli`` boolean flag.
    """
    parser = argparse.ArgumentParser(
        description="Jarvis — Local AI Operating System",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        default=False,
        help="Launch the terminal REPL instead of the desktop GUI.",
    )
    return parser.parse_args()


def repl(agent: Agent) -> None:
    """Run the interactive terminal REPL.

    Args:
        agent: A fully constructed Agent instance.
    """
    print("\n  JARVIS — Local AI Operating System")
    print("  Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_input = input("  You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye.")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("  Goodbye.")
            sys.exit(0)

        results = agent.run(user_input)
        display_results(results)
        print()


def main() -> None:
    """Entry point — launches GUI by default, REPL with --cli."""
    setup_logging()
    args = parse_args()
    ctx = build_agent()

    if args.cli:
        repl(ctx["agent"])
    else:
        from gui import launch_gui

        launch_gui(ctx["agent"], config_ctx=ctx)


if __name__ == "__main__":
    main()
