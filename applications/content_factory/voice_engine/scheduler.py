"""
Scheduler for the Voice Engine.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar('T')
R = TypeVar('R')

class VoiceScheduler:
    """Manages concurrent execution of voice generation tasks."""
    
    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max_workers

    def execute_batch(
        self,
        tasks: list[T],
        generator_func: Callable[[T], R]
    ) -> dict[str, R]:
        """
        Executes a batch of tasks in parallel using ThreadPoolExecutor.
        Returns a dictionary mapping task_id to result.
        """
        results = {}
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_task = {
                executor.submit(generator_func, task): task 
                for task in tasks
            }
            for future in future_to_task:
                task = future_to_task[future]
                try:
                    # We assume task has a task_id attribute
                    results[task.task_id] = future.result()
                except Exception as e:
                    # Capture the error and let planner handle it or re-raise
                    results[task.task_id] = (task, e)
        return results
