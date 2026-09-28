"""
Scheduler for orchestrating parallel image generation tasks.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .models import GenerationTask


class GenerationScheduler:
    """Manages the parallel execution of multiple image generation tasks."""

    def __init__(self, max_workers: int = 2) -> None:
        self.max_workers = max_workers

    def execute_batch(
        self, 
        tasks: list[GenerationTask], 
        worker_func: Callable[[GenerationTask], Any]
    ) -> list[Any]:
        """
        Executes a batch of generation tasks in parallel.
        In a real scenario, this might manage GPU VRAM scheduling.
        For now, it manages thread concurrency for mocked renders or API calls.
        """
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {executor.submit(worker_func, task): task for task in tasks}
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    # We pass the exception back up through the return list so the caller handles it
                    results.append((task, exc))
        return results
