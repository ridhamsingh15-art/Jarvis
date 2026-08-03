from enum import StrEnum


class VisionState(StrEnum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"

class CameraState(StrEnum):
    RECORDING = "RECORDING"
    IDLE = "IDLE"
    ERROR = "ERROR"

class CaptureMode(StrEnum):
    FULL_SCREEN = "FULL_SCREEN"
    WINDOW = "WINDOW"
    REGION = "REGION"

class UIElementType(StrEnum):
    BUTTON = "BUTTON"
    TEXT_FIELD = "TEXT_FIELD"
    MENU = "MENU"
    WINDOW = "WINDOW"
    STATUS_BAR = "STATUS_BAR"
