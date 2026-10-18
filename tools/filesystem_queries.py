"""Generic, bounded filesystem queries and idempotent text-file setup actions."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from core.exceptions import ExecutionError
from tools.file import _resolve_path, _validate_path


class FileSystemQueryTool:
    """Read-only directory summaries plus idempotent creation of requested text files."""

    @staticmethod
    def get_actions() -> tuple[str, ...]:
        return (
            "directory_file_stats",
            "extension_counts",
            "ensure_text_files",
            "list_directory_details",
        )

    @staticmethod
    def get_action_definitions():
        """Return argument metadata for actions registered by the mission engine."""
        from core.action_definition import ActionDefinition

        return {
            "directory_file_stats": ActionDefinition(
                name="directory_file_stats",
                description="Count direct child files and identify the largest file.",
                required_args=["path"],
            ),
            "extension_counts": ActionDefinition(
                name="extension_counts",
                description="Count file extensions in a directory.",
                required_args=["path"],
                optional_args=["limit"],
            ),
            "ensure_text_files": ActionDefinition(
                name="ensure_text_files",
                description="Idempotently create requested .txt files without overwriting existing files.",
                required_args=["path", "files"],
            ),
            "list_directory_details": ActionDefinition(
                name="list_directory_details",
                description="List direct child entries and file sizes.",
                required_args=["path"],
            ),
        }

    def execute(self, action: str, args: dict[str, Any]) -> str:
        handler = {
            "directory_file_stats": self._directory_file_stats,
            "extension_counts": self._extension_counts,
            "ensure_text_files": self._ensure_text_files,
            "list_directory_details": self._list_directory_details,
        }.get(action)
        if handler is None:
            raise ExecutionError(f"Unknown filesystem query action: {action}")
        return handler(args)

    @staticmethod
    def _directory(args: dict[str, Any]) -> Path:
        path = _resolve_path(str(args.get("path", "")))
        _validate_path(path, must_exist=True, read_only=True)
        if not path.is_dir():
            raise ExecutionError(f"Not a directory: '{path}'")
        return path

    @classmethod
    def _directory_file_stats(cls, args: dict[str, Any]) -> str:
        path = cls._directory(args)
        files = [item for item in path.iterdir() if item.is_file()]
        files.sort(key=lambda item: -item.stat().st_size)  # stable ties match filesystem enumeration order
        largest = None
        if files:
            largest = {"name": files[0].name, "size_bytes": files[0].stat().st_size}
        return json.dumps({
            "directory": str(path),
            "scope": "top_level_files_only",
            "file_count": len(files),
            "largest_file": largest,
        }, ensure_ascii=False)

    @classmethod
    def _extension_counts(cls, args: dict[str, Any]) -> str:
        path = cls._directory(args)
        try:
            limit = int(args.get("limit", 3))
        except (TypeError, ValueError) as exc:
            raise ExecutionError("Argument 'limit' must be an integer") from exc
        if not 1 <= limit <= 100:
            raise ExecutionError("Argument 'limit' must be between 1 and 100")
        counts = Counter(item.suffix.casefold() for item in path.iterdir() if item.is_file())
        ordered = sorted(counts.items(), key=lambda pair: -pair[1])  # stable ties preserve first-seen filesystem order
        return json.dumps({
            "directory": str(path),
            "scope": "top_level_files_only",
            "case_insensitive": True,
            "top_extensions": [{"extension": ext, "count": count} for ext, count in ordered[:limit]],
        }, ensure_ascii=False)

    @staticmethod
    def _ensure_text_files(args: dict[str, Any]) -> str:
        raw_path = str(args.get("path", ""))
        path = _resolve_path(raw_path)
        _validate_path(path)
        files = args.get("files")
        if not isinstance(files, dict) or not files:
            raise ExecutionError("Argument 'files' must be a non-empty object mapping names to text")
        for name, content in files.items():
            if not isinstance(name, str) or not name or Path(name).name != name or name in {".", ".."}:
                raise ExecutionError(f"Invalid direct-child filename: {name!r}")
            if Path(name).suffix.casefold() != ".txt":
                raise ExecutionError(f"Only .txt files are supported by this action: {name}")
            if not isinstance(content, str):
                raise ExecutionError(f"Content for {name} must be a string")

        if path.exists():
            if not path.is_dir():
                raise ExecutionError(f"Expected a directory but found a non-directory: '{path}'")
            expected_names = set(files)
            unexpected = [
                entry.name for entry in path.iterdir()
                if entry.name not in expected_names or not entry.is_file()
            ]
            if unexpected:
                raise ExecutionError(
                    f"Existing directory contains unexpected entries; refusing to modify it: {unexpected}"
                )
        path.mkdir(parents=True, exist_ok=True)
        created: list[str] = []
        reused: list[str] = []
        for name, content in files.items():
            target = path / name
            _validate_path(target)
            if target.exists():
                if not target.is_file():
                    raise ExecutionError(f"Expected a file but found a non-file: '{target}'")
                actual = target.read_text(encoding="utf-8")
                if actual != content:
                    raise ExecutionError(f"Existing file has different content; refusing to overwrite: '{target}'")
                reused.append(name)
                continue
            # Exclusive create prevents accidental overwrite and makes a rerun safe.
            with target.open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
            created.append(name)

        entries = []
        for entry in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
            if entry.is_file():
                entries.append({"name": entry.name, "size_bytes": entry.stat().st_size})
            else:
                entries.append({"name": entry.name, "type": "directory"})
        return json.dumps({
            "directory": str(path),
            "created": created,
            "reused": reused,
            "entries": entries,
            "direct_file_count": sum(1 for entry in path.iterdir() if entry.is_file()),
        }, ensure_ascii=False)

    @classmethod
    def _list_directory_details(cls, args: dict[str, Any]) -> str:
        path = cls._directory(args)
        entries = []
        for entry in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
            if entry.is_file():
                entries.append({"name": entry.name, "size_bytes": entry.stat().st_size})
            else:
                entries.append({"name": entry.name, "type": "directory"})
        return json.dumps({
            "directory": str(path),
            "entries": entries,
            "direct_file_count": sum(1 for entry in path.iterdir() if entry.is_file()),
        }, ensure_ascii=False)
