"""
Windows tool — controls Windows desktop applications.

Implements BaseTool to provide application launching capabilities.
Completely isolated from the core framework — communicates only
through the BaseTool interface.
"""

import logging
import subprocess

from core.exceptions import ExecutionError
from tools.base_tool import BaseTool

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

    def get_actions(self) -> dict[str, str]:
        """Return available actions and their descriptions.

        Returns:
            Dict mapping action names to descriptions.
        """
        app_list = ", ".join(_APP_COMMANDS.keys())

        return {
            "open_app": (
                f"Opens a Windows application. "
                f"Requires 'app' argument. "
                f"Known apps: {app_list}"
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
        dispatch: dict[str, callable] = {
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
