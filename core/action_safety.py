"""Conservative classification of built-in actions by side-effect risk.

This is intentionally a small allowlist. Only actions with no intended external
mutation may use ordinary failure recovery after invocation; all other tool outcomes
remain uncertain unless an explicit no-execution guarantee is carried by the error.
"""

from __future__ import annotations

# Keep aligned with mission_control.crash_safe's idempotent/read-only allowlist.
# Shell, browser navigation, desktop actions and every mutation are excluded by default.
READ_ONLY_ACTIONS: frozenset[tuple[str, str]] = frozenset({
    ("file", "read_file"),
    ("file", "list_directory"),
    ("file", "list_largest_files"),
    ("file", "summarize_files"),
    ("file", "directory_file_stats"),
    ("file", "extension_counts"),
    ("file", "list_directory_details"),
})


def is_known_read_only_action(tool: object, action: object) -> bool:
    """Return true only for an explicitly allowlisted read-only built-in action."""
    if not isinstance(tool, str) or not isinstance(action, str):
        return False
    return (tool.strip().casefold(), action.strip().casefold()) in READ_ONLY_ACTIONS


_PRE_SIDE_EFFECT_FAILURES: dict[tuple[str, str], tuple[str, ...]] = {
    # FileTool._open_file performs these checks before os.startfile is called.
    ("file", "open_file"): (
        "file does not exist:",
        "path does not exist:",  # compatibility with older FileTool/test doubles
        "not a file:",
        "operation blocked:",
    ),
}


def is_known_pre_side_effect_failure(tool: object, action: object, error: object) -> bool:
    """Recognize only built-in validation failures known to occur before side effects.

    This deliberately does not infer safety from generic phrases such as "permission
    denied" or "failed": those may happen after partial mutations.
    """
    if not isinstance(tool, str) or not isinstance(action, str) or not isinstance(error, str):
        return False
    key = (tool.strip().casefold(), action.strip().casefold())
    message = error.strip().casefold()
    # Isolated handlers preserve the exception class as a protocol prefix. Strip only
    # known class labels, then require an exact built-in pre-side-effect prefix.
    known_exception_prefixes = {
        "executionerror", "isolatedhandlererror", "runtimeerror", "valueerror",
        "filenotfounderror", "notadirectoryerror", "execution failed",
    }
    while ":" in message:
        prefix, remainder = message.split(":", 1)
        if prefix.strip() not in known_exception_prefixes:
            break
        message = remainder.strip()
    return any(message.startswith(prefix) for prefix in _PRE_SIDE_EFFECT_FAILURES.get(key, ()))
