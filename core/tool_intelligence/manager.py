import logging
import re
from typing import Any

from core.events.bus import EventBus
from core.exceptions import JarvisError
from core.registry import Registry
from core.task import Task
from core.tool_intelligence.argument_mapper import ArgumentMapper
from core.tool_intelligence.repair import PayloadRepairer
from core.tool_intelligence.resolver import ToolResolver
from core.tool_intelligence.schema_resolver import SchemaResolver
from core.tool_intelligence.telemetry import IntelligenceTelemetry
from core.tool_intelligence.validator import IntelligenceValidator
from core.validator import Validator

logger = logging.getLogger(__name__)


class ToolIntelligenceManager:
    """Intercepts, repairs, and validates LLM payloads before execution."""

    def __init__(self, registry: Registry, core_validator: Validator, event_bus: EventBus) -> None:
        self._resolver = ToolResolver()
        self._schema_resolver = SchemaResolver(registry)
        self._argument_mapper = ArgumentMapper()
        
        self._repairer = PayloadRepairer(
            self._resolver, 
            self._schema_resolver, 
            self._argument_mapper
        )
        
        self._intelligence_validator = IntelligenceValidator(core_validator)
        self._telemetry = IntelligenceTelemetry(event_bus)

    def process(self, task: Task) -> Task:
        """Process a task through the intelligence pipeline.
        
        This will attempt to repair the task payload. If it repairs successfully
        and passes the strict validator, the repaired task is returned. If it
        fails validation, a JarvisError is raised (just like the original Validator).

        Args:
            task: The raw Task to process.

        Returns:
            The safely validated (and potentially repaired) Task.

        Raises:
            JarvisError: If the task fails strict validation after repair attempts.
        """
        # Save original state for telemetry
        orig_tool = task.tool
        orig_action = task.action
        orig_args = dict(task.args)

        # 1. Attempt to Repair
        repaired_task, metrics = self._repairer.repair(task)

        # 2. Strict Validation
        outcome = self._intelligence_validator.validate(repaired_task, metrics)

        # 3. Publish Telemetry
        self._telemetry.publish_outcome(outcome, orig_tool, orig_action, orig_args)

        # 4. Result evaluation
        if outcome.is_valid:
            if outcome.metrics.was_repaired:
                logger.info(
                    "Intelligently repaired payload for %s.%s", 
                    outcome.task.tool, outcome.task.action
                )
            return outcome.task
        else:
            logger.warning(
                "Payload failed intelligence validation: %s", 
                outcome.error_message
            )
            # Re-raise to maintain original contract
            raise JarvisError(outcome.error_message or "Validation failed")

    def resolve_from_registry(self, user_input: str) -> tuple[str, str, dict] | None:
        """Attempt to resolve a TOOL request directly from registry metadata.

        Inspects registered tool names and their action keywords against the
        user input. Falls back to None if no high-confidence match is found,
        at which point the caller should use the LLM path.

        Args:
            user_input: Raw user input string.

        Returns:
            (tool_name, action_name, args) if matched, else None.
        """
        lower = user_input.lower().strip()
        registry = self._schema_resolver._registry  # access via SchemaResolver

        for tool_name in registry.list_tools():
            tool = registry.get(tool_name)
            if tool is None:
                continue
            # Check if tool name appears in the input
            if tool_name in lower:
                action_defs = tool.get_actions()
                actions = list(action_defs.keys())
                if actions:
                    matched_action = None
                    for action in actions:
                        if action.replace("_", " ") in lower or action in lower:
                            matched_action = action
                            break
                    if matched_action is None:
                        continue

                    action_def = action_defs[matched_action]
                    args: dict[str, Any] = {}

                    # Extract path if needed
                    path_match = re.search(r"['\"]([A-Za-z]:[\\/][^'\"]+)['\"]", user_input) or re.search(r"(?:at|to|from|in)\s+['\"]?([A-Za-z]:[\\/][^\s'\"]+)['\"]?", user_input, re.IGNORECASE)
                    if path_match:
                        args["path"] = path_match.group(1).rstrip("'\"")

                    # Extract content/text if needed
                    content_match = re.search(r"(?:containing|content|with content|with exact content)\s+(?:exactly\s+)?['\"]([^'\"]+)['\"]", user_input, re.IGNORECASE)
                    if content_match:
                        expected = action_def.required_args + getattr(action_def, "optional_args", [])
                        if "text" in expected:
                            args["text"] = content_match.group(1)
                        elif "content" in expected:
                            args["content"] = content_match.group(1)

                    # Only claim resolution if all required arguments are satisfied
                    if all(req in args for req in action_def.required_args):
                        logger.info(
                            "Registry-driven resolution: %s.%s with args %s for input '%s'",
                            tool_name, matched_action, args, user_input[:60]
                        )
                        return tool_name, matched_action, args
        return None
