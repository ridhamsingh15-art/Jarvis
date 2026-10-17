"""Intent-to-tool planner for bounded, evidence-producing filesystem tasks."""
from __future__ import annotations

import json
import re
from pathlib import Path

from tools.known_folders import known_folder_path


def _documents_path() -> Path:
    return known_folder_path("documents")


def _downloads_path() -> Path:
    return known_folder_path("downloads")


def _desktop_path() -> Path:
    return known_folder_path("desktop")


def _step(tool: str, action: str, args: dict) -> str:
    return json.dumps({"tool": tool, "action": action, "args": args}, ensure_ascii=False)


def build_objective_plan(objective: str) -> list[str]:
    """Map a supported objective to explicit tool steps; never invent tool results."""
    text = objective.strip()
    if not text:
        raise ValueError("Objective cannot be empty")

    # Explicit destructive file requests still become structured steps; the crash-safe
    # ExecutionPolicy records the denial before FileTool can run.
    delete_match = re.match(r"\s*(?:please\s+)?delete\s+(?:the\s+)?(?:file\s+)?(.+?)\s*[.!]?\s*$", text, re.IGNORECASE)
    if delete_match:
        raw_path = delete_match.group(1).strip().strip("'\"")
        if raw_path:
            return [_step("file", "delete", {"path": str(Path(raw_path).expanduser())})]

    # General bounded list/summarize objectives use only explicitly named paths.
    largest_match = re.search(
        r"\blist\s+(?:the\s+)?(\d+)\s+largest\s+files?\s+in\s+(.+?)(?:\s+and\s+summarize\s+them)?[.!]?\s*$",
        text, re.IGNORECASE,
    )
    if largest_match:
        limit = int(largest_match.group(1))
        if not 1 <= limit <= 100:
            raise ValueError("Requested largest-file count must be between 1 and 100")
        raw_path = largest_match.group(2).strip().strip("'\"")
        if not raw_path:
            raise ValueError("A directory path is required for largest-file objectives")
        path = str(Path(raw_path).expanduser())
        steps = [_step("file", "list_largest_files", {"path": path, "limit": limit})]
        if re.search(r"\band\s+summarize\s+them\b", text, re.IGNORECASE):
            steps.append(_step("file", "summarize_files", {"path": path, "limit": limit}))
        return steps

    # Explicit shell commands are sent through the shell policy gate, never executed here.
    shell_match = re.search(
        r"\b(?:run|execute)\s+(?:the\s+)?command\s+(.+?)\s+"
        r"(?:on|against)\s+(?:my\s+)?(?P<folder>downloads|documents|desktop)(?:\s+folder)?(?:\s+to\s+.+)?$",
        text,
        flags=re.IGNORECASE,
    )
    if shell_match:
        command = shell_match.group(1).strip().strip('"')
        folder_name = shell_match.group("folder").casefold()
        folder = {"downloads": _downloads_path, "documents": _documents_path, "desktop": _desktop_path}[folder_name]()
        if re.match(r"^(?:rmdir|rd|del|erase)\b", command, re.IGNORECASE) and not re.search(r"[A-Za-z]:\\|%[A-Za-z_]", command):
            command = f'{command} "{folder}"'
        return [_step("shell", "run", {"command": command, "cwd": str(Path.home()), "timeout": 30})]

    # A bounded read of one explicitly named path; the file tool reports missing files.
    read_match = re.search(
        r"\b(?:read|open)\s+(?:the\s+)?file\s+(.+?)\s+and\s+tell\s+me\s+what\s+it\s+says\s*\.?$",
        text,
        flags=re.IGNORECASE,
    )
    if read_match:
        raw_path = read_match.group(1).strip().strip('"')
        return [_step("file", "read_file", {"path": str(Path(raw_path).expanduser())})]

    # Direct-child file count and largest-file metadata.
    if (
        re.search(r"\b(?:total\s+number|how\s+many|count)\b", text, re.IGNORECASE)
        and re.search(r"\bfiles?\b", text, re.IGNORECASE)
        and re.search(r"\b(?:documents|desktop|downloads)\b", text, re.IGNORECASE)
        and re.search(r"\blargest\b", text, re.IGNORECASE)
    ):
        folder_match = re.search(r"\b(documents|desktop|downloads)\b", text, re.IGNORECASE)
        folder_name = folder_match.group(1).casefold() if folder_match else "documents"
        folder_path = {"documents": _documents_path, "desktop": _desktop_path, "downloads": _downloads_path}[folder_name]()
        return [_step("file", "directory_file_stats", {"path": str(folder_path)})]

    # Top extension frequencies, grouped case-insensitively by suffix.
    if (
        re.search(r"\bextensions?\b", text, re.IGNORECASE)
        and re.search(r"\b(?:most\s+often|most\s+common|top)\b", text, re.IGNORECASE)
        and re.search(r"\bdownloads\b", text, re.IGNORECASE)
    ):
        count_match = re.search(r"\b(?:top\s+)?(\d+)\s+(?:file\s+)?extensions?\b", text, re.IGNORECASE)
        limit = int(count_match.group(1)) if count_match else 3
        if not 1 <= limit <= 20:
            raise ValueError("Requested extension count must be between 1 and 20")
        return [_step("file", "extension_counts", {"path": str(_downloads_path()), "limit": limit})]

    # Idempotently ensure a set of requested text files, then return actual directory entries.
    create_match = re.search(
        r"\bcreate\s+(?:a\s+)?folder\s+named\s+([A-Za-z0-9_. -]+?)\s*,?\s+"
        r"(?:put|create|write)\s+(?:two\s+)?text\s+files?\s+in\s+it\s+called\s+(.+?)\s+"
        r"containing\s+(.+?)\s*,?\s+then\s+list\s+the\s+folder\s+with\s+file\s+sizes\s*\.?$",
        text,
        flags=re.IGNORECASE,
    )
    if create_match:
        folder_name = create_match.group(1).strip().strip('"')
        filenames_text = create_match.group(2).strip()
        contents_text = create_match.group(3).strip().rstrip(".")
        if not folder_name or Path(folder_name).name != folder_name or folder_name in {".", ".."}:
            raise ValueError("Folder name must be a single directory name")
        filename_matches = re.findall(r"([A-Za-z0-9_.-]+\.txt)", filenames_text, flags=re.IGNORECASE)
        content_match = re.search(r"(?:the\s+)?words?\s+([A-Za-z0-9_.-]+)\s+(?:and|,)\s+([A-Za-z0-9_.-]+)", contents_text, flags=re.IGNORECASE)
        content_matches = [content_match.groups()] if content_match else []
        if len(filename_matches) < 2 or not content_matches:
            raise ValueError("Could not identify two text filenames and their contents")
        names = filename_matches[:2]
        words = content_matches[0]
        files = {names[0]: words[0], names[1]: words[1]}
        target = _documents_path() / folder_name
        return [_step("file", "ensure_text_files", {"path": str(target), "files": files})]

    raise ValueError(
        "I couldn't safely map this objective to supported tools. No action was executed."
    )
