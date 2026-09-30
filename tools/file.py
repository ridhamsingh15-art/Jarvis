"""
File tool — manages files and directories on the local filesystem.

Implements BaseTool to provide file operations using pathlib and
shutil. Validates all paths before execution and blocks operations
on Windows system directories and the Jarvis project directory.
"""

import logging
import os
import shutil
from pathlib import Path

from core.action_definition import ActionDefinition
from core.exceptions import ExecutionError
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# Directories that must never be modified or deleted (prefix match)
_PROTECTED_PREFIXES: tuple[str, ...] = (
    os.environ.get("SYSTEMROOT", r"C:\Windows"),
    r"C:\Program Files",
    r"C:\Program Files (x86)",
)

# Paths protected by exact match (e.g. drive root)
_PROTECTED_EXACT: tuple[str, ...] = (
    os.environ.get("SYSTEMDRIVE", "C:") + "\\",
)

# The Jarvis project root (this file lives at tools/file.py)
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


def _resolve_path(raw: str) -> Path:
    """Resolve a user-supplied path string to an absolute Path.

    Args:
        raw: Raw path string from the user.

    Returns:
        Resolved absolute Path.

    Raises:
        ExecutionError: If the path string is empty.
    """
    raw = raw.strip()

    if not raw:
        raise ExecutionError("Path cannot be empty")

    return Path(raw).resolve()


def _is_protected(path: Path, read_only: bool = False) -> bool:
    """Check if a path falls within a protected directory.

    Protected directories include Windows system directories
    and the Jarvis project directory itself (for write/delete mutations).
    The system drive root is protected by exact match only.

    Args:
        path: Resolved absolute path to check.
        read_only: If True, allow reading workspace files while blocking sensitive files.

    Returns:
        True if the path is protected.
    """
    path_str = str(path).lower()

    # Check exact-match protected paths (e.g. C:\)
    for protected in _PROTECTED_EXACT:
        if path_str.rstrip("\\") == protected.lower().rstrip("\\"):
            return True

    # Check prefix-match protected directories
    for protected in _PROTECTED_PREFIXES:
        if path_str.startswith(protected.lower()):
            return True

    if read_only:
        # For read-only operations, block secret/credential files
        if path.name == ".env" or path.name.endswith(".pem") or path.name.endswith(".key"):
            return True
        return False

    # Check Jarvis project directory for mutations
    try:
        rel = path.relative_to(_PROJECT_ROOT)
        if (
            rel.name.startswith("jarvis_session_test")
            or rel.name.startswith("test_")
            or (rel.parts and rel.parts[0] in (".jarvis_test_workspace", "jarvis_test_workspace"))
        ):
            return False
        return True
    except ValueError:
        return False


def _validate_path(path: Path, must_exist: bool = False, read_only: bool = False) -> None:
    """Validate a path for safety and existence.

    Args:
        path: Resolved absolute path.
        must_exist: If True, raise if the path does not exist.
        read_only: If True, evaluate with read-only safety rules.

    Raises:
        ExecutionError: If the path is protected or doesn't exist.
    """
    if _is_protected(path, read_only=read_only):
        raise ExecutionError(
            f"Operation blocked: '{path}' is in a protected directory"
        )

    if must_exist and not path.exists():
        raise ExecutionError(f"Path does not exist: '{path}'")


class FileTool(BaseTool):
    """Tool for managing files and directories."""

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "file"

    @property
    def description(self) -> str:
        """Human-readable description for LLM prompts."""
        return "Manage files and directories on the local filesystem"

    def get_actions(self) -> dict[str, ActionDefinition]:
        """Return available actions and their structured definitions."""
        from core.action_definition import ActionDefinition
        
        return {
            "create_file": ActionDefinition(
                name="create_file",
                description="Creates a file, including parent directories. If text is provided, writes it.",
                required_args=["path"],
                optional_args=["text"],
            ),
            "write_file": ActionDefinition(
                name="write_file",
                description="Writes text to a file, replacing existing contents.",
                required_args=["path", "content"],
            ),
            "list_directory": ActionDefinition(
                name="list_directory",
                description="Lists contents of a directory.",
                required_args=["path"]
            ),
            "create_folder": ActionDefinition(
                name="create_folder",
                description="Creates a new folder (and parents if needed).",
                required_args=["path"]
            ),
            "rename": ActionDefinition(
                name="rename",
                description="Renames a file or folder.",
                required_args=["path", "new_name"]
            ),
            "move": ActionDefinition(
                name="move",
                description="Moves a file or folder to a new location.",
                required_args=["path", "dest"]
            ),
            "copy": ActionDefinition(
                name="copy",
                description="Copies a file or folder.",
                required_args=["path", "dest"]
            ),
            "delete": ActionDefinition(
                name="delete",
                description="Deletes a file or empty folder.",
                required_args=["path"]
            ),
            "open_file": ActionDefinition(
                name="open_file",
                description="Opens a file with the default application.",
                required_args=["path"]
            ),
            "read_file": ActionDefinition(
                name="read_file",
                description="Reads and returns text content from a file.",
                required_args=["path"]
            ),
            "patch_file": ActionDefinition(
                name="patch_file",
                description="Surgically modifies a file by replacing old_text with new_text.",
                required_args=["path"],
                optional_args=[
                    "old_text", "new_text", "target_text", "replacement_text",
                    "search", "replace", "target", "replacement", "content",
                    "search_pattern", "replace_pattern", "replacement_pattern", "pattern",
                    "replace_with", "old_content", "new_content", "search_text", "replace_text",
                ],
            ),
            "edit_file": ActionDefinition(
                name="edit_file",
                description="Edits a file by replacing target_text with replacement_text.",
                required_args=["path"],
                optional_args=[
                    "old_text", "new_text", "target_text", "replacement_text",
                    "search", "replace", "target", "replacement", "content",
                    "search_pattern", "replace_pattern", "replacement_pattern", "pattern",
                    "replace_with", "old_content", "new_content", "search_text", "replace_text",
                ],
            ),
        }

    def execute(self, action: str, args: dict) -> str:
        """Execute a file action.

        Args:
            action: The action to perform.
            args: Arguments for the action.

        Returns:
            Human-readable result string.

        Raises:
            ExecutionError: If the action fails.
        """
        from collections.abc import Callable
        dispatch: dict[str, Callable] = {
            "create_file": self._create_file,
            "write_file": self._write_file,
            "patch_file": self._patch_file,
            "edit_file": self._patch_file,
            "list_directory": self._list_directory,
            "create_folder": self._create_folder,
            "rename": self._rename,
            "move": self._move,
            "copy": self._copy,
            "delete": self._delete,
            "open_file": self._open_file,
            "read_file": self._read_file,
        }

        handler = dispatch.get(action)

        if handler is None:
            raise ExecutionError(f"Unknown file action: '{action}'")

        return handler(args)

    @staticmethod
    def _create_file(args: dict) -> str:
        """Create a file without overwriting an existing one, optionally with text."""
        path = _resolve_path(args.get("path", ""))
        _validate_path(path)

        if path.exists():
            raise ExecutionError(f"Already exists: '{path}'")

        path.parent.mkdir(parents=True, exist_ok=True)
        text = args.get("text")
        if text is not None:
            path.write_text(str(text), encoding="utf-8")
        else:
            path.touch(exist_ok=False)
        logger.info("Created file: %s", path)
        return f"Created file: {path}"

    @staticmethod
    def _write_file(args: dict) -> str:
        """Write text to an existing or new file after safety validation."""
        path = _resolve_path(args.get("path", ""))
        content = args.get("content")
        if not isinstance(content, str):
            raise ExecutionError("Argument 'content' must be a string")

        _validate_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise ExecutionError(f"Failed to write '{path}': {exc}") from exc

        logger.info("Wrote file: %s", path)
        return f"Wrote {len(content)} character(s) to: {path}"

    @staticmethod
    def _patch_file(args: dict) -> str:
        """Surgically replace old_text with new_text in an existing file after validation."""
        path = _resolve_path(args.get("path", ""))
        _validate_path(path, must_exist=True)

        old_text = (
            args.get("old_text") or args.get("target_text") or args.get("search") or
            args.get("target") or args.get("search_pattern") or args.get("pattern") or
            args.get("search_text") or args.get("old_content")
        )
        new_text = (
            args.get("new_text") or args.get("replacement_text") or args.get("replace") or
            args.get("replacement") or args.get("replace_pattern") or
            args.get("replacement_pattern") or args.get("replace_with") or
            args.get("replace_text") or args.get("new_content")
        )
        content_override = args.get("content")

        if content_override is not None and old_text is None:
            return FileTool._write_file(args)

        if old_text is None:
            raise ExecutionError("Missing required argument: 'old_text' or 'target_text'")
        if new_text is None:
            new_text = ""

        current_content = path.read_text(encoding="utf-8")
        if old_text not in current_content:
            raise ExecutionError(f"Target text not found in '{path}'. Nothing was modified.")

        updated_content = current_content.replace(old_text, new_text, 1)
        path.write_text(updated_content, encoding="utf-8")
        logger.info("Patched file: %s", path)
        return f"Successfully modified '{path}': replaced {len(old_text)} character(s) with {len(new_text)} character(s)."

    @staticmethod
    def _list_directory(args: dict) -> str:
        """List contents of a directory.

        Args:
            args: Must contain 'path' key.

        Returns:
            Formatted listing of directory contents.
        """
        path = _resolve_path(args.get("path", ""))
        _validate_path(path, must_exist=True)

        if not path.is_dir():
            raise ExecutionError(f"Not a directory: '{path}'")

        entries = sorted(path.iterdir())

        if not entries:
            return f"Directory '{path.name}' is empty"

        lines: list[str] = [f"Contents of {path}:"]

        for entry in entries:
            prefix = "[DIR] " if entry.is_dir() else "      "
            lines.append(f"  {prefix}{entry.name}")

        logger.info("Listed directory: %s (%d items)", path, len(entries))

        return "\n".join(lines)

    @staticmethod
    def _create_folder(args: dict) -> str:
        """Create a new folder, including parent directories.

        Args:
            args: Must contain 'path' key.

        Returns:
            Success message.
        """
        path = _resolve_path(args.get("path", ""))
        _validate_path(path)

        if path.exists():
            raise ExecutionError(f"Already exists: '{path}'")

        path.mkdir(parents=True, exist_ok=False)
        logger.info("Created folder: %s", path)

        return f"Created folder: {path}"

    @staticmethod
    def _rename(args: dict) -> str:
        """Rename a file or folder.

        Args:
            args: Must contain 'path' and 'new_name' keys.

        Returns:
            Success message.
        """
        path = _resolve_path(args.get("path", ""))
        new_name = args.get("new_name", "").strip()

        if not new_name:
            raise ExecutionError("Missing required argument: 'new_name'")

        _validate_path(path, must_exist=True)

        new_path = path.parent / new_name
        _validate_path(new_path)

        if new_path.exists():
            raise ExecutionError(f"Target already exists: '{new_path}'")

        path.rename(new_path)
        logger.info("Renamed: %s -> %s", path, new_path)

        return f"Renamed '{path.name}' to '{new_name}'"

    @staticmethod
    def _move(args: dict) -> str:
        """Move a file or folder to a new location.

        Args:
            args: Must contain 'path' and 'dest' keys.

        Returns:
            Success message.
        """
        source = _resolve_path(args.get("path", ""))
        dest = _resolve_path(args.get("dest", ""))

        _validate_path(source, must_exist=True)
        _validate_path(dest)

        result_path = shutil.move(str(source), str(dest))
        logger.info("Moved: %s -> %s", source, result_path)

        return f"Moved '{source.name}' to '{dest}'"

    @staticmethod
    def _copy(args: dict) -> str:
        """Copy a file or folder.

        Args:
            args: Must contain 'path' and 'dest' keys.

        Returns:
            Success message.
        """
        source = _resolve_path(args.get("path", ""))
        dest = _resolve_path(args.get("dest", ""))

        _validate_path(source, must_exist=True)
        _validate_path(dest)

        if source.is_dir():
            shutil.copytree(str(source), str(dest))
        else:
            shutil.copy2(str(source), str(dest))

        logger.info("Copied: %s -> %s", source, dest)

        return f"Copied '{source.name}' to '{dest}'"

    @staticmethod
    def _delete(args: dict) -> str:
        """Delete a file or empty folder.

        Args:
            args: Must contain 'path' key.

        Returns:
            Success message.
        """
        path = _resolve_path(args.get("path", ""))
        _validate_path(path, must_exist=True)

        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()

        logger.info("Deleted: %s", path)

        return f"Deleted '{path.name}'"

    @staticmethod
    def _read_file(args: dict) -> str:
        path = _resolve_path(args.get("path", ""))
        _validate_path(path, must_exist=True, read_only=True)
        if not path.is_file():
            raise ExecutionError(f"Not a file: '{path}'")
        try:
            content = path.read_text(encoding="utf-8")
            logger.info("Read file: %s (%d chars)", path, len(content))
            return content
        except OSError as exc:
            raise ExecutionError(f"Failed to read '{path.name}': {exc}") from exc

    @staticmethod
    def _open_file(args: dict) -> str:
        """Open a file with the default application.

        Args:
            args: Must contain 'path' key.

        Returns:
            Success message.
        """
        path = _resolve_path(args.get("path", ""))

        if not path.exists():
            raise ExecutionError(f"File does not exist: '{path}'")

        if not path.is_file():
            raise ExecutionError(f"Not a file: '{path}'")

        try:
            os.startfile(str(path))
            logger.info("Opened file: %s", path)
            return f"Opened '{path.name}'"
        except OSError as exc:
            raise ExecutionError(
                f"Failed to open '{path.name}': {exc}"
            ) from exc
