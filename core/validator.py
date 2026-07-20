from core.task import Task
from core.registry import TOOLS


def validate(task: Task):

    # Check tool
    if task.tool not in TOOLS:
        raise ValueError(f"Unknown tool: {task.tool}")

    tool = TOOLS[task.tool]

    # Check action
    if task.action not in tool["actions"]:
        raise ValueError(
            f"Unknown action '{task.action}' for tool '{task.tool}'"
        )

    return True