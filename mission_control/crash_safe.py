"""Write-ahead, restart-safe execution for structured JARVIS missions."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from core.exceptions import ExecutionError
from core.execution_policy import (
    CapabilitySource,
    ExecutionPolicy,
    PolicyContext,
    PolicyVerdict,
)
from core.task import Task, TaskStatus
from tools.file import _validate_path

from .crash_store import CrashSafeMissionStore, CrashSafeStoreCorruptionError

_ACTIVE_STEP_CLAIMS: set[tuple[str, int, int]] = set()
_ACTIVE_STEP_CLAIMS_LOCK = threading.Lock()


def _process_is_running(pid: Any) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        open_process.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        wait_for_single_object = kernel32.WaitForSingleObject
        wait_for_single_object.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        wait_for_single_object.restype = ctypes.c_uint32
        handle = open_process(0x00100000, 0, pid)  # SYNCHRONIZE access only
        if not handle:
            return False
        try:
            return wait_for_single_object(handle, 0) == 0x00000102  # WAIT_TIMEOUT => alive
        finally:
            close_handle(handle)
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False


def _claim_is_active(mission_id: str, step_index: int, pid: int) -> bool:
    with _ACTIVE_STEP_CLAIMS_LOCK:
        return (mission_id, step_index, pid) in _ACTIVE_STEP_CLAIMS


def _register_active_claim(mission_id: str, step_index: int, pid: int) -> None:
    with _ACTIVE_STEP_CLAIMS_LOCK:
        _ACTIVE_STEP_CLAIMS.add((mission_id, step_index, pid))


def _release_active_claim(mission_id: str, step_index: int, pid: int) -> None:
    with _ACTIVE_STEP_CLAIMS_LOCK:
        _ACTIVE_STEP_CLAIMS.discard((mission_id, step_index, pid))


_READ_ONLY_ACTIONS = frozenset({
    ("file", "read_file"), ("file", "list_directory"),
    ("file", "list_largest_files"), ("file", "summarize_files"),
    ("file", "directory_file_stats"), ("file", "extension_counts"),
    ("file", "list_directory_details"),
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _windows_process_images() -> set[str] | None:
    """Read process image names independently of the action handler; None means unavailable."""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        return {row[0].casefold() for row in csv.reader(StringIO(result.stdout)) if row and row[0]}
    except (csv.Error, IndexError):
        return None


def _wait_for_process_images(expected: set[str], attempts: int = 4) -> set[str] | None:
    """Poll the OS process inventory briefly after an application/browser launch."""
    latest: set[str] | None = None
    for attempt in range(max(1, min(attempts, 6))):
        latest = _windows_process_images()
        if latest is None or latest.intersection(expected):
            return latest
        if attempt + 1 < attempts:
            time.sleep(0.25)
    return latest


def _stable_key(mission_id: str, index: int, spec: dict[str, Any]) -> str:
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{mission_id}\0{index}\0{canonical}".encode()).hexdigest()


def _paths_from_output(output: Any) -> list[str]:
    if isinstance(output, dict):
        paths = output.get("paths", [])
        if isinstance(paths, list):
            return [str(path) for path in paths]
    if isinstance(output, str):
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                return [str(item["path"]) for item in data.get("files", []) if isinstance(item, dict) and item.get("path")]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return []


def _cdp_page_urls() -> list[str] | None:
    """Read open page URLs only when loopback Chromium CDP inspection is opted in."""
    if os.environ.get("JARVIS_ENABLE_CDP_VERIFICATION") != "1":
        return None
    import http.client

    connection = http.client.HTTPConnection("127.0.0.1", 9222, timeout=0.4)
    try:
        connection.request("GET", "/json/list")
        response = connection.getresponse()
        if response.status != 200:
            return None
        payload = response.read(1_000_000)
        targets = json.loads(payload.decode("utf-8"))
        if not isinstance(targets, list):
            return None
        return [
            item["url"] for item in targets
            if isinstance(item, dict) and item.get("type") == "page"
            and isinstance(item.get("url"), str)
        ]
    except (OSError, ValueError, json.JSONDecodeError, http.client.HTTPException):
        return None
    finally:
        connection.close()


def _redact_url_evidence(url: str) -> str:
    """Keep host/path evidence but never persist userinfo, query values, or fragments."""
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        return "[invalid URL]"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    authority = host + (f":{port}" if port is not None else "")
    prefix = f"{parsed.scheme}://" if parsed.scheme else ""
    suffix = "?[redacted]" if parsed.query else ""
    suffix += "#[redacted]" if parsed.fragment else ""
    return f"{prefix}{authority}{parsed.path}{suffix}"


def _browser_url_matches(expected: str, actual: str) -> bool:
    from urllib.parse import parse_qs, urlsplit

    try:
        wanted, current = urlsplit(expected), urlsplit(actual)
        _ = wanted.port, current.port
    except ValueError:
        return False
    if wanted.scheme not in {"http", "https"} or current.scheme not in {"http", "https"}:
        return False
    if (wanted.hostname or "").casefold() != (current.hostname or "").casefold():
        return False
    if wanted.path.rstrip("/") != current.path.rstrip("/"):
        return False
    expected_query, actual_query = parse_qs(wanted.query), parse_qs(current.query)
    return all(actual_query.get(key) == values for key, values in expected_query.items())


def _verify_browser_dispatch(action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Check browser process/page evidence using the exact BrowserTool URL policy."""
    from tools.browser import build_browser_target

    try:
        target = build_browser_target(action, args)
    except (ExecutionError, TypeError, ValueError):
        return {"status": "failed", "error": "Requested browser destination is not a valid HTTP(S) URL."}
    browser_images = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe"}
    images = _wait_for_process_images(browser_images)
    if images is None:
        return {"status": "not_supported", "method": "Windows browser process inventory unavailable"}
    matched = sorted(images.intersection(browser_images))
    if not matched:
        return {"status": "failed", "error": "No supported browser process was found after the open request."}
    cdp_urls = _cdp_page_urls()
    if cdp_urls is not None:
        page_details = _cdp_page_details(target)
        matched_pages = [
            page for page in (page_details or [])
            if isinstance(page, dict)
            and isinstance(page.get("url"), str)
            and _browser_url_matches(target, page["url"])
        ]
        if matched_pages:
            page = matched_pages[0]
            body_text = page.get("text", "")
            expected_text = args.get("expected_text")
            expected_title = args.get("expected_title")
            if expected_text is not None and (
                not isinstance(expected_text, str) or not expected_text.strip()
            ):
                return {"status": "failed", "error": "expected_text must be a non-empty string when supplied."}
            if expected_title is not None and not isinstance(expected_title, str):
                return {"status": "failed", "error": "expected_title must be a string when supplied."}
            capture_page_excerpt = args.get("capture_page_excerpt", False)
            if not isinstance(capture_page_excerpt, bool):
                return {"status": "failed", "error": "capture_page_excerpt must be a boolean when supplied."}
            text_match = expected_text.strip().casefold() in body_text.casefold() if isinstance(expected_text, str) else None
            title_match = expected_title.casefold() == str(page.get("title", "")).casefold() if isinstance(expected_title, str) else None
            checks = ["destination_is_valid_http_url", "browser_process_present", "local_cdp_page_url_matches_target", "document_ready_state_complete"]
            if text_match is not None:
                checks.append("expected_text_present_in_dom")
            if title_match is not None:
                checks.append("expected_title_matches")
            evidence = {
                "page_url": _redact_url_evidence(page["url"]),
                "page_title": str(page.get("title", ""))[:200],
                "ready_state": page.get("ready_state", ""),
                "body_text_sha256": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
                "body_text_characters": len(body_text),
                "body_text_excerpt": body_text[:4000] if args.get("capture_page_excerpt") is True else "",
                "page_excerpt_captured": args.get("capture_page_excerpt") is True,
                "checks": checks,
                "expected_text_match": text_match,
                "expected_title_match": title_match,
                "process_images": matched,
            }
            if page.get("ready_state") != "complete":
                return {"status": "partial", **evidence, "limitation": "DOM is available but document loading is not complete."}
            if text_match is False or title_match is False:
                return {"status": "failed", **evidence, "error": "The requested browser postcondition was not present in the inspected page."}
            return {"status": "verified", **evidence}
        return {
            "status": "partial", "checks": ["destination_is_valid_http_url", "browser_process_present", "local_cdp_reachable"],
            "process_images": matched,
            "open_page_urls": [_redact_url_evidence(url) for url in cdp_urls[:5]],
            "limitation": "A local Chromium inspection endpoint was reachable, but no inspected open page matched the requested destination.",
        }
    return {
        "status": "partial", "checks": ["destination_is_valid_http_url", "browser_process_present"],
        "process_images": matched,
        "limitation": "No local Chromium inspection endpoint is enabled; the default-browser API does not expose active-tab URL or page content.",
    }


def _capture_append_line_baseline(args: dict[str, Any]) -> int | None:
    """Capture only safe file metadata before an append, never file contents."""
    try:
        path = Path(str(args["path"])).expanduser().resolve(strict=False)
        _validate_path(path)
        if path.exists():
            _validate_path(path, must_exist=True)
            if not path.is_file():
                return None
            return path.stat().st_size
        return 0
    except (ExecutionError, OSError, KeyError, TypeError, ValueError):
        return None


def _verify_file_mutation_outcome(
    action: str, args: dict[str, Any], baseline_file_size: int | None = None,
) -> dict[str, Any]:
    """Independently inspect common file mutation postconditions on disk."""
    try:
        raw_path = args.get("path")
        if not isinstance(raw_path, (str, Path)) or not str(raw_path).strip():
            return {"status": "failed", "error": "File mutation has no valid path argument."}
        path = Path(raw_path).expanduser().resolve(strict=False)
        if action == "delete":
            return {"status": "verified", "checks": ["deleted_path_absent"]} if not path.exists() else {"status": "failed", "error": "Deleted path still exists on disk."}
        if action == "create_folder":
            return {"status": "verified", "checks": ["directory_exists"]} if path.is_dir() else {"status": "failed", "error": "Created directory is missing."}
        if action == "rename":
            name = args.get("new_name")
            if not isinstance(name, str) or not name.strip():
                return {"status": "failed", "error": "Rename verification is missing new_name."}
            target = path.parent / name
            return {"status": "verified", "checks": ["source_absent", "renamed_target_exists"]} if not path.exists() and target.exists() else {"status": "failed", "error": "Rename postcondition did not match disk state."}
        if action == "move":
            raw_dest = args.get("dest")
            if not isinstance(raw_dest, (str, Path)) or not str(raw_dest).strip():
                return {"status": "failed", "error": "Move verification is missing dest."}
            target = Path(raw_dest).expanduser().resolve(strict=False)
            if target.is_dir():
                target = target / path.name
            return {"status": "verified", "checks": ["source_absent", "moved_target_exists"]} if not path.exists() and target.exists() else {"status": "failed", "error": "Move postcondition did not match disk state."}
        if action == "copy":
            raw_dest = args.get("dest")
            if not isinstance(raw_dest, (str, Path)) or not str(raw_dest).strip():
                return {"status": "failed", "error": "Copy verification is missing dest."}
            source = path.resolve(strict=True)
            target = Path(raw_dest).expanduser().resolve(strict=True)
            if source.is_file() and target.is_file() and source.read_bytes() == target.read_bytes():
                return {"status": "verified", "checks": ["source_and_copy_bytes_match"]}
            if source.is_dir() and target.is_dir():
                source_entries = sorted(str(item.relative_to(source)) for item in source.rglob("*"))
                target_entries = sorted(str(item.relative_to(target)) for item in target.rglob("*"))
                if source_entries == target_entries and all(
                    not (source / rel).is_file() or (source / rel).read_bytes() == (target / rel).read_bytes()
                    for rel in source_entries
                ):
                    return {"status": "verified", "checks": ["directory_entries_match", "file_bytes_match"]}
            return {"status": "failed", "error": "Copy postcondition did not match source state."}
        if action in {"create_file", "write_file"}:
            target = path.resolve(strict=True)
            if not target.is_file():
                return {"status": "failed", "error": "Expected file is missing after mutation."}
            expected = args.get("content") if action == "write_file" else args.get("text", args.get("content"))
            if expected is None:
                return {"status": "verified", "checks": ["empty_file_exists"]} if target.stat().st_size == 0 else {"status": "failed", "error": "Created empty file contains unexpected data."}
            return {"status": "verified", "checks": ["file_content_matches_requested_text"]} if isinstance(expected, str) and target.read_text(encoding="utf-8") == expected else {"status": "failed", "error": "File contents do not match the requested text."}
        if action == "append_line":
            expected_line = args.get("line")
            target = path.resolve(strict=True)
            if baseline_file_size is None:
                return {"status": "partial", "method": "append baseline unavailable; refusing to infer success"}
            if not target.is_file() or target.stat().st_size <= baseline_file_size:
                return {"status": "failed", "error": "Append did not increase the target file size."}
            lines = target.read_text(encoding="utf-8").splitlines()
            if not isinstance(expected_line, str) or not lines or lines[-1] != expected_line:
                return {"status": "failed", "error": "The final file line does not match the requested append."}
            return {"status": "verified", "checks": ["file_size_increased", "appended_line_matches_disk"]}
        if action in {"patch_file", "edit_file"}:
            target = path.resolve(strict=True)
            if not target.is_file():
                return {"status": "failed", "error": "Patched file is missing."}
            old_text = next((args.get(key) for key in ("old_text", "target_text", "search", "target", "search_pattern", "pattern", "search_text", "old_content") if args.get(key)), None)
            new_text = next((args.get(key) for key in ("new_text", "replacement_text", "replace", "replacement", "replace_pattern", "replacement_pattern", "replace_with", "replace_text", "new_content") if args.get(key) is not None), "")
            content_override = args.get("content")
            content = target.read_text(encoding="utf-8")
            if content_override is not None and old_text is None:
                matched = isinstance(content_override, str) and content == content_override
            else:
                matched = isinstance(old_text, str) and isinstance(new_text, str) and old_text not in content and (new_text == "" or new_text in content)
            if matched:
                return {"status": "verified", "checks": ["patched_file_postcondition_matches"]}
            return {"status": "partial", "method": "postcondition ambiguous; replacement could not be independently established"}
    except (ExecutionError, OSError, KeyError, TypeError, ValueError):
        return {"status": "failed", "error": "Independent file mutation postcondition check failed."}
    return {"status": "not_supported", "method": f"no independent verifier registered for file.{action}"}


def _is_known_read_only_shell_command(command: Any) -> bool:
    """Classify only a small allowlist of commands whose purpose is observation."""
    import ntpath
    import shlex

    if not isinstance(command, str) or not command.strip():
        return False
    try:
        tokens = [token.strip().strip('"').strip("'") for token in shlex.split(command, posix=False)]
    except ValueError:
        return False
    if not tokens:
        return False
    executable = ntpath.basename(tokens[0].replace("/", "\\")).casefold()
    args = [token.casefold() for token in tokens[1:]]
    if executable in {"echo", "echo.exe"}:
        return True
    if executable in {"dir", "dir.exe"}:
        return not any(token in {">", ">>", "|", "&"} for token in args)
    if executable in {"git", "git.exe"}:
        return args[:1] in (["status"], ["log"], ["branch"]) or args[:2] == ["diff", "--check"]
    if executable in {"python", "python.exe", "py", "py.exe"}:
        return args[:1] in (["--version"], ["-v"])
    return executable in {"where", "where.exe", "whoami", "whoami.exe", "hostname", "hostname.exe", "ver"}


def _verify_action_outcome(
    tool: str, action: str, args: dict[str, Any], output: Any,
    baseline_process_images: set[str] | None = None,
) -> dict[str, Any]:
    """Independently check action postconditions instead of trusting tool success text."""
    if tool == "shell" and action == "run":
        if not isinstance(output, dict) or output.get("blocked") or output.get("timed_out") or output.get("exit_code") != 0:
            return {"status": "failed", "error": "Shell process did not finish successfully."}
        command = args.get("command") or args.get("cmd") or args.get("executable")
        if _is_known_read_only_shell_command(command):
            return {"status": "verified", "checks": ["process_exit_code_zero", "read_only_command_classified"]}
        return {"status": "not_supported", "method": "shell side effects require an independent expected-state verifier"}
    if tool == "windows" and action == "open_app":
        app = args.get("app")
        known = {"notepad": {"notepad.exe"}, "calculator": {"calculator.exe", "calc.exe"},
                 "paint": {"mspaint.exe"}, "cmd": {"cmd.exe"}, "terminal": {"windowsterminal.exe", "wt.exe"},
                 "explorer": {"explorer.exe"}, "task manager": {"taskmgr.exe"}, "snipping tool": {"snippingtool.exe"}}
        if not isinstance(app, str) or app.casefold().strip() not in known:
            return {"status": "not_supported", "method": "unknown Windows application mapping"}
        if baseline_process_images is None:
            return {"status": "not_supported", "method": "No pre-action process baseline was captured"}
        images = _wait_for_process_images(known[app.casefold().strip()])
        if images is None:
            return {"status": "not_supported", "method": "Windows process inventory unavailable"}
        expected = known[app.casefold().strip()]
        matched = sorted(images.intersection(expected))
        already_running = sorted(baseline_process_images.intersection(expected))
        if matched and already_running:
            return {
                "status": "partial", "method": "matching process existed before launch",
                "process_images": matched,
                "limitation": "Process-name inventory cannot prove this action launched a new instance when the app was already running.",
            }
        if matched:
            return {"status": "verified", "checks": ["independent_process_inventory", "absent_before_action"], "process_images": matched}
        return {"status": "failed", "error": "Application process was not found in the independent Windows process inventory."}
    if tool == "browser" and action in {"open_url", "open_site", "search_google"}:
        return _verify_browser_dispatch(action, args)
    if tool != "file":
        return {"status": "not_supported", "method": "no independent verifier registered"}
    try:
        if action == "read_file":
            from tools.file import _MAX_READ_CHARS, _READ_TRUNCATION_MARKER

            path = Path(str(args["path"])).expanduser().resolve(strict=True)
            if not path.is_file() or not isinstance(output, str):
                raise ValueError("Read output does not match the file's current contents.")
            with path.open("r", encoding="utf-8") as stream:
                expected_content = stream.read(_MAX_READ_CHARS + 1)
            if len(expected_content) > _MAX_READ_CHARS:
                expected_content = expected_content[:_MAX_READ_CHARS] + _READ_TRUNCATION_MARKER
            if expected_content != output:
                raise ValueError("Read output does not match the bounded file content currently on disk.")
            return {"status": "verified", "checks": ["file_exists", "bounded_content_matches_disk"]}

        if action in {"list_largest_files", "summarize_files", "directory_file_stats", "extension_counts", "list_directory_details", "ensure_text_files"}:
            data = json.loads(output) if isinstance(output, str) else output
            if not isinstance(data, dict):
                raise ValueError("Filesystem action did not return a JSON object.")
            raw_path = args.get("path")
            path = Path(str(raw_path)).expanduser().resolve(strict=True)
            if not path.is_dir():
                raise ValueError("Target directory does not exist after execution.")
            if action == "list_largest_files":
                files = data.get("files")
                if not isinstance(files, list):
                    raise ValueError("Largest-files result is missing its files array.")
                expected_files = []
                for entry in path.iterdir():
                    try:
                        if not entry.is_file():
                            continue
                        resolved = entry.resolve(strict=True)
                        _validate_path(resolved, must_exist=True, read_only=True)
                        expected_files.append({"path": str(resolved), "size_bytes": resolved.stat().st_size})
                    except (OSError, ExecutionError):
                        continue
                expected_files.sort(key=lambda item: (-item["size_bytes"], item["path"].casefold()))
                expected_files = expected_files[:int(args.get("limit", 10))]
                actual_files = []
                for item in files:
                    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                        raise TypeError("Largest-files result contains an invalid file entry.")
                    target = Path(item["path"]).resolve(strict=True)
                    if not target.is_file() or target.stat().st_size != item.get("size_bytes") or target.parent != path:
                        raise ValueError("Reported file path or size does not match disk state.")
                    actual_files.append({"path": str(target), "size_bytes": target.stat().st_size})
                if actual_files != expected_files:
                    raise ValueError("Largest-files result does not match the independently computed top files.")
                return {"status": "verified", "checks": ["top_file_selection_matches_disk", "reported_sizes_match", "descending_size_order"]}
            if action == "summarize_files":
                files = data.get("files")
                if not isinstance(files, list):
                    raise ValueError("Summary result is missing its files array.")
                for item in files:
                    target = Path(str(item["path"])).resolve(strict=True)
                    if not target.is_file() or target.stat().st_size != item.get("size_bytes"):
                        raise ValueError("Summary file metadata does not match disk state.")
                    if item.get("summary_status") == "text_preview" and target.read_text(encoding="utf-8", errors="replace")[:2048] != item.get("preview"):
                        raise ValueError("Summary preview does not match current file contents.")
                return {"status": "verified", "checks": ["file_metadata_matches", "text_previews_match"]}
            if action == "directory_file_stats":
                files = [item for item in path.iterdir() if item.is_file()]
                files.sort(key=lambda item: -item.stat().st_size)
                largest = {"name": files[0].name, "size_bytes": files[0].stat().st_size} if files else None
                if data.get("file_count") != len(files) or data.get("largest_file") != largest:
                    raise ValueError("Directory statistics do not match current disk state.")
                return {"status": "verified", "checks": ["direct_file_count_matches", "largest_file_matches"]}
            if action == "extension_counts":
                from collections import Counter
                counts = Counter(item.suffix.casefold() for item in path.iterdir() if item.is_file())
                expected = sorted(counts.items(), key=lambda pair: -pair[1])[:int(args.get("limit", 3))]
                actual = [(item.get("extension"), item.get("count")) for item in data.get("top_extensions", []) if isinstance(item, dict)]
                if actual != expected:
                    raise ValueError("Extension counts do not match current disk state.")
                return {"status": "verified", "checks": ["extension_frequency_matches"]}
            if action == "list_directory_details":
                expected = []
                for entry in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
                    expected.append({"name": entry.name, "size_bytes": entry.stat().st_size} if entry.is_file() else {"name": entry.name, "type": "directory"})
                if data.get("entries") != expected or data.get("direct_file_count") != sum(item.is_file() for item in path.iterdir()):
                    raise ValueError("Directory listing does not match current disk state.")
                return {"status": "verified", "checks": ["entries_match", "direct_file_count_matches"]}
            if action == "ensure_text_files":
                files = args.get("files")
                if not isinstance(files, dict) or not files:
                    raise ValueError("Requested file manifest is invalid.")
                for name, content in files.items():
                    target = path / name
                    if not target.is_file() or target.read_text(encoding="utf-8") != content:
                        raise ValueError(f"File postcondition failed for {name}.")
                if any(not (path / name).is_file() for name in files):
                    raise ValueError("One or more requested files are missing.")
                return {"status": "verified", "checks": ["requested_files_exist", "contents_match"]}
        if action == "list_directory":
            path = Path(str(args["path"])).expanduser().resolve(strict=True)
            if not path.is_dir() or not isinstance(output, str):
                raise ValueError("Directory listing target or output is invalid.")
            actual_names = {entry.name for entry in path.iterdir()}
            reported_names = set()
            for line in output.splitlines()[1:]:
                item = line.strip().removeprefix("[DIR] ").strip()
                if item:
                    reported_names.add(item)
            if output.startswith("Contents of ") and reported_names != actual_names:
                raise ValueError("Directory listing does not match current directory entries.")
            if not actual_names and "is empty" not in output:
                raise ValueError("Empty-directory result is inconsistent with disk state.")
            return {"status": "verified", "checks": ["directory_exists", "entry_names_match"]}
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "failed", "error": f"Independent postcondition check failed: {type(exc).__name__}: {exc}"}
    return {"status": "not_supported", "method": f"no independent verifier registered for {tool}.{action}"}


def _parse_plan(steps: list[str]) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, set[str]]]:
    """Validate step identity and dependency edges before creating any mission record."""
    parsed: list[dict[str, Any]] = []
    indices: dict[str, int] = {}
    for index, text in enumerate(steps):
        try:
            spec = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid JSON for step {index + 1}.") from exc
        if not isinstance(spec, dict) or not isinstance(spec.get("tool"), str) or not spec["tool"]:
            raise ValueError(f"Invalid tool definition for step {index + 1}.")
        if not isinstance(spec.get("action"), str) or not spec["action"] or not isinstance(spec.get("args", {}), dict):
            raise ValueError(f"Invalid action or arguments for step {index + 1}.")
        step_id = spec.get("id", f"step_{index + 1}")
        if not isinstance(step_id, str) or not step_id or step_id in indices:
            raise ValueError(f"Missing or duplicate step id at position {index + 1}.")
        dependencies = spec.get("depends_on")
        if dependencies is None:
            dependencies = [parsed[-1].get("id", f"step_{index}") ] if parsed else []
        if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
            raise ValueError(f"Invalid dependencies for step {step_id}.")
        if len(set(dependencies)) != len(dependencies) or step_id in dependencies:
            raise ValueError(f"Invalid or self-referential dependencies for step {step_id}.")
        spec["id"] = step_id
        spec["depends_on"] = dependencies
        indices[step_id] = index
        parsed.append(spec)

    ancestors: dict[str, set[str]] = {}
    for index, spec in enumerate(parsed):
        step_id = spec["id"]
        dependencies = spec["depends_on"]
        if any(dep not in indices for dep in dependencies):
            raise ValueError(f"Unknown dependency in step {step_id}.")
        if any(indices[dep] >= index for dep in dependencies):
            raise ValueError(f"Dependencies must appear before their dependent step ({step_id}).")
        inherited: set[str] = set(dependencies)
        for dep in dependencies:
            inherited.update(ancestors[dep])
        ancestors[step_id] = inherited
    return parsed, indices, ancestors


def _iter_output_references(value: Any):
    if isinstance(value, dict):
        if "$ref" in value:
            if set(value) != {"$ref"} or not isinstance(value["$ref"], str):
                raise ValueError("Output references must contain only a string '$ref'.")
            yield value["$ref"]
            return
        for child in value.values():
            yield from _iter_output_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_output_references(child)


def _validate_resolved_argument_types(args: dict[str, Any], step_index: int) -> None:
    """Fail before invoking a tool if an output reference resolves to the wrong type."""
    string_fields = {
        "path", "query", "url", "app", "task", "command", "cmd", "executable",
        "cwd", "line", "content", "text", "new_name", "dest",
    }
    for name, value in args.items():
        if name in string_fields and not isinstance(value, str):
            raise ValueError(f"Resolved argument '{name}' for step {step_index + 1} must be a string.")
        if name == "limit" and (
            not isinstance(value, int) or isinstance(value, bool) or value < 1
        ):
            raise ValueError(f"Resolved argument 'limit' for step {step_index + 1} must be a positive integer.")
        if name == "timeout" and (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not 1 <= value <= 120
        ):
            raise ValueError(f"Resolved argument 'timeout' for step {step_index + 1} must be between 1 and 120.")
        if name == "files" and not isinstance(value, dict):
            raise ValueError(f"Resolved argument 'files' for step {step_index + 1} must be an object.")


def _resolve_output_references(
    value: Any,
    *,
    mission_id: str,
    current_index: int,
    store: CrashSafeMissionStore,
    step_indices: dict[str, int],
) -> Any:
    """Resolve explicit {'$ref': 'step_id.result.key'} values from persisted prior results."""
    if isinstance(value, dict):
        if "$ref" in value:
            if set(value) != {"$ref"} or not isinstance(value["$ref"], str):
                raise ValueError("Invalid output reference object.")
            parts = value["$ref"].split(".")
            if len(parts) < 2 or parts[1] != "result" or any(not part for part in parts):
                raise ValueError("Output references must use step_id.result[.key...] syntax.")
            source_id = parts[0]
            source_index = step_indices.get(source_id)
            if source_index is None or source_index >= current_index:
                raise ValueError("Output reference must target a prior step.")
            record = store.step(mission_id, source_index)
            if not record or record.get("status") != "completed":
                raise ValueError(f"Output reference source {source_id} has no verified completed result.")
            result = record.get("result")
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    pass
            for part in parts[2:]:
                if isinstance(result, dict) and part in result:
                    result = result[part]
                elif isinstance(result, list) and part.isdecimal() and int(part) < len(result):
                    result = result[int(part)]
                else:
                    raise ValueError(f"Output reference path does not exist: {value['$ref']}.")
            return result
        return {
            key: _resolve_output_references(
                child, mission_id=mission_id, current_index=current_index,
                store=store, step_indices=step_indices,
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve_output_references(
                child, mission_id=mission_id, current_index=current_index,
                store=store, step_indices=step_indices,
            )
            for child in value
        ]
    return value


class CrashSafeMissionRunner:
    """Execute structured tool steps with durable intent and result records.

    ``after_execute`` is a test seam invoked after the real handler returns but
    before result persistence; production callers should leave it unset.
    """

    def __init__(
        self,
        store: CrashSafeMissionStore,
        execution_engine: Any,
        policy: ExecutionPolicy,
        *,
        before_execute: Callable[[str, int, Task], None] | None = None,
        after_execute: Callable[[str, int, Task], None] | None = None,
        after_step: Callable[[str, int, dict[str, Any]], None] | None = None,
    ) -> None:
        self.store = store
        self.execution_engine = execution_engine
        self.policy = policy
        self.before_execute = before_execute
        self.after_execute = after_execute
        self.after_step = after_step

    def _corrupt_store_result(self, mission_id: str, error: CrashSafeStoreCorruptionError) -> dict[str, Any]:
        reason = (
            "Stored crash-safe mission data is corrupt. Execution stopped; inspect and "
            f"reconcile this checkpoint before resuming. {error}"
        )
        # Mark the mission terminal so a later automatic resume cannot replay work
        # using data whose arguments or evidence cannot be trusted.
        self.store.set_mission_state(mission_id, "FAILED", reason)
        mission = self.store.mission(mission_id) or {}
        mission["verification_status"] = "not_verified"
        return {"mission": mission, "steps": [], "error": reason}

    def run(self, mission_id: str, objective: str, steps: list[str]) -> dict[str, Any]:
        if not steps:
            self.store.create_mission(mission_id, objective, steps)
            reason = "Planner produced no executable steps."
            self.store.set_mission_state(mission_id, "FAILED", reason)
            return self.result(mission_id)
        try:
            parsed_plan, step_indices, ancestors = _parse_plan(steps)
            for spec in parsed_plan:
                references = list(_iter_output_references(spec.get("args", {})))
                if references and spec["tool"] in {"shell", "codex_desktop"}:
                    raise ValueError("Tool output references are not allowed in shell or desktop-agent instructions.")
                for reference in references:
                    parts = reference.split(".")
                    if (
                        len(parts) < 2 or parts[1] != "result"
                        or parts[0] not in ancestors[spec["id"]]
                        or len(parts) > 10 or any(not part for part in parts)
                    ):
                        raise ValueError(f"Invalid or undeclared output dependency in step {spec['id']}.")
        except (TypeError, ValueError) as exc:
            existing_mission = self.store.mission(mission_id)
            if existing_mission is not None:
                try:
                    existing_steps = self.store.steps(mission_id)
                except CrashSafeStoreCorruptionError as storage_error:
                    return self._corrupt_store_result(mission_id, storage_error)
                return {
                    "mission": existing_mission, "steps": existing_steps,
                    "error": f"Invalid execution plan for existing mission; durable state was not changed: {exc}",
                }
            self.store.create_mission(mission_id, objective, steps)
            self.store.set_mission_state(mission_id, "FAILED", f"Invalid execution plan: {exc}")
            return self.result(mission_id)
        existing_mission = self.store.mission(mission_id)
        if existing_mission is not None:
            try:
                persisted_steps = json.loads(existing_mission.get("steps_json", "[]"))
            except (TypeError, json.JSONDecodeError):
                return self._corrupt_store_result(
                    mission_id,
                    CrashSafeStoreCorruptionError(
                        "Stored crash-safe mission data is corrupt: crash_missions.steps_json is not valid JSON."
                    ),
                )
            if not isinstance(persisted_steps, list) or any(not isinstance(item, str) for item in persisted_steps):
                return self._corrupt_store_result(
                    mission_id,
                    CrashSafeStoreCorruptionError(
                        "Stored crash-safe mission data is corrupt: crash_missions.steps_json has an invalid JSON shape."
                    ),
                )
            if existing_mission.get("objective") != objective or persisted_steps != steps:
                try:
                    existing_steps = self.store.steps(mission_id)
                except CrashSafeStoreCorruptionError as exc:
                    return self._corrupt_store_result(mission_id, exc)
                return {
                    "mission": existing_mission, "steps": existing_steps,
                    "error": "Mission ID is already bound to a different objective or step plan; refusing to execute it.",
                }
        else:
            self.store.create_mission(mission_id, objective, steps)
        mission = self.store.mission(mission_id)
        if mission and mission["state"] in {"COMPLETED", "FAILED", "ABANDONED"}:
            return self.result(mission_id)

        for index, step_text in enumerate(steps):
            spec = parsed_plan[index]
            tool = str(spec["tool"])
            action = str(spec["action"])
            args = spec.get("args", {})
            try:
                existing = self.store.step(mission_id, index)
            except CrashSafeStoreCorruptionError as exc:
                return self._corrupt_store_result(mission_id, exc)
            if existing and existing["status"] == "completed":
                continue
            try:
                args = _resolve_output_references(
                    args, mission_id=mission_id, current_index=index,
                    store=self.store, step_indices=step_indices,
                )
                args = _prepare_expected_outcome_args(spec, tool, args)
                _validate_resolved_argument_types(args, index)
            except CrashSafeStoreCorruptionError as exc:
                return self._corrupt_store_result(mission_id, exc)
            except (TypeError, ValueError) as exc:
                reason = f"Step {index + 1} output dependency failed: {exc}"
                self.store.set_mission_state(mission_id, "FAILED", reason)
                return self.result(mission_id)
            idempotent = (tool, action) in _READ_ONLY_ACTIONS
            side_effecting = not idempotent
            if existing and existing["status"] == "started":
                owner_pid = existing.get("runner_pid", 0)
                if _claim_is_active(mission_id, index, owner_pid) or (
                    owner_pid != os.getpid() and _process_is_running(owner_pid)
                ):
                    # Another live runner owns the write-ahead intent. Do not mutate
                    # its state or execute the step a second time.
                    return self.result(mission_id)
                if side_effecting:
                    reason = (
                        f"needs_review: step {index + 1} ({tool}.{action}) was started before the previous process "
                        "stopped; the side effect outcome is unknown, so it was not replayed."
                    )
                    self.store.mark_needs_review(mission_id, index, reason)
                    return self.result(mission_id)
            if existing and existing["status"] == "pending_approval":
                # A resume must preserve the approval request; it must not convert
                # an awaiting-operator decision into a terminal failure.
                self.store.set_mission_state(
                    mission_id, "WAITING_APPROVAL",
                    str(existing.get("error") or existing.get("stderr") or "Operator approval is required."),
                )
                return self.result(mission_id)
            if existing and existing["status"] not in {"started", "completed", "retry_authorized"}:
                self.store.set_mission_state(mission_id, "FAILED", f"Step {index + 1} is terminal ({existing['status']}); automatic replay is disabled.")
                return self.result(mission_id)

            persisted_approval = bool(
                existing and existing.get("status") == "retry_authorized"
                and existing.get("stderr") == "Operator explicitly approved this step."
            )
            decision = self.policy.check(PolicyContext(
                tool=tool, action=action, source=CapabilitySource.CORE,
                source_id=f"mission:{mission_id}",
                # Approval must come from the durable operator-approval workflow, never
                # from model-authored or manually edited plan JSON.
                user_confirmed=persisted_approval,
                request_id=_stable_key(mission_id, index, spec), args=args,
            ))
            idempotency_key = _stable_key(mission_id, index, spec)
            if decision.verdict != PolicyVerdict.ALLOW:
                requires_approval = decision.verdict == PolicyVerdict.REQUIRE_CONFIRMATION
                reason = (
                    f"Execution policy requires confirmation for {tool}.{action}: {decision.reason}"
                    if requires_approval else
                    f"Execution policy denied (Execution policy deny) for {tool}.{action}: {decision.reason}"
                )
                record = {
                    "status": "pending_approval" if requires_approval else "blocked",
                    "stdout": "", "stderr": reason,
                    "normalized_code": None if requires_approval else (126 if tool == "file" else None),
                    "exit_code": None, "error": reason, "finished_at": _now(), "result": None,
                    "verification": {"status": "not_run", "method": "action was not executed"},
                }
                claimed = self.store.begin_step(
                    mission_id=mission_id, step_index=index, tool=tool, action=action, args=args,
                    idempotency_key=idempotency_key, side_effecting=side_effecting, started_at=_now(),
                    count_attempt=False,
                )
                if not claimed:
                    return self.result(mission_id)
                self.store.finish_step(mission_id, index, record)
                self.store.set_mission_state(mission_id, "WAITING_APPROVAL" if requires_approval else "FAILED", reason)
                if self.after_step is not None:
                    self.after_step(mission_id, index, record)
                return self.result(mission_id)

            claimed = self.store.begin_step(
                mission_id=mission_id, step_index=index, tool=tool, action=action, args=args,
                idempotency_key=idempotency_key, side_effecting=side_effecting, started_at=_now(),
                # Only replay an already-started read-only step after this runner has
                # checked that the previous owner is no longer active. Fresh concurrent
                # claims must remain exclusive even for read-only work.
                allow_readonly_replay=bool(
                    existing and existing["status"] == "started" and not side_effecting
                ),
            )
            if not claimed:
                return self.result(mission_id)
            runner_pid = os.getpid()
            _register_active_claim(mission_id, index, runner_pid)
            task = Task(tool=tool, action=f"{tool}.{action}", args=args, max_retries=0)
            baseline_process_images = (
                _windows_process_images() if tool == "windows" and action == "open_app" else None
            )
            baseline_file_size = (
                _capture_append_line_baseline(args) if tool == "file" and action == "append_line" else None
            )
            # Distinguish execution failures from projection/observer failures after
            # the durable step result has already committed. Never finish a committed
            # step a second time just because an after_step callback raises.
            step_result_committed = False
            try:
                if self.before_execute is not None:
                    self.before_execute(mission_id, index, task)
                self.execution_engine.execute(task)
                if self.after_execute is not None:
                    self.after_execute(mission_id, index, task)
                output = task.result
                stdout = str(output.get("stdout", "")) if isinstance(output, dict) else str(output if output is not None else "")
                stderr = str(output.get("stderr", "")) if isinstance(output, dict) else ""
                shell_blocked = bool(output.get("blocked", False)) if isinstance(output, dict) else False
                shell_timeout = bool(output.get("timed_out", False)) if isinstance(output, dict) else False
                shell_code = output.get("exit_code") if isinstance(output, dict) and tool == "shell" else None
                normalized_code = None if tool == "shell" else (0 if task.status == TaskStatus.COMPLETED else 1)
                ok = task.status == TaskStatus.COMPLETED and not shell_blocked and not shell_timeout
                if tool == "shell":
                    ok = ok and isinstance(shell_code, int) and shell_code == 0
                verification = _verify_action_outcome(
                    tool, action, args, output, baseline_process_images=baseline_process_images,
                ) if ok else {
                    "status": "not_run", "method": "tool execution did not report success"
                }
                if ok and tool == "file" and action in {
                    "create_file", "write_file", "append_line", "patch_file", "edit_file",
                    "create_folder", "rename", "move", "copy", "delete",
                }:
                    verification = _verify_file_mutation_outcome(action, args, baseline_file_size)
                if ok:
                    verification = _verify_declared_expected_outcome(
                        spec, tool, action, args, output, verification,
                    )
                verification_status = verification.get("status")
                # A tool's success-shaped return is not sufficient: dependencies may
                # proceed only after independent verification of this step's outcome.
                if verification_status != "verified":
                    ok = False
                status = "completed" if ok else ("needs_review" if side_effecting else "failed")
                if ok:
                    error = ""
                elif task.status != TaskStatus.COMPLETED or shell_blocked or shell_timeout or (tool == "shell" and shell_code != 0):
                    error = task.error or stderr or ("Shell tool timed out" if shell_timeout else f"Tool result not successful (status={task.status.value}, code={shell_code})")
                else:
                    error = (
                        verification.get("error") or verification.get("limitation")
                        or f"Independent outcome verification did not establish success "
                        f"(status={verification_status or 'missing'}, method={verification.get('method', 'unknown')})."
                    )
                record = {
                    "status": status, "stdout": stdout, "stderr": stderr,
                    "exit_code": shell_code if isinstance(shell_code, int) and not shell_blocked and not shell_timeout else None,
                    "normalized_code": normalized_code, "error": error,
                    "paths": _paths_from_output(output), "result": output,
                    "verification": verification, "finished_at": _now(),
                }
                self.store.finish_step(mission_id, index, record)
                step_result_committed = True
                if self.after_step is not None:
                    self.after_step(mission_id, index, record)
                if not ok:
                    self.store.set_mission_state(mission_id, "FAILED", f"Step {index + 1} ({tool}.{action}) failed: {error}")
                    return self.result(mission_id)
            except Exception as exc:  # noqa: BLE001 - persist arbitrary tool errors as terminal step failures
                if step_result_committed:
                    # The durable step status is authoritative. A callback used to
                    # update a legacy projection/UI is not allowed to rewrite the
                    # completed step as failed or trigger a second finish_step call.
                    error = f"Post-commit callback failed for step {index + 1}: {type(exc).__name__}: {exc}"
                    self.store.set_mission_state(mission_id, "FAILED", error)
                    return self.result(mission_id)
                # A thrown exception can happen after a side effect. Preserve that
                # uncertainty for operator reconciliation instead of labelling it safe to retry.
                error = f"{type(exc).__name__}: {exc}"
                step_status = "needs_review" if side_effecting else "failed"
                if side_effecting:
                    error = "needs_review: execution raised after the side-effect boundary; outcome is uncertain. " + error
                self.store.finish_step(mission_id, index, {
                    "status": step_status, "stdout": "", "stderr": error,
                    "exit_code": None, "normalized_code": 1 if tool != "shell" else None,
                    "error": error, "finished_at": _now(), "result": None,
                    "verification": {"status": "not_run", "method": "execution raised before independent verification"},
                })
                self.store.set_mission_state(mission_id, "FAILED", error)
                if self.after_step is not None:
                    self.after_step(mission_id, index, {"status": "failed", "error": error, "stderr": error})
                return self.result(mission_id)
            finally:
                _release_active_claim(mission_id, index, runner_pid)

        self.store.set_mission_state(mission_id, "COMPLETED", "")
        return self.result(mission_id)

    def result(self, mission_id: str) -> dict[str, Any]:
        mission = self.store.mission(mission_id)
        try:
            steps = self.store.steps(mission_id)
        except CrashSafeStoreCorruptionError as exc:
            return self._corrupt_store_result(mission_id, exc)
        if mission is not None:
            statuses = [step.get("verification", {}).get("status", "not_supported") for step in steps]
            all_verified = bool(statuses) and all(status == "verified" for status in statuses)
            any_evidence = any(
                status in {"verified", "partial"} for status in statuses
            ) or any(step.get("status") in {"completed", "needs_review"} for step in steps)
            mission["verification_status"] = (
                "verified" if mission.get("state") == "COMPLETED" and all_verified
                else "partial" if any_evidence
                else "not_verified"
            )
        return {"mission": mission, "steps": steps}


def _cdp_page_details(expected_url: str | None = None) -> list[dict[str, Any]] | None:
    """Inspect open Chromium page DOM through an explicitly enabled loopback CDP endpoint.

    Only loopback WebSocket targets from 127.0.0.1:9222 are accepted. Page text is
    read as untrusted data and is not interpreted as instructions.
    """
    import http.client
    from urllib.parse import urlsplit

    if os.environ.get("JARVIS_ENABLE_CDP_VERIFICATION") != "1":
        return None
    try:
        connection = http.client.HTTPConnection("127.0.0.1", 9222, timeout=0.6)
        try:
            connection.request("GET", "/json/list")
            response = connection.getresponse()
            if response.status != 200:
                return None
            targets = json.loads(response.read(1_000_000).decode("utf-8"))
        finally:
            connection.close()
        if not isinstance(targets, list):
            return None

        from websockets.exceptions import WebSocketException
        from websockets.sync.client import connect

        pages: list[dict[str, Any]] = []
        candidates = [
            target for target in targets
            if isinstance(target, dict) and target.get("type") == "page"
            and isinstance(target.get("webSocketDebuggerUrl"), str)
            and (
                expected_url is None
                or (
                    isinstance(target.get("url"), str)
                    and _browser_url_matches(expected_url, target["url"])
                )
            )
        ]
        for target in candidates[:3]:
            endpoint = target.get("webSocketDebuggerUrl")
            if not isinstance(endpoint, str):
                continue
            parsed = urlsplit(endpoint)
            if (
                parsed.scheme != "ws"
                or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.port != 9222
                or parsed.username
                or parsed.password
            ):
                continue
            try:
                with connect(endpoint, open_timeout=0.5, close_timeout=0.2, max_size=1_000_000) as ws:
                    ws.send(json.dumps({
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": "({url: location.href, title: document.title, readyState: document.readyState, text: (document.body && document.body.innerText || '').slice(0, 12000)})",
                            "returnByValue": True,
                            "awaitPromise": True,
                        },
                    }))
                    deadline = time.monotonic() + 1.0
                    while time.monotonic() < deadline:
                        try:
                            message = json.loads(ws.recv(timeout=max(0.05, deadline - time.monotonic())))
                        except TimeoutError:
                            break
                        if not isinstance(message, dict) or message.get("id") != 1:
                            continue
                        result = message.get("result", {}).get("result", {}).get("value")
                        if isinstance(result, dict):
                            pages.append({
                                "url": result.get("url", target.get("url", "")),
                                "title": result.get("title", "")[:300] if isinstance(result.get("title"), str) else "",
                                "ready_state": result.get("readyState", ""),
                                "text": result.get("text", "") if isinstance(result.get("text"), str) else "",
                            })
                        break
            except (OSError, ValueError, TimeoutError, RuntimeError, WebSocketException):
                continue
        return pages
    except (ImportError, OSError, ValueError, json.JSONDecodeError, http.client.HTTPException):
        return None


def _prepare_expected_outcome_args(spec: dict[str, Any], tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Translate explicitly machine-checkable browser assertions into verifier inputs."""
    expected = spec.get("expected_outcome")
    if not isinstance(expected, str):
        return args
    if tool == "browser" and expected.startswith("contains_text:"):
        value = expected.removeprefix("contains_text:").strip()
        if value:
            args["expected_text"] = value
    elif tool == "browser" and expected.startswith("title_equals:"):
        value = expected.removeprefix("title_equals:").strip()
        if value:
            args["expected_title"] = value
    return args


def _verify_declared_expected_outcome(
    spec: dict[str, Any], tool: str, action: str, args: dict[str, Any],
    output: Any, verification: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate explicit deterministic assertions; prose alone never proves success."""
    expected = spec.get("expected_outcome")
    if not isinstance(expected, str) or not expected.strip():
        return verification
    expected = expected.strip()
    if expected.startswith(("contains_text:", "title_equals:")) and tool == "browser":
        # Browser DOM assertions are evaluated by the CDP-backed browser verifier.
        if verification.get("status") not in {"verified", "failed"}:
            return {**verification, "expected_outcome_status": "not_verified",
                    "limitation": "Browser semantic assertions require accessible local Chromium DOM inspection."}
        return {**verification, "expected_outcome_status": verification.get("status")}
    if expected.startswith("url_matches:") and tool == "browser":
        wanted = expected.removeprefix("url_matches:").strip()
        requested = args.get("url") or args.get("site")
        if action not in {"open_url", "open_site"} or not isinstance(requested, str) or not _browser_url_matches(wanted, requested):
            return {
                **verification, "status": "failed", "expected_outcome_status": "failed",
                "error": "Declared URL must match the URL/site requested by this browser action.",
            }
        urls = _cdp_page_urls()
        matched = bool(wanted and urls is not None and any(_browser_url_matches(wanted, url) for url in urls))
        base_status = verification.get("status", "not_supported")
        status = base_status if base_status in {"failed", "partial"} else ("verified" if matched else "failed")
        return {
            **verification, "status": status,
            "expected_outcome_status": "verified" if matched else "failed",
            "expected_url": _redact_url_evidence(wanted) if wanted else "",
            "checks": list(verification.get("checks", [])) + ["declared_url_matches_requested_and_open_page"],
            **({} if matched else {"error": "No inspected open page matched the requested expected URL."}),
        }
    if expected.startswith("file_exists:") and tool == "file":
        raw_path = expected.removeprefix("file_exists:").strip()
        target_actions = {"create_file", "write_file", "append_line", "edit_file", "patch_file", "read_file"}
        requested_path = args.get("path")
        try:
            path = Path(raw_path).expanduser().resolve()
            requested = Path(str(requested_path)).expanduser().resolve() if isinstance(requested_path, str) else None
            same_target = requested is not None and path == requested
            matched = path.is_file()
        except (OSError, ValueError, TypeError):
            matched, same_target = False, False
            path = Path(raw_path).expanduser()
        if action not in target_actions or not same_target:
            return {
                **verification, "status": "failed", "expected_outcome_status": "failed",
                "expected_path": str(path),
                "error": "file_exists assertion must target this action's requested file path.",
            }
        base_status = verification.get("status", "not_supported")
        status = base_status if base_status in {"failed", "partial"} else ("verified" if matched else "failed")
        return {
            **verification, "status": status,
            "expected_outcome_status": "verified" if matched else "failed",
            "checks": list(verification.get("checks", [])) + ["declared_file_exists_at_requested_target"],
            "expected_path": str(path),
            **({} if matched else {"error": "Declared expected file does not exist."}),
        }
    if expected.startswith("file_contains:") and tool == "file":
        payload = expected.removeprefix("file_contains:")
        raw_path, separator, wanted_text = payload.partition("::")
        if not separator or not raw_path.strip() or not wanted_text:
            return {**verification, "status": "not_supported", "expected_outcome_status": "not_supported",
                    "limitation": "Use file_contains:<path>::<literal text> for a deterministic file assertion."}
        target_actions = {"create_file", "write_file", "append_line", "edit_file", "patch_file", "read_file"}
        requested_path = args.get("path")
        try:
            path = Path(raw_path.strip()).expanduser().resolve()
            requested = Path(str(requested_path)).expanduser().resolve() if isinstance(requested_path, str) else None
            same_target = requested is not None and path == requested
            content = path.read_text(encoding="utf-8") if same_target and path.is_file() else ""
            matched = same_target and path.is_file() and wanted_text in content
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest() if same_target and path.is_file() else ""
        except (OSError, UnicodeError, ValueError, TypeError):
            matched, same_target, digest = False, False, ""
            path = Path(raw_path.strip()).expanduser()
        if action not in target_actions or not same_target:
            return {
                **verification, "status": "failed", "expected_outcome_status": "failed",
                "error": "file_contains assertion must target this action's requested file path.",
                "expected_path": str(path),
            }
        base_status = verification.get("status", "not_supported")
        status = base_status if base_status in {"failed", "partial"} else ("verified" if matched else "failed")
        return {
            **verification, "status": status,
            "expected_outcome_status": "verified" if matched else "failed",
            "checks": list(verification.get("checks", [])) + ["declared_file_contains_text_at_requested_target"],
            "expected_text_match": matched, "observed_file_sha256": digest,
            **({} if matched else {"error": "Declared text was not found in the requested target file."}),
        }
    if expected.startswith("output_contains:"):
        wanted_text = expected.removeprefix("output_contains:").strip()
        rendered = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, default=str)
        matched = bool(wanted_text) and wanted_text.casefold() in rendered.casefold()
        base_status = verification.get("status", "not_supported")
        # Matching output is a report from the tool, not independent proof of a
        # side effect. It may add evidence but cannot upgrade a failed/unsupported
        # independent verifier to verified success.
        status = base_status if matched else "failed"
        return {
            **verification, "status": status,
            "expected_outcome_status": "verified" if matched else "failed",
            "checks": list(verification.get("checks", [])) + ["declared_output_contains_text"],
            **({} if matched else {"error": "Tool output did not contain the declared text."}),
        }
    if expected.startswith("process_running:"):
        wanted_image = expected.removeprefix("process_running:").strip().casefold()
        app = str(args.get("app", "")).casefold().strip()
        known_apps = {
            "notepad": {"notepad.exe"}, "calculator": {"calculator.exe", "calc.exe"},
            "paint": {"mspaint.exe"}, "cmd": {"cmd.exe"},
            "terminal": {"windowsterminal.exe", "wt.exe"}, "explorer": {"explorer.exe"},
            "task manager": {"taskmgr.exe"}, "snipping tool": {"snippingtool.exe"},
        }
        allowed_images = known_apps.get(app, set()) if tool == "windows" and action == "open_app" else set()
        if not wanted_image or wanted_image not in allowed_images:
            return {
                **verification, "status": "failed", "expected_outcome_status": "failed",
                "error": "process_running assertion must match the application requested by windows.open_app.",
            }
        images = _windows_process_images()
        matched = bool(images is not None and wanted_image in images)
        base_status = verification.get("status", "not_supported")
        status = base_status if base_status in {"failed", "partial"} else ("verified" if matched else "failed")
        return {
            **verification, "status": status,
            "expected_outcome_status": "verified" if matched else "failed",
            "checks": list(verification.get("checks", [])) + ["declared_requested_process_running"],
            "process_images": [wanted_image] if matched else [],
            **({} if matched else {"error": "Requested application process was not found in the independent process inventory."}),
        }
    # Natural-language descriptions remain useful plan annotations, not executable
    # proof. Action-specific independent verifiers still decide success.
    return {
        **verification,
        "declared_expected_outcome": expected[:300],
        "expected_outcome_status": "action_verifier_only",
    }
