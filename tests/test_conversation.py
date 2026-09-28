from unittest.mock import MagicMock

from core.agent import Agent
from core.cognition.conversation import ConversationResponse
from core.task import TaskStatus


def test_agent_fast_path_skips_planner() -> None:
    planner = MagicMock()
    validator = MagicMock()
    executor = MagicMock()

    def execute(task):
        task.start()
        task.complete("Opened calculator")
        return task

    executor.execute.side_effect = execute

    # Build a mock CognitiveManager that returns ACTION for "open calculator"
    cognitive_manager = MagicMock()

    response = ConversationResponse(
        type="ACTION",
        message="I'll open the calculator for you.",
        tool="windows",
        action="open_app",
        parameters={"app": "calculator"},
    )

    cognitive_manager.process.return_value = response
    cognitive_manager.process_fast.return_value = response

    agent = Agent(planner, validator, executor, cognitive_manager=cognitive_manager)
    tasks = agent.run("open calculator")

    # The planner must NOT have been called — fast-path via ConversationEngine
    planner.plan.assert_not_called()
    
    # Task 0 is the system respond task
    assert tasks[0].status is TaskStatus.COMPLETED
    assert tasks[0].args["message"] == "I'll open the calculator for you."
    
    # Task 1 is the executed action task
    assert tasks[1].status is TaskStatus.COMPLETED
    assert tasks[1].tool == "windows"
    assert tasks[1].action == "open_app"

def test_agent_natural_response() -> None:
    planner = MagicMock()
    validator = MagicMock()
    executor = MagicMock()

    cognitive_manager = MagicMock()
    response = ConversationResponse(
        type="RESPONSE",
        message="I am your friendly AI.",
    )
    cognitive_manager.process.return_value = response
    cognitive_manager.process_fast.return_value = response

    agent = Agent(planner, validator, executor, cognitive_manager=cognitive_manager)
    tasks = agent.run("Who are you?")

    planner.plan.assert_not_called()
    executor.execute.assert_not_called()
    
    assert len(tasks) == 1
    assert tasks[0].status is TaskStatus.COMPLETED
    assert tasks[0].args["message"] == "I am your friendly AI."
