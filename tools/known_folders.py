"""Resolve Windows user folders through the shell Known Folder API."""
from __future__ import annotations

import ctypes
import os
import uuid
from pathlib import Path

_KNOWN_FOLDER_IDS = {
    "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "downloads": "374DE290-123F-4565-9164-39C4925E467B",
}


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(guid_text: str) -> _GUID:
    parsed = uuid.UUID(guid_text)
    data4 = bytes((parsed.clock_seq_hi_variant, parsed.clock_seq_low)) + parsed.node.to_bytes(6, "big")
    return _GUID(parsed.time_low, parsed.time_mid, parsed.time_hi_version, (ctypes.c_ubyte * 8).from_buffer_copy(data4))


def known_folder_path(name: str) -> Path:
    """Return a redirected user folder; JARVIS_KNOWN_FOLDER_* is a test-only override."""
    key = name.strip().casefold()
    if key not in _KNOWN_FOLDER_IDS:
        raise ValueError(f"Unsupported Windows known folder: {name!r}")
    override = os.environ.get(f"JARVIS_KNOWN_FOLDER_{key.upper()}")
    if override:
        return Path(override).expanduser().resolve()
    if os.name != "nt":
        return (Path.home() / {"desktop": "Desktop", "documents": "Documents", "downloads": "Downloads"}[key]).resolve()

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(_GUID), ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    guid = _guid(_KNOWN_FOLDER_IDS[key])
    output = ctypes.c_wchar_p()
    result = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(output))
    if result != 0:
        raise OSError(result, f"SHGetKnownFolderPath failed for {key}")
    try:
        return Path(output.value).resolve()
    finally:
        ole32.CoTaskMemFree(output)
