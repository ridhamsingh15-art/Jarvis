"""Own the durable autonomy manager on a dedicated asyncio loop for synchronous UI/CLI callers."""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from .exceptions import GoalExecutionError


class AutonomyService:
    """Lifecycle wrapper that keeps scheduling active while the desktop app is open."""

    def __init__(self, manager: Any) -> None:
        self.manager = manager
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._shutdown_lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._loop is not None and self._thread is not None and self._thread.is_alive()

    def start(self, timeout: float = 10.0) -> None:
        with self._shutdown_lock:
            if self.running:
                return
            self._ready.clear()
            self._startup_error = None
            self._thread = threading.Thread(
                target=self._thread_main, name="jarvis-autonomy-loop", daemon=True,
            )
            self._thread.start()
        if not self._ready.wait(timeout):
            raise GoalExecutionError("Timed out starting the durable autonomy service.")
        if self._startup_error is not None:
            raise GoalExecutionError(
                f"Could not start durable autonomy service: {self._startup_error}"
            ) from self._startup_error

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.manager.start())
        except Exception as exc:  # noqa: BLE001 - relay startup failures to caller
            self._startup_error = exc
            self._ready.set()
            loop.close()
            self._loop = None
            return
        loop.call_soon(self._ready.set)
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            self._loop = None

    def _require_running(self) -> asyncio.AbstractEventLoop:
        loop = self._loop
        if loop is None or loop.is_closed() or not loop.is_running():
            raise GoalExecutionError("Durable autonomy service is not running.")
        return loop

    def create_goal(self, description: str):
        self._require_running()
        return self.manager.create_goal(description)

    def start_goal(self, goal_id):
        self._require_running()
        return self.manager.start_goal(goal_id)

    def pause_goal(self, goal_id):
        self._require_running()
        return self.manager.pause_goal(goal_id)

    def resume_goal(self, goal_id):
        self._require_running()
        return self.manager.resume_goal(goal_id)

    def cancel_goal(self, goal_id):
        self._require_running()
        return self.manager.cancel_goal(goal_id)

    def status(self, goal_id):
        return self.manager.status(goal_id)

    def list_goals(self):
        return self.manager.list_goals()

    def get_plan(self, goal_id):
        return self.manager.get_plan(goal_id)

    def create_schedule(self, description: str, interval_seconds: int):
        self._require_running()
        return self.manager.create_schedule(description, interval_seconds)

    def list_schedules(self):
        return self.manager.list_schedules()

    def set_schedule_enabled(self, schedule_id: str, enabled: bool):
        self._require_running()
        return self.manager.set_schedule_enabled(schedule_id, enabled)

    def delete_schedule(self, schedule_id: str):
        self._require_running()
        return self.manager.delete_schedule(schedule_id)

    def list_schedule_runs(self, schedule_id: str | None = None):
        return self.manager.list_schedule_runs(schedule_id)

    def shutdown(self, timeout: float = 15.0) -> None:
        with self._shutdown_lock:
            loop, thread = self._loop, self._thread
            if loop is None or thread is None:
                return
            stop_error: Exception | None = None
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self.manager.stop(), loop)
                try:
                    future.result(timeout=timeout)
                except FutureTimeout as exc:
                    future.cancel()
                    stop_error = GoalExecutionError("Timed out stopping durable autonomy service.")
                    stop_error.__cause__ = exc
                except Exception as exc:  # noqa: BLE001 - ensure the loop stops even if shutdown reports an error
                    stop_error = exc
                finally:
                    loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=timeout)
            if thread.is_alive():
                raise GoalExecutionError("Autonomy service thread did not stop cleanly.") from stop_error
            self._thread = None
            self._loop = None
            if stop_error is not None:
                raise GoalExecutionError(f"Autonomy service shutdown reported an error: {stop_error}") from stop_error
