"""
Windows tool — controls Windows desktop applications.

Implements BaseTool to provide allowlisted application launching capabilities.
The tool launches only fixed command mappings; it never accepts executable paths
or command-line arguments from model-controlled input.
"""

import logging
import subprocess

from core.action_definition import ActionDefinition
from core.exceptions import ExecutionError
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

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
    """Tool for launching a fixed allowlist of Windows applications."""

    @property
    def name(self) -> str:
        return "windows"

    @property
    def description(self) -> str:
        return "Launch allowlisted Windows applications without passing model-controlled command arguments"

    def get_actions(self) -> dict[str, ActionDefinition]:
        app_list = ", ".join(_APP_COMMANDS.keys())
        return {
            "open_app": ActionDefinition(
                name="open_app",
                description=f"Launches one allowlisted Windows application. Known apps: {app_list}",
                required_args=["app"],
            ),
        }

    def execute(self, action: str, args: dict) -> str:
        args = self.validate_action_call(action, args)
        if action != "open_app":
            raise ExecutionError(f"Unknown Windows action: '{action}'")
        return self._open_app(args)

    @staticmethod
    def _open_app(args: dict) -> str:
        raw_app = args.get("app")
        if not isinstance(raw_app, str):
            raise ExecutionError("Argument 'app' must be a string.")
        app_name = raw_app.casefold().strip()
        if not app_name:
            raise ExecutionError("Missing required argument: 'app'")

        command = _APP_COMMANDS.get(app_name)
        if command is None:
            known = ", ".join(_APP_COMMANDS.keys())
            raise ExecutionError(f"Unknown application: '{app_name}'. Known apps: {known}")

        try:
            subprocess.Popen([command], shell=False)
            logger.info("Windows application launch request accepted: %s", app_name)
            return f"Launch request accepted for {app_name}; application readiness was not verified."
        except OSError as exc:
            raise ExecutionError(f"Failed to launch {app_name}: {exc}") from exc
