import builtins
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from .models import (
    BoundingBox,
    DetectedObject,
    ImageFrame,
    OCRResult,
    Screenshot,
    UIElement,
)


class ScreenshotProvider(ABC):
    """Abstract interface for capturing screen images."""

    @abstractmethod
    def capture_screen(self) -> Screenshot:
        pass

    @abstractmethod
    def capture_window(self, window_title: str) -> Screenshot:
        pass

    @abstractmethod
    def capture_region(self, region: BoundingBox) -> Screenshot:
        pass


class OCRProvider(ABC):
    """Abstract interface for Optical Character Recognition."""

    @abstractmethod
    def extract_text(self, image: ImageFrame) -> builtins.list[OCRResult]:
        pass


class ObjectDetector(ABC):
    """Abstract interface for detecting generic objects in an image."""

    @abstractmethod
    def detect(self, image: ImageFrame) -> builtins.list[DetectedObject]:
        pass


class UIAnalyzerProvider(ABC):
    """Abstract interface for analyzing UI hierarchies from an image."""

    @abstractmethod
    def analyze(self, image: ImageFrame) -> builtins.list[UIElement]:
        pass


class CameraProvider(ABC):
    """Abstract interface for hardware camera capture."""

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def get_frame(self) -> AsyncGenerator[ImageFrame, None]:
        pass
