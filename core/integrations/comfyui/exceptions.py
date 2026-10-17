"""
Exceptions for the ComfyUI Integration.
"""

class ComfyUIError(Exception):
    """Base exception for the ComfyUI integration."""

class ComfyUIServerOfflineError(ComfyUIError):
    """Raised when the ComfyUI server is unreachable."""

class WorkflowExecutionError(ComfyUIError):
    """Raised when a workflow fails during execution on the server."""

class ImageDownloadError(ComfyUIError):
    """Raised when output images cannot be downloaded."""

class WebSocketTimeoutError(ComfyUIError):
    """Raised when a generation job hangs and times out."""
