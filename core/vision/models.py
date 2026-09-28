import builtins
from dataclasses import dataclass, field

from core.models import JarvisModel
from core.models.primitives import Identifier, Timestamp

from .enums import UIElementType, VisionState


@dataclass(frozen=True, slots=True)
class BoundingBox(JarvisModel):
    """Immutable representation of a 2D bounding box."""
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class ImageFrame(JarvisModel):
    """Immutable representation of an image or camera frame."""
    data: bytes
    width: int
    height: int
    format: str = "PNG"
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class Screenshot(JarvisModel):
    """Immutable representation of a captured screen state."""
    frame: ImageFrame
    window_title: str | None = None
    timestamp: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class OCRResult(JarvisModel):
    """Immutable representation of parsed text and its location."""
    text: str
    bounding_box: BoundingBox
    confidence: float


@dataclass(frozen=True, slots=True)
class DetectedObject(JarvisModel):
    """Immutable representation of a detected object in a frame."""
    label: str
    bounding_box: BoundingBox
    confidence: float


@dataclass(frozen=True, slots=True)
class UIElement(JarvisModel):
    """Immutable representation of a graphical user interface element."""
    type: UIElementType
    text: str | None
    bounding_box: BoundingBox
    state: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VisionSession(JarvisModel):
    """Immutable tracking state of a current vision context."""
    session_id: Identifier
    state: VisionState = VisionState.IDLE
    last_active: Timestamp = field(default_factory=Timestamp)


@dataclass(frozen=True, slots=True)
class ScreenContext(JarvisModel):
    """High-level snapshot aggregating multiple vision outputs."""
    screenshot: Screenshot
    ocr_results: builtins.list[OCRResult] = field(default_factory=list)
    ui_elements: builtins.list[UIElement] = field(default_factory=list)
    timestamp: Timestamp = field(default_factory=Timestamp)
