"""
Data models for the Voice Integration.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


class ProviderType(StrEnum):
    ELEVENLABS = "elevenlabs"
    XTTS = "xtts"
    PIPER = "piper"


@dataclass(frozen=True, kw_only=True)
class VoiceRequest:
    """A request to generate voice audio."""
    text: str
    provider: ProviderType = ProviderType.ELEVENLABS
    voice_id: str = "default"
    language: str = "en"
    streaming: bool = False
    allow_fallback: bool = True


@dataclass(frozen=True, kw_only=True)
class VoiceResponse:
    """A response containing generated voice audio and metadata."""
    audio_data: bytes
    provider_used: ProviderType
    voice_id: str
    language: str
    generation_time: float = field(default_factory=time.time)
    duration_seconds: Optional[float] = None
