"""
Scans approved directories for files to index.
"""

import os
import uuid
from collections.abc import Generator
from pathlib import Path

from .metadata import determine_file_type, extract_metadata
from .registry import KnowledgeDocument

_IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv", 
    "env", ".idea", ".vscode", "build", "dist", "target"
}

_IGNORE_EXTENSIONS = {
    ".pyc", ".pyd", ".o", ".obj", ".exe", ".dll", ".so", ".dylib", ".class", 
    ".jar", ".war", ".zip", ".tar", ".gz", ".7z", ".rar", ".iso", ".bin"
}

class KnowledgeScanner:
    """Traverses directories and yields KnowledgeDocument models."""

    def __init__(self, root_dirs: list[str]) -> None:
        self.root_dirs = [Path(d).expanduser().resolve() for d in root_dirs]

    def scan(self) -> Generator[KnowledgeDocument, None, None]:
        """Yields documents for files in the approved root directories."""
        for root_dir in self.root_dirs:
            if not root_dir.exists() or not root_dir.is_dir():
                continue
                
            for doc in self._scan_dir(root_dir):
                yield doc

    def _scan_dir(self, directory: Path) -> Generator[KnowledgeDocument, None, None]:
        try:
            for entry in os.scandir(directory):
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in _IGNORE_DIRS and not entry.name.startswith("."):
                        yield from self._scan_dir(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    if not entry.name.startswith("."):
                        doc = self._create_document(entry)
                        if doc:
                            yield doc
        except PermissionError:
            pass

    def _create_document(self, entry: os.DirEntry) -> KnowledgeDocument | None:
        try:
            path = Path(entry.path)
            ext = path.suffix.lower()
            
            if ext in _IGNORE_EXTENSIONS:
                return None
                
            stat = entry.stat()
            file_type = determine_file_type(ext)
            
            return KnowledgeDocument(
                id=str(uuid.uuid4()),
                path=str(path),
                filename=path.name,
                extension=ext,
                file_type=file_type,
                size_bytes=stat.st_size,
                last_modified=stat.st_mtime,
                last_indexed=0.0,
                metadata=extract_metadata(str(path))
            )
        except Exception:
            return None
