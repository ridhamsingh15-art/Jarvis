"""
File tool — manages files and directories on the local filesystem.

Implements BaseTool to provide file operations using pathlib and
shutil. Validates all paths before execution and blocks operations
on Windows system directories and the Jarvis project directory.
"""

import json
import logging
import os
import shutil
from pathlib import Path

from core.action_definition import ActionDefinition
from core.exceptions import ExecutionError
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

_MAX_READ_CHARS = 64000
_MAX_DIRECTORY_ENTRIES = 200
_READ_TRUNCATION_MARKER = "\n\n[JARVIS: file content truncated after 64000 characters; additional content remains.]"

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
_SENSITIVE_READ_DIRS: frozenset[str] = frozenset({
    ".ssh", ".aws", ".azure", ".gnupg", ".kube", ".docker",
})
_SENSITIVE_READ_FILES: frozenset[str] = frozenset({
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials", "credentials.json", "secrets", "secrets.json",
    "service-account.json", "application_default_credentials.json",
    ".netrc", ".npmrc", ".pypirc", ".git-credentials",
    "token", "token.json", "access_token", "refresh_token",
})
_SENSITIVE_READ_SUFFIXES: frozenset[str] = frozenset({
    ".pem", ".key", ".p12", ".pfx", ".ppk", ".jks", ".keystore", ".kdbx",
})


def _is_sensitive_read_path(path: Path) -> bool:
    """Recognize common secret files and credential-store directories portably."""
    parts = tuple(part.casefold() for part in path.parts)
    name = path.name.casefold()
    if name == ".env" or name.startswith((".env.", ".env-", ".env_")):
        return True
    if name in _SENSITIVE_READ_FILES or name.endswith(tuple(_SENSITIVE_READ_SUFFIXES)):
        return True
    if any(part in _SENSITIVE_READ_DIRS for part in parts):
        return True
    # Google Cloud ADC and Windows credential-manager files commonly live here.
    for index, part in enumerate(parts[:-1]):
        if part == ".config" and parts[index + 1] == "gcloud":
            return True
        if (
            part == "appdata"
            and index + 2 < len(parts)
            and parts[index + 1:index + 3] in {
                ("roaming", "microsoft"), ("local", "microsoft"),
            }
            and any(token in parts[index + 3:] for token in ("credentials", "vault"))
        ):
            return True
    return False


def _resolve_path(raw: str | Path) -> Path:
    """Resolve a user-supplied path without leaking raw path-resolution errors."""
    if not isinstance(raw, (str, Path)):
        raise ExecutionError("Path must be a non-empty string.")
    raw_text = str(raw).strip()
    if not raw_text:
        raise ExecutionError("Path cannot be empty")
    try:
        return Path(raw_text).expanduser().resolve()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ExecutionError("Path could not be safely resolved.") from exc


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
        # Read, list, open, copy, and move paths must not expose known credentials.
        return _is_sensitive_read_path(path)

    # Check Jarvis project directory for mutations
    try:
        rel = path.relative_to(_PROJECT_ROOT)
        return not (
            rel.parts and rel.parts[0] in (".jarvis_test_workspace", "jarvis_test_workspace")
        )
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
    """Tool for managing files and directories, optionally bounded to a workspace."""

    _MUTATING_ACTIONS = frozenset({
        "create_file", "write_file", "append_line", "patch_file", "edit_file",
        "create_folder", "rename", "move", "copy", "delete",
    })

    def __init__(self, workspace_root: str | Path | None = None) -> None:
        self._workspace_root = Path(workspace_root).resolve() if workspace_root is not None else None

    def _enforce_workspace_boundary(self, action: str, args: dict) -> dict:
        if self._workspace_root is None or action not in self._MUTATING_ACTIONS:
            return args
        normalized = dict(args)
        keys = ["path"] + (["dest"] if action in {"move", "copy"} else [])
        for key in keys:
            raw = normalized.get(key)
            if not isinstance(raw, (str, Path)) or not str(raw).strip():
                raise ExecutionError(f"A valid '{key}' path is required for workspace-scoped writes")
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = self._workspace_root / candidate
            resolved = candidate.resolve(strict=False)
            try:
                resolved.relative_to(self._workspace_root)
            except ValueError as exc:
                raise ExecutionError(
                    f"Write blocked: '{resolved}' is outside workspace '{self._workspace_root}'"
                ) from exc
            normalized[key] = str(resolved)

        # A rename's destination is derived from ``new_name``, not ``dest``.
        # Validate it separately: checking only the source lets ``../outside``
        # escape the workspace even though ``path`` itself is contained.
        if action == "rename":
            raw_name = normalized.get("new_name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise ExecutionError("A valid 'new_name' filename is required for workspace-scoped rename")
            name_path = Path(raw_name)
            if name_path.name != raw_name or raw_name in {".", ".."}:
                raise ExecutionError("Rename target must be a single filename within the configured workspace")
            target = (Path(normalized["path"]).parent / raw_name).resolve(strict=False)
            try:
                target.relative_to(self._workspace_root)
            except ValueError as exc:
                raise ExecutionError(
                    f"Rename blocked: '{target}' is outside workspace '{self._workspace_root}'"
                ) from exc
        return normalized

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
            "append_line": ActionDefinition(
                name="append_line",
                description="Appends one UTF-8 line to an existing or new file. This is a side-effecting action requiring explicit policy approval.",
                required_args=["path", "line"],
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
            "list_largest_files": ActionDefinition(
                name="list_largest_files",
                description="Lists the largest regular files in a directory with exact paths and byte sizes.",
                required_args=["path"],
                optional_args=["limit"],
            ),
            "summarize_files": ActionDefinition(
                name="summarize_files",
                description="Summarizes the largest text files in a directory using bounded local previews.",
                required_args=["path"],
                optional_args=["limit"],
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
        # Normalize the legacy content alias before schema validation. Keep it
        # out of ActionDefinition so ToolIntelligenceManager still performs its
        # canonical content -> text normalization before the strict Validator.
        if action == "create_file" and isinstance(args, dict) and "content" in args and "text" not in args:
            args = {key: value for key, value in args.items() if key != "content"} | {"text": args["content"]}
        args = self.validate_action_call(action, args)
        from collections.abc import Callable
        dispatch: dict[str, Callable] = {
            "create_file": self._create_file,
            "write_file": self._write_file,
            "append_line": self._append_line,
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
            "list_largest_files": self._list_largest_files,
            "summarize_files": self._summarize_files,
        }

        handler = dispatch.get(action)

        if handler is None:
            raise ExecutionError(f"Unknown file action: '{action}'")

        # Check every mutating path before a handler can create directories or touch files.
        args = self._enforce_workspace_boundary(action, args)
        return handler(args)

    @staticmethod
    def _create_file(args: dict) -> str:
        """Create a file without overwriting an existing one, optionally with text."""
        path = _resolve_path(args.get("path", ""))
        _validate_path(path)

        if path.exists():
            raise ExecutionError(f"Already exists: '{path}'")

        path.parent.mkdir(parents=True, exist_ok=True)
        # "content" is a legacy alias used by existing mission payloads.
        text = args.get("text", args.get("content"))
        if text is not None:
            if not isinstance(text, str):
                raise ExecutionError("Arguments 'text'/'content' must be a string.")
            path.write_text(text, encoding="utf-8")
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
    def _append_line(args: dict) -> str:
        """Append exactly one UTF-8 line after path validation."""
        path = _resolve_path(args.get("path", ""))
        line = args.get("line")
        if not isinstance(line, str) or "\n" in line or "\r" in line:
            raise ExecutionError("Argument 'line' must be a single-line string")
        _validate_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise ExecutionError(f"Failed to append to '{path}': {exc}") from exc
        logger.info("Appended one line to: %s", path)
        return f"Appended one line to: {path}"

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
        if old_text is not None and not isinstance(old_text, str):
            raise ExecutionError("Replacement target text must be a string.")
        if new_text is not None and not isinstance(new_text, str):
            raise ExecutionError("Replacement text must be a string.")

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
        _validate_path(path, must_exist=True, read_only=True)

        if not path.is_dir():
            raise ExecutionError(f"Not a directory: '{path}'")

        entries: list[Path] = []
        for entry in path.iterdir():
            entries.append(entry)
            if len(entries) > _MAX_DIRECTORY_ENTRIES:
                break
        truncated = len(entries) > _MAX_DIRECTORY_ENTRIES
        entries = sorted(entries[:_MAX_DIRECTORY_ENTRIES])

        if not entries and not truncated:
            return f"Directory '{path.name}' is empty"

        lines: list[str] = [f"Contents of {path}:"]
        for entry in entries:
            prefix = "[DIR] " if entry.is_dir() else "      "
            lines.append(f"  {prefix}{entry.name}")

        if truncated:
            lines.append(
                f"[JARVIS: listing truncated after {_MAX_DIRECTORY_ENTRIES} entries; more entries may exist.]"
            )
        logger.info("Listed directory: %s (%d items, truncated=%s)", path, len(entries), truncated)
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
        if Path(new_name).name != new_name or new_name in {".", ".."}:
            raise ExecutionError("'new_name' must be a single filename, not a path")

        _validate_path(path, must_exist=True, read_only=True)

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

        # A move mutates its source as well as writing the destination. Apply
        # both mutation protection (system/project boundaries) and read protection
        # (sensitive credential paths) before crossing the side-effect boundary.
        _validate_path(source, must_exist=True)
        _validate_path(source, must_exist=True, read_only=True)
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

        _validate_path(source, must_exist=True, read_only=True)
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
    def _list_largest_files(args: dict) -> str:
        """Return the largest non-sensitive regular files as JSON evidence."""
        path = _resolve_path(args.get("path", ""))
        _validate_path(path, must_exist=True, read_only=True)
        if not path.is_dir():
            raise ExecutionError(f"Not a directory: '{path}'")
        try:
            limit = int(args.get("limit", 10))
        except (TypeError, ValueError) as exc:
            raise ExecutionError("Argument 'limit' must be an integer") from exc
        if not 1 <= limit <= 100:
            raise ExecutionError("Argument 'limit' must be between 1 and 100")
        files = []
        for entry in path.iterdir():
            try:
                if not entry.is_file():
                    continue
                resolved = entry.resolve()
                _validate_path(resolved, must_exist=True, read_only=True)
                files.append({"path": str(resolved), "size_bytes": resolved.stat().st_size})
            except (OSError, ExecutionError):
                # Unreadable or sensitive entries are excluded, never treated as successful output.
                continue
        files.sort(key=lambda item: (-item["size_bytes"], item["path"].casefold()))
        return json.dumps({"directory": str(path), "count": min(limit, len(files)), "files": files[:limit]}, ensure_ascii=False)

    @staticmethod
    def _summarize_files(args: dict) -> str:
        """Produce bounded previews for the largest readable text files."""
        path = _resolve_path(args.get("path", ""))
        _validate_path(path, must_exist=True, read_only=True)
        if not path.is_dir():
            raise ExecutionError(f"Not a directory: '{path}'")
        try:
            limit = int(args.get("limit", 10))
        except (TypeError, ValueError) as exc:
            raise ExecutionError("Argument 'limit' must be an integer") from exc
        if not 1 <= limit <= 100:
            raise ExecutionError("Argument 'limit' must be between 1 and 100")
        text_suffixes = {".txt", ".md", ".csv", ".json", ".log", ".py", ".html", ".css", ".js", ".xml", ".yaml", ".yml", ".ini", ".toml", ".rst"}
        files = []
        for entry in path.iterdir():
            try:
                if not entry.is_file():
                    continue
                resolved = entry.resolve()
                _validate_path(resolved, must_exist=True, read_only=True)
                files.append({"path": str(resolved), "size_bytes": resolved.stat().st_size})
            except (OSError, ExecutionError):
                continue
        files.sort(key=lambda item: (-item["size_bytes"], item["path"].casefold()))
        summaries = []
        for item in files[:limit]:
            file_path = Path(item["path"])
            preview = ""
            summary_status = "metadata_only"
            if file_path.suffix.lower() in text_suffixes:
                try:
                    _validate_path(file_path, must_exist=True, read_only=True)
                    with file_path.open("r", encoding="utf-8", errors="replace") as stream:
                        preview = stream.read(2048)
                    summary_status = "text_preview"
                except (OSError, ExecutionError) as exc:
                    summary_status = f"read_error: {type(exc).__name__}: {exc}"
            summaries.append({**item, "summary_status": summary_status, "preview": preview})
        return json.dumps({"directory": str(path), "summarized": len(summaries), "files": summaries}, ensure_ascii=False)

    @staticmethod
    def _read_file(args: dict) -> str:
        path = _resolve_path(args.get("path", ""))
        _validate_path(path, must_exist=True, read_only=True)
        if not path.is_file():
            raise ExecutionError(f"Not a file: '{path}'")
        try:
            with path.open("r", encoding="utf-8") as stream:
                content = stream.read(_MAX_READ_CHARS + 1)
            truncated = len(content) > _MAX_READ_CHARS
            if truncated:
                content = content[:_MAX_READ_CHARS] + _READ_TRUNCATION_MARKER
            logger.info("Read file: %s (returned_chars=%d, truncated=%s)", path, len(content), truncated)
            return content
        except UnicodeDecodeError as exc:
            raise ExecutionError(
                f"File '{path.name}' is not valid UTF-8 text; open it with an appropriate application instead."
            ) from exc
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
        _validate_path(path, read_only=True)

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
