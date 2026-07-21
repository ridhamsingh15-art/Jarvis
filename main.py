"""
Jarvis — Local AI Operating System.

Entry point that wires up all components and runs the
interactive REPL loop.
"""

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


def build_agent() -> Agent:
    """Wire up all components and return a configured Agent.

    Dependency graph:
        Config → LLMClient
        WindowsTool + BrowserTool + FileTool → Registry
        LLMClient + Registry → Planner
        Registry → Validator
        Registry → Executor
        Planner + Validator + Executor → Agent
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

    # Core components
    llm = LLMClient(config)
    planner = Planner(llm, registry)
    validator = Validator(registry)
    executor = Executor(registry)

    return Agent(planner, validator, executor)


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


def main() -> None:
    """Run the Jarvis interactive REPL."""
    setup_logging()

    print("\n  JARVIS — Local AI Operating System")
    print("  Type 'exit' or 'quit' to stop.\n")

    agent = build_agent()

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


if __name__ == "__main__":
    main()