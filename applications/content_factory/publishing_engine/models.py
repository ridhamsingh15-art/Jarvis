"""
Models for the Publishing Engine.
"""
from dataclasses import dataclass


@dataclass
class PublishRequest:
    platforms: list[str]
    mode: str  # draft, scheduled, immediate
    scheduled_time: str | None = None
