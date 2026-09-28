"""
Scheduler for the Animation Engine.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import List, Callable, Dict

from .models import AnimationTask, AnimationAsset


class AnimationScheduler:
    """Manages concurrent execution of animation tasks."""
    
    def __init__(self, max_workers: int = 2) -> None:
        self._max_workers = max_workers

    def execute_batch(
        self,
        tasks: List[AnimationTask],
        generator_func: Callable[[AnimationTask], AnimationAsset]
    ) -> Dict[str, AnimationAsset]:
        """
        Executes a batch of AnimationTasks in parallel using ThreadPoolExecutor.
        Returns a dictionary mapping task_id to AnimationAsset.
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
                    asset = future.result()
                    results[task.task_id] = asset
                except Exception as e:
                    # In a real system, we'd capture this error per scene.
                    # For now, we allow the planner to handle retries at the task level.
                    raise e
        return results
