"""
Agent Pipeline

1. Receive user input
2. Ask planner for tasks
3. Normalize tasks
4. Convert to Task objects
5. Validate tasks
6. Execute tasks
7. Return results
"""
from core.planner import plan
from core.validator import validate
from core.executor import execute


class Agent:

    def run(self, prompt):

        tasks = plan(prompt)

        if not isinstance(tasks, list):
            tasks = [tasks]

        results = []

        for task in tasks:

            validate(task)

            result = execute(task)

            results.append(result)

        return results