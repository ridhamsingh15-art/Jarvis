import asyncio
from unittest.mock import MagicMock

import pytest

from core.events.bus import EventBus
from core.runtime.enums import ComponentState
from core.vision import (
    BoundingBox,
    DefaultObjectDetector,
    DefaultUIAnalyzer,
    ImageFrame,
    MSSScreenshotProvider,
    OpenCVCameraProvider,
    TesseractOCRProvider,
    VisionManager,
)


@pytest.fixture
def screenshot():
    return MSSScreenshotProvider()

@pytest.fixture
def ocr():
    return TesseractOCRProvider()

@pytest.fixture
def detector():
    return DefaultObjectDetector()

@pytest.fixture
def ui_analyzer():
    return DefaultUIAnalyzer()

@pytest.fixture
def camera():
    return OpenCVCameraProvider()

@pytest.fixture
def manager(screenshot, ocr, detector, ui_analyzer, camera):
    logger = MagicMock()
    event_bus = EventBus(logger)
    return VisionManager(
        screenshot=screenshot,
        ocr=ocr,
        detector=detector,
        ui_analyzer=ui_analyzer,
        camera=camera,
        event_bus=event_bus,
        logger=logger
    )

@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    await manager.stop()
    assert manager.state == ComponentState.STOPPED

def test_screenshot_capture(screenshot):
    res = screenshot.capture_screen()
    assert res.frame.width == 1920
    
    res = screenshot.capture_window("Test")
    assert res.window_title == "Test"
    
    res = screenshot.capture_region(BoundingBox(x=0, y=0, width=100, height=100))
    assert res.frame.width == 100

def test_ocr_provider(ocr):
    frame = ImageFrame(data=b"mock TEXT payload", width=100, height=100)
    res = ocr.extract_text(frame)
    assert len(res) == 1
    assert res[0].text == "Hello World"
    
    empty_frame = ImageFrame(data=b"empty", width=100, height=100)
    assert len(ocr.extract_text(empty_frame)) == 0

def test_ui_analyzer(ui_analyzer):
    frame = ImageFrame(data=b"mock UI payload", width=100, height=100)
    res = ui_analyzer.analyze(frame)
    assert len(res) == 1
    assert res[0].text == "Submit"

def test_manager_integration(manager):
    ctx = manager.capture_screen()
    assert ctx.screenshot.frame.width == 1920
    
    # Text reading from screenshot
    text_results = manager.read_text(ctx.screenshot)
    assert isinstance(text_results, list)
    
    # UI from screenshot
    ui_results = manager.analyze_ui(ctx.screenshot)
    assert isinstance(ui_results, list)

@pytest.mark.asyncio
async def test_camera_integration(manager):
    await manager.start()
    manager.capture_camera()
    assert manager._camera_task is not None
    assert manager._camera._is_running is True
    
    await asyncio.sleep(0.1) # Let camera capture a frame
    
    await manager.stop()
    assert manager._camera._is_running is False
