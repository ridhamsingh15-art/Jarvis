"""
Planner — converts user intent into executable Task objects.

Owns the full chain: build prompt → call LLM → parse → normalize
→ create Tasks. This is where raw natural language becomes
structured, validated intent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from core.model_gateway import ModelGateway
from core.normalizer import normalize
from core.parser import parse_json
from core.registry import Registry
from core.task import Task

if TYPE_CHECKING:
    from core.identity.manager import IdentityManager

logger = logging.getLogger(__name__)




class Planner:
    """Converts natural language into a list of Task objects.

    Pipeline:
        1. Build system prompt from Registry descriptions
        2. Send to ModelGateway and get raw text
        3. Parse JSON from raw text
        4. Normalize aliases to canonical names
        5. Create Task objects
    """

    def __init__(
        self,
        gateway: ModelGateway,
        registry: Registry,
        identity: IdentityManager | None = None,
        model_selector: Any = None,
    ) -> None:
        self._gateway = gateway
        self._registry = registry
        self._identity = identity
        from core.routing.model_selector import TaskModelSelector
        self._model_selector = model_selector or TaskModelSelector()

    def plan(
        self,
        user_input: str,
        context: str = "",
        requirements: Any = None,
    ) -> list[Task]:
        """Convert user input into a list of Task objects.

        Args:
            user_input: Natural language instruction from the user.
            context: Optional conversation history for LLM context.
            requirements: Optional explicit InferenceRequirements.

        Returns:
            List of Task objects ready for validation and execution.

        Raises:
            RouterError: If the model gateway fails to generate a response.
            ParseError: If the LLM output cannot be parsed.
        """
        logger.info("Planning for: %s", user_input)

        system_prompt = self._build_system_prompt(context)
        reqs = requirements or self._model_selector.select_requirements(user_input)
        
        # Local models can emit malformed JSON or structurally invalid tool calls.
        # Permit one schema-correction retry; never normalize an invalid payload.
        # Provider/router errors are intentionally not retried here.
        from core.exceptions import ParseError

        last_error: Exception | None = None
        for attempt in range(2):
            attempt_prompt = system_prompt
            if attempt:
                attempt_prompt += (
                    "\n\nYour previous output failed the tool-call schema check: "
                    f"{type(last_error).__name__}: {last_error}. Return only a valid "
                    "JSON object or array. Each action must contain non-empty string "
                    "fields 'tool' and 'action' and an object field 'args'. Do not "
                    "include extra top-level action fields or markdown."
                )
            response = self._gateway.generate(
                attempt_prompt, user_input, requirements=reqs
            )
            raw_response = response.text
            logger.debug("Raw LLM response length: %d", len(raw_response))

            try:
                parsed = parse_json(raw_response)
                self._validate_action_schema(parsed)
                normalized = normalize(parsed)
                tasks = self._create_tasks(normalized)
                if not tasks:
                    raise ParseError("Planner returned an empty task list")
            except ParseError as exc:
                last_error = exc
                if attempt == 0:
                    logger.warning("Planner output failed parsing/schema validation; retrying once (%s)", type(exc).__name__)
                    continue
                raise ParseError("Planner output remained invalid after one schema-correction retry") from exc
            except (ValueError, TypeError, AttributeError) as exc:
                last_error = ParseError(f"Invalid action structure: {type(exc).__name__}")
                if attempt == 0:
                    logger.warning("Planner output had an invalid action structure; retrying once (%s)", type(exc).__name__)
                    continue
                raise ParseError("Planner output remained invalid after one schema-correction retry") from exc

            logger.info("Created %d task(s)", len(tasks))
            return tasks

        raise ParseError("Planner failed to produce a valid plan") from last_error

    @staticmethod
    def _validate_action_schema(parsed: Any) -> None:
        """Validate the external tool-call envelope before normalization."""
        from core.exceptions import ParseError

        actions = [parsed] if isinstance(parsed, dict) else parsed
        if not isinstance(actions, list) or not actions:
            raise ParseError("Planner output must be a non-empty action object or array")
        for index, item in enumerate(actions):
            if not isinstance(item, dict):
                raise ParseError(f"Action {index} must be a JSON object")
            unknown = set(item) - {"tool", "action", "args"}
            if unknown:
                raise ParseError(f"Action {index} has unsupported fields: {sorted(unknown)}")
            if not isinstance(item.get("tool"), str) or not item["tool"].strip():
                raise ParseError(f"Action {index} requires a non-empty string 'tool'")
            if not isinstance(item.get("action"), str) or not item["action"].strip():
                raise ParseError(f"Action {index} requires a non-empty string 'action'")
            if "args" in item and not isinstance(item["args"], dict):
                raise ParseError(f"Action {index} field 'args' must be a JSON object")
            args = item.get("args", {})
            if any(not isinstance(key, str) for key in args):
                raise ParseError(f"Action {index} argument names must be strings")

    def _build_system_prompt(self, context: str = "") -> str:
        """Build the system prompt dynamically from the Registry.

        If an IdentityManager is available, delegates prompt construction
        to the identity subsystem. Otherwise falls back to a minimal prompt.

        Args:
            context: Optional conversation history to include.

        Returns:
            Complete system prompt with tool descriptions and
            context injected.
        """
        tool_descriptions = self._registry.describe()

        if self._identity is not None:
            return self._identity.build_planner_prompt(tool_descriptions, context)

        # Fallback for when IdentityManager is not injected (e.g. tests)
        return f"""You are JARVIS, an AI operating system.

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