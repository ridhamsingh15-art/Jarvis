"""
Planner — converts user intent into executable Task objects.

Owns the full chain: build prompt → call LLM → parse → normalize
→ create Tasks. This is where raw natural language becomes
structured, validated intent.
"""

import logging

from core.model_gateway import ModelGateway
from core.normalizer import normalize
from core.parser import parse_json
from core.registry import Registry
from core.task import Task

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """You are Jarvis, an AI operating system.

You must ONLY use the tools listed below.
Return ONLY valid JSON — no explanation, no markdown, no code fences.

For a single action return a JSON object:
{{"tool": "", "action": "", "args": {{}}}}

For multiple actions return a JSON array:
[{{"tool": "", "action": "", "args": {{}}}}]

If the user is greeting you, asking a question, or making conversation
(not requesting a specific tool action), respond with:
{{"tool": "system", "action": "respond", "args": {{"message": "your response here"}}}}

Available tools:

{tool_descriptions}

{context}"""


class Planner:
    """Converts natural language into a list of Task objects.

    Pipeline:
        1. Build system prompt from Registry descriptions
        2. Send to ModelGateway and get raw text
        3. Parse JSON from raw text
        4. Normalize aliases to canonical names
        5. Create Task objects
    """

    def __init__(self, gateway: ModelGateway, registry: Registry) -> None:
        self._gateway = gateway
        self._registry = registry

    def plan(self, user_input: str, context: str = "") -> list[Task]:
        """Convert user input into a list of Task objects.

        Args:
            user_input: Natural language instruction from the user.
            context: Optional conversation history for LLM context.

        Returns:
            List of Task objects ready for validation and execution.

        Raises:
            RouterError: If the model gateway fails to generate a response.
            ParseError: If the LLM output cannot be parsed.
        """
        logger.info("Planning for: %s", user_input)

        system_prompt = self._build_system_prompt(context)
        
        # Use Gateway for text generation
        response = self._gateway.generate(system_prompt, user_input)
        raw_response = response.text

        logger.debug("Raw LLM response: %s", raw_response[:300])

        parsed = parse_json(raw_response)
        normalized = normalize(parsed)
        tasks = self._create_tasks(normalized)

        logger.info("Created %d task(s)", len(tasks))

        return tasks

    def _build_system_prompt(self, context: str = "") -> str:
        """Build the system prompt dynamically from the Registry.

        Args:
            context: Optional conversation history to include.

        Returns:
            Complete system prompt with tool descriptions and
            context injected.
        """
        tool_descriptions = self._registry.describe()

        return _SYSTEM_PROMPT_TEMPLATE.format(
            tool_descriptions=tool_descriptions,
            context=context,
        )

    @staticmethod
    def _create_tasks(normalized: list[dict]) -> list[Task]:
        """Convert normalized dicts into Task objects.

        Args:
            normalized: List of normalized action dicts.

        Returns:
            List of Task instances in PENDING state.
        """
        return [
            Task(
                tool=item.get("tool", ""),
                action=item.get("action", ""),
                args=item.get("args", {}),
            )
            for item in normalized
        ]