"""
Application Lifecycle Manager.

Manages application states (Start, Stop, Suspend, Resume, Restart).
"""
import logging
from typing import Any
from .models import AppState
from .registry import AppRegistry
from .exceptions import AppLifecycleError

logger = logging.getLogger(__name__)

class AppLifecycleManager:
    """Manages the state transitions of AI applications."""

    def __init__(self, registry: AppRegistry):
        self._registry = registry

    def start(self, app_id: str) -> None:
        """Start the application."""
        status = self._registry.get_status(app_id)
        if not status:
            raise AppLifecycleError(f"Application {app_id} is not registered.")
            
        if status.state in (AppState.STARTING, AppState.RUNNING):
            raise AppLifecycleError(f"Application {app_id} is already {status.state.value}.")
            
        logger.info(f"Starting application {app_id}...")
        self._registry.update_state(app_id, AppState.RUNNING)

    def stop(self, app_id: str) -> None:
        """Stop the application."""
        status = self._registry.get_status(app_id)
        if not status:
            raise AppLifecycleError(f"Application {app_id} is not registered.")
            
        if status.state == AppState.STOPPED:
            logger.info(f"Application {app_id} is already stopped.")
            return
            
        logger.info(f"Stopping application {app_id}...")
        self._registry.update_state(app_id, AppState.STOPPED)

    def suspend(self, app_id: str) -> None:
        """Suspend the application execution."""
        status = self._registry.get_status(app_id)
        if not status:
            raise AppLifecycleError(f"Application {app_id} is not registered.")
            
        if status.state != AppState.RUNNING:
            raise AppLifecycleError(f"Cannot suspend application {app_id} because it is in state {status.state.value}.")
            
        logger.info(f"Suspending application {app_id}...")
        self._registry.update_state(app_id, AppState.SUSPENDED)

    def resume(self, app_id: str) -> None:
        """Resume a suspended application."""
        status = self._registry.get_status(app_id)
        if not status:
            raise AppLifecycleError(f"Application {app_id} is not registered.")
            
        if status.state != AppState.SUSPENDED:
            raise AppLifecycleError(f"Cannot resume application {app_id} because it is in state {status.state.value}.")
            
        logger.info(f"Resuming application {app_id}...")
        self._registry.update_state(app_id, AppState.RUNNING)

    def restart(self, app_id: str) -> None:
        """Restart the application."""
        logger.info(f"Restarting application {app_id}...")
        self.stop(app_id)
        self.start(app_id)
