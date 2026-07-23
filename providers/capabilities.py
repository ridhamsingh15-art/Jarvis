"""
Capability definitions for the Model Router subsystem.
"""

from enum import Enum


class Capability(Enum):
    """Features that an AI provider can support.
    
    These are used by the Provider Registry to filter candidates for a given request.
    """
    CHAT = "chat"
    REASONING = "reasoning"
    VISION = "vision"
    AUDIO = "audio"
    EMBEDDINGS = "embeddings"
    IMAGE_GENERATION = "image_generation"
    TOOL_USE = "tool_use"
