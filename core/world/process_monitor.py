"""
Process Monitor.

Collects a snapshot of interesting running processes using the standard
`psutil` library when available, with a safe no-op fallback.

AI-process detection is heuristic: any process whose name matches a set
of known AI/ML/media binary names is flagged as an AI process.
"""
from __future__ import annotations

import logging
from typing import Optional

from .exceptions import ObserverError
from .models import ProcessInfo, ProcessStatus

logger = logging.getLogger(__name__)

# Heuristic: process names that are typically AI/ML/media workloads
_AI_PROCESS_NAMES = frozenset({
    "python", "python3", "ollama", "llama", "llama.cpp", "llama-server",
    "ffmpeg", "blender", "stable-diffusion", "comfyui", "automatic1111",
    "text-generation-webui", "whisper", "bark", "coqui",
})

# Max processes to track (avoid overwhelming the context window)
_MAX_PROCESSES = 20


def _classify_status(status_str: str) -> ProcessStatus:
    mapping = {
        "running":  ProcessStatus.RUNNING,
        "sleeping": ProcessStatus.SLEEPING,
        "zombie":   ProcessStatus.ZOMBIE,
    }
    return mapping.get(status_str.lower(), ProcessStatus.UNKNOWN)


class ProcessMonitor:
    """
    Collects a snapshot of running processes, annotating AI workloads.
    Falls back to an empty list if psutil is not installed.
    """

    def observe(self) -> list[ProcessInfo]:
        try:
            import psutil
        except ImportError:
            logger.debug("psutil not installed — process monitor returning empty list.")
            return []

        processes: list[ProcessInfo] = []
        try:
            for proc in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_info"]):
                try:
                    info = proc.info
                    name = (info.get("name") or "").lower()
                    mem_bytes = (info.get("memory_info") or None)
                    mem_mb = (mem_bytes.rss / 1_048_576) if mem_bytes else 0.0
                    is_ai = any(ai in name for ai in _AI_PROCESS_NAMES)

                    processes.append(ProcessInfo(
                        pid=info["pid"],
                        name=info.get("name", "unknown"),
                        status=_classify_status(info.get("status", "")),
                        cpu_percent=float(info.get("cpu_percent") or 0.0),
                        memory_mb=mem_mb,
                        is_ai_process=is_ai,
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:  # noqa: BLE001
            raise ObserverError(f"Process enumeration failed: {e}") from e

        # Sort AI processes first, then by CPU desc, then truncate
        processes.sort(key=lambda p: (not p.is_ai_process, -p.cpu_percent))
        return processes[:_MAX_PROCESSES]
