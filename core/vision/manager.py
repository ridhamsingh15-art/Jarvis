import asyncio
import builtins
import threading

from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .enums import VisionState
from .interfaces import (
    CameraProvider,
    ObjectDetector,
    OCRProvider,
    ScreenshotProvider,
    UIAnalyzerProvider,
)
from .models import (
    BoundingBox,
    OCRResult,
    ScreenContext,
    Screenshot,
    UIElement,
    VisionSession,
)
from .screen_context import ScreenContextManager


class VisionManager(RuntimeComponent):
    """Orchestrates the Vision Subsystem."""

    def __init__(
        self,
        screenshot: ScreenshotProvider,
        ocr: OCRProvider,
        detector: ObjectDetector,
        ui_analyzer: UIAnalyzerProvider,
        camera: CameraProvider,
        event_bus: EventBus,
        logger: AsyncLogger
    ) -> None:
        self._screenshot = screenshot
        self._ocr = ocr
        self._detector = detector
        self._ui = ui_analyzer
        self._camera = camera
        self._event_bus = event_bus
        self._logger = logger

        self._context_manager = ScreenContextManager(screenshot, ocr, ui_analyzer)
        
        self._lock = threading.RLock()
        self._session = VisionSession(session_id=Identifier("vision_1"), state=VisionState.IDLE)
        self._camera_task: asyncio.Task[None] | None = None

        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.vision",
            name="Vision System",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return

        self._state = ComponentState.STARTING
        self._logger.info("Starting Vision System...")
        
        self._state = ComponentState.RUNNING
        self._publish_event("vision.started", {})
        self._logger.info("Vision System started.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return

        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Vision System...")
        
        if self._camera_task and not self._camera_task.done():
            self._camera.stop()
            self._camera_task.cancel()
            
        self._state = ComponentState.STOPPED
        self._publish_event("vision.stopped", {})
        self._logger.info("Vision System stopped.")

    async def health(self) -> HealthReport:
        try:
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={"vision_state": self._session.state.value}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def capture_screen(self) -> ScreenContext:
        """Captures the full screen and analyzes it."""
        self._logger.info("Capturing full screen context...")
        context = self._context_manager.capture_full_context()
        self._publish_event("vision.screenshot", {"mode": "FULL_SCREEN", "window": context.screenshot.window_title or ""})
        return context

    def capture_window(self, window_title: str) -> Screenshot:
        """Captures a specific window."""
        self._logger.info(f"Capturing window: {window_title}")
        return self._screenshot.capture_window(window_title)

    def capture_region(self, region: BoundingBox) -> Screenshot:
        """Captures a specific region on screen."""
        self._logger.info(f"Capturing region: {region.width}x{region.height}")
        return self._screenshot.capture_region(region)

    def read_text(self, screenshot: Screenshot) -> builtins.list[OCRResult]:
        """Extracts text from a given screenshot."""
        results = self._ocr.extract_text(screenshot.frame)
        self._publish_event("vision.ocr.completed", {"results_count": str(len(results))})
        return results

    def analyze_ui(self, screenshot: Screenshot) -> builtins.list[UIElement]:
        """Analyzes UI elements from a given screenshot."""
        results = self._ui.analyze(screenshot.frame)
        self._publish_event("vision.ui.updated", {"elements_count": str(len(results))})
        return results

    def capture_camera(self) -> None:
        """Starts background camera capture loop."""
        with self._lock:
            if self._camera_task and not self._camera_task.done():
                return
            
            self._camera.start()
            self._camera_task = asyncio.create_task(self._camera_loop())
            self._logger.info("Camera capture started.")

    async def _camera_loop(self) -> None:
        try:
            async for frame in self._camera.get_frame():
                self._publish_event("vision.camera.frame", {"format": frame.format, "size": f"{frame.width}x{frame.height}"})
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            self._logger.error(f"Camera loop failed: {e}")
            self._camera.stop()

    def _publish_event(self, topic: str, payload: dict[str, str]) -> None:
        event = Event(
            topic=topic,
            payload=payload,
            source=self.metadata.id
        )
        self._event_bus.publish(event)
