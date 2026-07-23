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
from core.executor import Executor
from core.llm import LLMClient
from core.planner import Planner
from core.registry import Registry
from core.task import TaskStatus
from core.validator import Validator
from memory.memory_manager import MemoryManager
from memory.sqlite_memory import SqliteMemory
from tools.browser import BrowserTool
from tools.file import FileTool
from tools.windows import WindowsTool


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

    # Core components
    llm = LLMClient(config)
    planner = Planner(llm, registry)
    validator = Validator(registry)
    executor = Executor(registry)

    agent = Agent(planner, validator, executor, memory=memory_manager)

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
            print(f"  ✓ {task.result}")
        elif task.status == TaskStatus.FAILED:
            print(f"  ✗ {task.error}")
        else:
            print(f"  ? {task.tool}.{task.action} — {task.status.value}")


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