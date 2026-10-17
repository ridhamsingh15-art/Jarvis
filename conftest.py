"""Keep Windows pytest temporary state isolated per process.

Pytest's default numbered temp root is shared by all runs under %TEMP%. A stale or
malformed pytest-current directory symlink can raise PermissionError during
pytest_sessionfinish, preventing the terminal summary and changing the exit code.
Use a private basetemp for each run unless the caller explicitly supplies one.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def pytest_configure(config) -> None:
    if os.name != "nt" or config.option.basetemp is not None:
        return
    basetemp = Path(tempfile.mkdtemp(prefix="jarvis-pytest-"))
    config._jarvis_private_basetemp = basetemp
    config.option.basetemp = str(basetemp)


def pytest_unconfigure(config) -> None:
    basetemp = getattr(config, "_jarvis_private_basetemp", None)
    if basetemp is not None:
        shutil.rmtree(basetemp, ignore_errors=True)
