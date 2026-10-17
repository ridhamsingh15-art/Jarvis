import hashlib
import os
import uuid
from typing import ClassVar

from core.models.primitives import Identifier

from .interfaces import IDocumentParser
from .models import KnowledgeDocument


class TextParser(IDocumentParser):
    """Parses standard text-based files."""

    SUPPORTED_EXTS: ClassVar[set[str]] = {
        ".txt", ".md", ".csv", ".html", ".json", ".xml",
        ".py", ".java", ".cpp", ".js", ".rs", ".go"
    }

    def parse(self, file_path: str) -> KnowledgeDocument:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} not found.")

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return KnowledgeDocument(
            id=Identifier(f"doc_{uuid.uuid4().hex[:8]}"),
            path=file_path,
            content=content,
            content_hash=content_hash,
            metadata={"type": "text"}
        )

    def supports(self, file_path: str) -> bool:
        _, ext = os.path.splitext(file_path)
        return ext.lower() in self.SUPPORTED_EXTS


class BinaryParserMock(IDocumentParser):
    """Mocks parsing of complex binary documents like PDFs for testing purposes."""

    SUPPORTED_EXTS: ClassVar[set[str]] = {".pdf", ".docx", ".xlsx", ".pptx"}

    def parse(self, file_path: str) -> KnowledgeDocument:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} not found.")

        # For the mock, we pretend to extract text from the file name and size
        file_size = os.path.getsize(file_path)
        content = f"Mock extracted content from binary file {os.path.basename(file_path)} with size {file_size}."
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        return KnowledgeDocument(
            id=Identifier(f"doc_{uuid.uuid4().hex[:8]}"),
            path=file_path,
            content=content,
            content_hash=content_hash,
            metadata={"type": "binary_mock"}
        )

    def supports(self, file_path: str) -> bool:
        _, ext = os.path.splitext(file_path)
        return ext.lower() in self.SUPPORTED_EXTS
