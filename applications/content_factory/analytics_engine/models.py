"""
Models for the Analytics Engine.
"""
from dataclasses import dataclass


@dataclass
class AnalyticsSyncRequest:
    platforms: list[str]
    days_since_publish: int
