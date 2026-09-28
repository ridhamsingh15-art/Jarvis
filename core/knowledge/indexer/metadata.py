"""
Extracts basic metadata from files for the PKI.
"""

from pathlib import Path
from typing import Any


def extract_metadata(file_path: str) -> dict[str, Any]:
    """Extract standard metadata from a file path."""
    path = Path(file_path)
    
    try:
        stat = path.stat()
        return {
            "is_symlink": path.is_symlink(),
            "created_time": stat.st_ctime,
            "permissions": oct(stat.st_mode)[-3:],
        }
    except Exception:
        return {}

def determine_file_type(extension: str) -> str:
    """Map file extension to a logical file type."""
    ext = extension.lower()
    
    if ext in {".txt", ".md", ".csv", ".json", ".xml", ".log", ".yaml", ".yml"}:
        return "text"
    if ext in {".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".rs", ".go", ".java"}:
        return "code"
    if ext in {".pdf"}:
        return "pdf"
    if ext in {".doc", ".docx"}:
        return "word"
    if ext in {".xls", ".xlsx"}:
        return "excel"
    if ext in {".ppt", ".pptx"}:
        return "powerpoint"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}:
        return "image"
    if ext in {".mp4", ".avi", ".mov", ".mkv"}:
        return "video"
    if ext in {".mp3", ".wav", ".aac", ".ogg"}:
        return "audio"
    
    return "unknown"
