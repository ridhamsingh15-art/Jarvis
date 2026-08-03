from pathlib import Path
from unittest.mock import MagicMock

from core.agent import Agent
from core.task import Task, TaskStatus
from memory.memory_manager import MemoryManager
from memory.sqlite_memory import SqliteMemory


def test_personal_fact_survives_a_new_memory_manager(tmp_path: Path) -> None:
    db_path = str(tmp_path / "memory.db")
    first_manager = MemoryManager(SqliteMemory(db_path))
    first_manager.remember_fact("favorite editor", "VS Code")

    second_manager = MemoryManager(SqliteMemory(db_path))

    assert second_manager.recall_fact("favorite editor") == "VS Code"


def test_agent_remembers_and_recalls_a_personal_fact(tmp_path: Path) -> None:
    memory = MemoryManager(SqliteMemory(str(tmp_path / "memory.db")))
    agent = Agent(MagicMock(), MagicMock(), MagicMock(), memory=memory)

    remembered = agent.run("remember my favorite editor is VS Code")
    recalled = agent.run("what is my favorite editor?")

    assert remembered[0].status == TaskStatus.COMPLETED
    assert remembered[0].result == "I'll remember that your favorite editor is VS Code."
    assert recalled[0].status == TaskStatus.COMPLETED
    assert recalled[0].result == "Your favorite editor is VS Code."


def test_agent_remembers_and_recalls_a_name(tmp_path: Path) -> None:
    memory = MemoryManager(SqliteMemory(str(tmp_path / "memory.db")))
    agent = Agent(MagicMock(), MagicMock(), MagicMock(), memory=memory)

    agent.run("my name is Ridham")
    result = agent.run("can you say my name?")

    assert result[0].result == "Your name is Ridham."


def test_agent_hides_internal_execution_errors_from_the_user() -> None:
    executor = MagicMock()
    failed_task = Task(tool="file", action="create_file", args={"path": "test.txt"})
    failed_task.start()
    failed_task.fail("Already exists: 'C:/private/path/test.txt'")
    executor.execute.return_value = failed_task
    validator = MagicMock()
    agent = Agent(MagicMock(), validator, executor)

    result = agent._process_task(
        Task(tool="file", action="create_file", args={"path": "test.txt"})
    )

    assert (
        result.error
        == "That file or folder already exists. Please choose another name."
    )
