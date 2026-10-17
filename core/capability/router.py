"""
Core Router Logic — prompts the reasoning model to generate the CapabilityPlan.
"""

import json
import logging

from core.capability.exceptions import RoutingError
from core.capability.models import CapabilityPlan
from core.capability.planner import CapabilityPlanner
from core.capability.registry import CapabilityRegistry
from core.model_router import ModelRouter

logger = logging.getLogger(__name__)


class CapabilityRouter:
    """Uses a reasoning model to decide which capabilities are required."""

    def __init__(self, model_router: ModelRouter, registry: CapabilityRegistry) -> None:
        self._router = model_router
        self._registry = registry
        self._planner = CapabilityPlanner()

    def route(self, user_input: str) -> CapabilityPlan:
        """Analyze the user request and generate a capability plan.
        
        Args:
            user_input: The user's request.
            
        Returns:
            The structured CapabilityPlan.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = f"User Request: {user_input}"
        
        try:
            response = self._router.generate(system_prompt, user_prompt)
            text = response.text
            
            # Parse JSON block
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            data = json.loads(text.strip())
            return self._planner.build_plan(data)
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse routing decision: %s", e)
            raise RoutingError(f"Router returned invalid JSON: {e}")

    def _build_system_prompt(self) -> str:
        """Construct the prompt using registered capabilities."""
        capabilities_info = []
        for cap in self._registry.list_all():
            capabilities_info.append(f"- {cap.name} ({cap.type.value}): {cap.description}")
            
        cap_str = "\n".join(capabilities_info)
        
        return f"""You are the Intelligent Capability Router for JARVIS AIOS.
Your job is NOT to execute the user's request.
Your job is strictly to DECIDE which capabilities and tools are required to fulfill the request.

Available Registered Capabilities:
{cap_str}

Output a strictly valid JSON object matching this schema:
{{
    "reasoning_model": "auto", // Or specific model name if requested
    "required_capabilities": ["list", "of", "capability", "names"],
    "required_tools": ["list", "of", "tool", "names"],
    "requires_planner": boolean, // True if the task needs multi-step planning
    "requires_memory": boolean, // True if it involves past conversations/facts
    "requires_workspace": boolean, // True if it involves local files or projects
    "requires_knowledge": boolean, // True if it involves system knowledge bases
    "requires_internet": boolean, // True if it needs to search the web
    "requires_automation": boolean, // True if it needs to execute external workflows (like n8n, youtube uploads, social media)
    "requires_scripting": boolean, // True if it asks to write/generate a production video script, documentary, story, or content template
    "requires_storyboard": boolean, // True if it asks to create a storyboard, shot list, or generate visual prompts from a script
    "requires_project_management": boolean, // True if it asks to manage a Project Bundle, open an episode, or reuse assets
    "requires_image_generation": boolean, // True if it asks to render, generate, or create physical images from a storyboard
    "requires_animation": boolean, // True if it asks to generate animations, animate images, or turn scenes into video
    "requires_voice": boolean, // True if it asks to generate voiceovers, narration, dialogue, or audio
    "requires_video": boolean, // True if it asks to assemble, render, compile, or export the final video
    "requires_music": boolean, // True if it asks to generate background music, ambient audio, or sound effects
    "requires_subtitles": boolean, // True if it asks to generate subtitles, SRT, or VTT files
    "requires_thumbnail": boolean, // True if it asks to generate click-optimized thumbnails
    "requires_seo": boolean, // True if it asks to generate SEO metadata, YouTube titles, tags, or descriptions
    "requires_publishing": boolean, // True if it asks to publish, upload, or post the project to a platform
    "requires_analytics": boolean, // True if it asks to track metrics, views, retention, or analytics
    "requires_agents": boolean, // True if it needs a specialized agent (e.g. coding)
    "requires_execution": boolean, // True if it actually executes tools
    "estimated_complexity": "low" | "medium" | "high",
    "estimated_cost": "low" | "medium" | "high",
    "estimated_latency": "low" | "medium" | "high",
    "confidence": 0.0 to 1.0,
    "style": "storytelling" // The content style if applicable: educational, storytelling, mythology, technology, motivational, explainer, podcast, tutorial, documentary. Default: storytelling.
}}

Rules:
1. If it is a simple conversational request ("Hello", "Who are you"), requires_execution is false and requires_planner is false.
2. If it is a direct simple command ("Open calculator", "Play music"), requires_execution is true, requires_planner is false.
3. ALL file system operations (creating, writing, reading, deleting files) MUST set requires_planner to true. If the prompt contains the word "file", requires_planner is ALWAYS true.
4. If it is complex ("Build a Discord bot"), requires_planner is true, requires_workspace is true, requires_agents is true.
5. If it requires remembering past context ("Continue yesterday's work", "What did I say"), requires_memory is true.
6. If the user asks to "find", "search", "locate", or implies they want to access personal knowledge or documents without specifying an exact path (e.g. "Where is my Aadhaar", "Show me Ramayana assets"), requires_knowledge is true.
7. If the user asks to trigger an external workflow, make a video, upload to YouTube/Instagram, run daily research, or sync data, requires_automation is true.
8. If the user asks to generate a script, documentary, story, or video content template, requires_scripting is true.
9. If the user asks to "storyboard" something, expand a script into shots, or generate image prompts for scenes, requires_storyboard is true.
10. If the user asks to open an episode, reuse an asset from a project, or manage Content Factory bundles, requires_project_management is true.
11. If the user asks to generate images from a storyboard or render visuals, requires_image_generation is true.
12. If the user asks to generate animations, animate images, or turn scenes into video, requires_animation is true.
13. If the user asks to generate voiceovers, narration, dialogue, or audio, requires_voice is true.
14. If the user asks to assemble, render, compile, or export the final video, requires_video is true.
15. If the user asks for post-production (music, subtitles, thumbnails, SEO, publishing, analytics), set the respective flags to true.
16. Do NOT include markdown blocks, only the raw JSON.
"""
