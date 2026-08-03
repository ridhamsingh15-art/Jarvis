"""
Windows tool — controls Windows desktop applications.

Implements BaseTool to provide application launching capabilities.
Completely isolated from the core framework — communicates only
through the BaseTool interface.
"""

import logging
import subprocess

from core.action_definition import ActionDefinition
from core.exceptions import ExecutionError
from tools.base_tool import BaseTool  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)

# Map of friendly app names to their Windows executable commands
_APP_COMMANDS: dict[str, str] = {
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "cmd": "cmd",
    "terminal": "wt",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "snipping tool": "snippingtool",
}


class WindowsTool(BaseTool):
    """Tool for controlling Windows desktop applications."""

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "windows"

    @property
    def description(self) -> str:
        """Human-readable description for LLM prompts."""
        return "Control Windows desktop applications"

    def get_actions(self) -> dict[str, ActionDefinition]:
        """Return available actions and their structured definitions.

        Returns:
            Dict mapping action names to ActionDefinition objects.
        """
        from core.action_definition import ActionDefinition
        
        app_list = ", ".join(_APP_COMMANDS.keys())

        return {
            "open_app": ActionDefinition(
                name="open_app",
                description=f"Opens a Windows application. Known apps: {app_list}",
                required_args=["app"]
            ),
        }

    def execute(self, action: str, args: dict) -> str:
        """Execute a Windows action.

        Args:
            action: The action to perform.
            args: Arguments for the action.

        Returns:
            Human-readable result string.

        Raises:
            ExecutionError: If the action or app is unknown.
        """
        from collections.abc import Callable
        dispatch: dict[str, Callable] = {
            "open_app": self._open_app,
        }

        handler = dispatch.get(action)

        if handler is None:
            raise ExecutionError(
                f"Unknown Windows action: '{action}'"
            )

        return handler(args)

    @staticmethod
    def _open_app(args: dict) -> str:
        """Launch a Windows application by name.

        Args:
            args: Must contain 'app' key with the application name.

        Returns:
            Success message.

        Raises:
            ExecutionError: If the app is unknown or launch fails.
        """
        app_name = args.get("app", "").lower().strip()

        if not app_name:
            raise ExecutionError(
                "Missing required argument: 'app'"
            )

        command = _APP_COMMANDS.get(app_name)

        if command is None:
            known = ", ".join(_APP_COMMANDS.keys())
            raise ExecutionError(
                f"Unknown application: '{app_name}'. "
                f"Known apps: {known}"
            )

        try:
            subprocess.Popen(command)
            logger.info("Opened application: %s", app_name)
            return f"Opened {app_name}"
        except OSError as exc:
            raise ExecutionError(
                f"Failed to open {app_name}: {exc}"
            ) from exc
