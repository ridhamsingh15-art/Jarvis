"""
Detects changes to files without relying on external watchdog dependencies.
"""


from .registry import KnowledgeDocument, SQLiteKnowledgeRegistry
from .scanner import KnowledgeScanner


class FileWatcher:
    """Polls the filesystem and compares against the registry to find changes."""
    
    def __init__(self, registry: SQLiteKnowledgeRegistry, root_dirs: list[str]) -> None:
        self._registry = registry
        self._scanner = KnowledgeScanner(root_dirs)
        
    def get_modified_files(self) -> list[KnowledgeDocument]:
        """Scans the roots and returns documents that are new or modified."""
        modified: list[KnowledgeDocument] = []
        
        for doc in self._scanner.scan():
            existing = self._registry.get_document_by_path(doc.path)
            
            if not existing:
                modified.append(doc)
            elif doc.last_modified > existing.last_indexed:
                # Retain the existing ID so we can overwrite chunks gracefully
                doc.id = existing.id
                modified.append(doc)
                
        return modified
