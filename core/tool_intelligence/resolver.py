"""
Tool Name Resolver — intelligently matches LLM tool names to registered tools.
"""



class ToolResolver:
    """Resolves aliased or hallucinated tool names to valid system tools and actions."""

    from typing import ClassVar

    # Maps a hallucinated full tool name directly to (tool, action)
    _TOOL_ALIASES: ClassVar[dict[str, tuple[str, str]]] = {
        "open_browser": ("browser", "open_url"),
        "search_google": ("browser", "search_google"),
        "search_web": ("browser", "search_google"),
        "write_file": ("file", "write_file"),
        "create_file": ("file", "write_file"),
        "save_file": ("file", "write_file"),
        "read_file": ("file", "read_file"),
        "open_file": ("file", "open_file"),
        "delete_file": ("file", "delete_file"),
        "launch_notepad": ("windows", "open_app"),
        "open_calculator": ("windows", "open_app"),
        "open_application": ("windows", "open_app"),
        "launch_program": ("windows", "open_app"),
        "start_app": ("windows", "open_app"),
        "execute_program": ("windows", "open_app"),
        "run_application": ("windows", "open_app"),
    }

    # Maps a hallucinated action name to a real action name within a specific tool
    _ACTION_ALIASES: ClassVar[dict[str, dict[str, str]]] = {
        "file": {
            "write": "write_file",
            "create": "write_file",
            "save": "write_file",
            "read": "read_file",
            "list": "list_directory",
            "mkdir": "create_folder",
        },
        "browser": {
            "open": "open_url",
            "browse": "open_url",
            "search": "search_google",
        },
        "windows": {
            "launch": "open_app",
            "run": "open_app",
            "open": "open_app",
        }
    }

    def resolve(self, tool_name: str, action_name: str) -> tuple[str, str, bool]:
        """Resolve the tool and action name.

        Args:
            tool_name: The raw tool name from the LLM.
            action_name: The raw action name from the LLM.

        Returns:
            A tuple of (resolved_tool, resolved_action, was_repaired).
        """
        repaired = False
        resolved_tool = tool_name.lower().strip()
        resolved_action = action_name.lower().strip()

        # 1. Check if the "tool name" itself is actually an action alias (e.g. LLM outputs tool="write_file")
        if resolved_tool in self._TOOL_ALIASES:
            resolved_tool, resolved_action = self._TOOL_ALIASES[resolved_tool]
            repaired = True

        # 2. Check if the action is aliased within the tool
        if resolved_tool in self._ACTION_ALIASES:
            aliases = self._ACTION_ALIASES[resolved_tool]
            if resolved_action in aliases:
                resolved_action = aliases[resolved_action]
                repaired = True

        return resolved_tool, resolved_action, repaired
