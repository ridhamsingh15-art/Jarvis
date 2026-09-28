"""
Models for the Analytics Engine.
"""
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class AnalyticsSyncRequest:
    platforms: list[str]
    days_since_publish: int
