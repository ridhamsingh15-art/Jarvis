import logging
import uuid
from core.models.primitives import Identifier
from core.llm import LLMClient
from .models import CreatorObjective
from .exceptions import ObjectiveParsingError

logger = logging.getLogger(__name__)

class ObjectiveParser:
    """Parses high-level user goals into structured CreatorObjectives."""

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    def parse(self, raw_prompt: str) -> CreatorObjective:
        """
        Uses an LLM (or heuristics) to determine the target format and topic from the prompt.
        For this implementation, we use rule-based matching backed by LLM stubs.
        """
        prompt_lower = raw_prompt.lower()
        
        target_format = "video"
        if "short" in prompt_lower:
            target_format = "short"
        elif "documentary" in prompt_lower:
            target_format = "documentary"
        elif "tutorial" in prompt_lower:
            target_format = "tutorial"
            
        # Determine topic
        # e.g., "Create today's Ramayana episode" -> "Ramayana"
        topic = raw_prompt
        if "ramayana" in prompt_lower:
            topic = "Ramayana"
        elif "mythology" in prompt_lower:
            topic = "Mythology"
        elif "ai" in prompt_lower:
            topic = "AI"
        elif "coding" in prompt_lower or "programming" in prompt_lower:
            topic = "Programming"

        logger.info(f"Parsed objective: Format='{target_format}', Topic='{topic}'")

        # Determine capabilities
        # A standard video pipeline
        required_capabilities = [
            "web_search",
            "script_writing",
            "storyboarding",
            "image_generation",
            "animation",
            "voice_generation",
            "video_assembly",
            "publishing",
            "analytics"
        ]

        return CreatorObjective(
            id=Identifier(f"obj_{uuid.uuid4().hex[:8]}"),
            raw_prompt=raw_prompt,
            target_format=target_format,
            topic=topic,
            required_capabilities=required_capabilities
        )
