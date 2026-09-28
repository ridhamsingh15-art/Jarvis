"""
Models for the Publishing Engine.
"""
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class PublishRequest:
    platforms: list[str]
    mode: str  # draft, scheduled, immediate
    scheduled_time: str | None = None
