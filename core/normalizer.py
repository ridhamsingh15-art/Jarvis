"""
Normalizer — maps raw AI output to the internal canonical schema.

Resolves tool aliases, action aliases, and argument aliases so
the rest of the pipeline can work with consistent names. This
module is pure data transformation — it never executes anything.
"""

from typing import Any

# Tool name aliases → canonical tool name
_TOOL_ALIASES: dict[str, str] = {
    # Windows aliases
    "application": "windows",
    "app": "windows",
    "desktop": "windows",
    "program": "windows",
    "system": "windows",
    # Browser aliases
    "web": "browser",
    "internet": "browser",
    "chrome": "browser",
    "edge": "browser",
    "firefox": "browser",
    # File aliases
    "folder": "file",
    "directory": "file",
    "filesystem": "file",
    "files": "file",
    "folders": "file",
    "fs": "file",
}

# Action name aliases → canonical action name
_ACTION_ALIASES: dict[str, str] = {
    # Windows action aliases
    "open": "open_app",
    "launch": "open_app",
    "start": "open_app",
    "run": "open_app",
    # Browser action aliases
    "search": "search_google",
    "google": "search_google",
    "search_web": "search_google",
    "navigate": "open_url",
    "go_to": "open_url",
    "browse": "open_url",
    "visit": "open_site",
    # File action aliases
    "ls": "list_directory",
    "dir": "list_directory",
    "list": "list_directory",
    "list_files": "list_directory",
    "mkdir": "create_folder",
    "make_folder": "create_folder",
    "create_directory": "create_folder",
    "new_folder": "create_folder",
    "create_file": "create_file",
    "new_file": "create_file",
    "write": "write_file",
    "write_file": "write_file",
    "rm": "delete",
    "remove": "delete",
    "mv": "move",
    "cp": "copy",
    "duplicate": "copy",
}

# Argument name aliases → canonical argument name
_ARG_ALIASES: dict[str, str] = {
    # Windows arg aliases
    "name": "app",
    "program": "app",
    "application": "app",
    "app_name": "app",
    # Browser arg aliases
    "link": "url",
    "address": "url",
    "website": "url",
    "webpage": "url",
    "site_name": "site",
    "website_name": "site",
    "search_query": "query",
    "search_term": "query",
    "search": "query",
    "text": "query",
    "content": "content",
    "contents": "content",
    # File arg aliases
    "folder": "path",
    "directory": "path",
    "file_path": "path",
    "folder_path": "path",
    "dir": "path",
    "source": "path",
    "from": "path",
    "destination": "dest",
    "target": "dest",
    "to": "dest",
    "new_name": "new_name",
    "filename": "new_name",
}


def _normalize_one(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single action dict to canonical form.

    Args:
        raw: A dict with 'tool', 'action', and optional 'args' keys.

    Returns:
        A new dict with aliases resolved and keys lowercased.
    """
    result: dict[str, Any] = {}

    # Normalize tool name
    tool = raw.get("tool", "").lower().strip()
    result["tool"] = _TOOL_ALIASES.get(tool, tool)

    # Normalize action name
    action = raw.get("action", "").lower().strip()
    if action == "open":
        result["action"] = {
            "windows": "open_app",
            "browser": "open_url",
            "file": "open_file",
        }.get(result["tool"], action)
    else:
        result["action"] = _ACTION_ALIASES.get(action, action)

    # Normalize argument names and values
    raw_args = raw.get("args", {})
    normalized_args: dict[str, Any] = {}

    for key, value in raw_args.items():
        canonical_key = _ARG_ALIASES.get(key.lower(), key.lower())

        if isinstance(value, str):
            value = value.strip()

        normalized_args[canonical_key] = value

    result["args"] = normalized_args

    return result


def normalize(raw: dict | list[dict]) -> list[dict]:
    """Normalize parsed LLM output into canonical action dicts.

    Always returns a list, even for single actions.

    Args:
        raw: A single action dict or a list of action dicts.

    Returns:
        List of normalized action dicts.
    """
    if isinstance(raw, dict):
        return [_normalize_one(raw)]

    return [_normalize_one(item) for item in raw]
