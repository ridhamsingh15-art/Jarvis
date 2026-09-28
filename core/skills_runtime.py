"""
Skills Runtime Adapter — Phase I implementation.

Wires existing SkillManager into the live request routing pipeline.

Does NOT build a second skill framework. Uses SkillManager directly.

Progressive disclosure:
    1. metadata      — skill name, description, tags
    2. instructions  — SKILL.md content injected into context
    3. execution     — skill provides tool hints, not direct execution

Skills MUST pass ExecutionPolicy. They cannot gain unrestricted tool access.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.skills.manager import SkillManager
    from core.skills.models import Skill, SkillMatch
    from core.execution_policy import ExecutionPolicy, CapabilitySource, PolicyContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill context for injection into CognitiveManager
# ---------------------------------------------------------------------------


@dataclass
class SkillContext:
    """Structured representation of a skill for context injection."""
    skill_id: str
    name: str
    description: str
    tags: list[str]
    instructions: str = ""      # SKILL.md content (if loaded)
    tools_hint: list[str] = None  # Tools the skill may use

    def __post_init__(self):
        if self.tools_hint is None:
            self.tools_hint = []

    def to_context_block(self) -> str:
        """Format skill context for injection into the system/user prompt."""
        lines = [
            f"## Active Skill: {self.name}",
            f"Description: {self.description}",
        ]
        if self.tags:
            lines.append(f"Tags: {', '.join(self.tags)}")
        if self.instructions:
            lines.append(f"\nInstructions:\n{self.instructions}")
        if self.tools_hint:
            lines.append(f"Relevant tools: {', '.join(self.tools_hint)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# SkillsRuntime
# ---------------------------------------------------------------------------


class SkillsRuntime:
    """
    Adapter that bridges SkillManager into the live routing pipeline.

    Called from CognitiveManager.process_fast() to:
    1. Discover matching skills for the user request
    2. Return SkillContext blocks for prompt injection
    3. Enforce that skill tool access passes ExecutionPolicy

    Failure is isolated — if skill lookup fails, routing continues without skills.
    """

    def __init__(
        self,
        skill_manager: "SkillManager | None" = None,
        execution_policy: "ExecutionPolicy | None" = None,
        max_skills: int = 2,
    ) -> None:
        self._manager = skill_manager
        self._policy = execution_policy
        self._max_skills = max_skills

    def find_skills_for(self, user_input: str) -> list[SkillContext]:
        """
        Find skills relevant to the user request and return context blocks.

        Args:
            user_input: The user's message.

        Returns:
            List of SkillContext objects (up to max_skills), empty list on failure.
        """
        if self._manager is None:
            return []

        try:
            matches: list["SkillMatch"] = self._manager.match_skill(user_input)
            if not matches:
                return []

            # Take top-N matches
            top = matches[: self._max_skills]
            contexts = []
            for match in top:
                ctx = self._build_context(match.skill)
                if ctx is not None:
                    contexts.append(ctx)
                    logger.debug(
                        "[SKILLS] Matched skill '%s' (score=%.2f) for input: %s",
                        match.skill.name, getattr(match, "score", 0.0), user_input[:80],
                    )
            return contexts
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SKILLS] Skill lookup failed (isolated): %s", exc)
            return []

    def check_tool_permission(
        self,
        tool: str,
        action: str,
        skill_id: str,
    ) -> bool:
        """
        Check whether a skill is allowed to use the given tool/action.

        Skills are treated as an untrusted source (SKILL) and must pass
        ExecutionPolicy just like plugins and MCP servers.

        Returns:
            True if allowed, False otherwise.
        """
        if self._policy is None:
            return True  # No policy configured — allow (test/dev mode)

        from core.execution_policy import PolicyContext, CapabilitySource, PolicyVerdict
        ctx = PolicyContext(
            tool=tool,
            action=action,
            source=CapabilitySource.SKILL,
            source_id=skill_id,
        )
        result = self._policy.check(ctx)
        if result.verdict != PolicyVerdict.ALLOW:
            logger.warning(
                "[SKILLS] Skill '%s' denied access to %s.%s: %s",
                skill_id, tool, action, result.reason,
            )
            return False
        return True

    def format_context_for_prompt(self, skill_contexts: list[SkillContext]) -> str:
        """
        Format skill contexts into a single prompt block.

        Args:
            skill_contexts: List of SkillContext objects.

        Returns:
            Formatted string for injection into system/user prompt.
        """
        if not skill_contexts:
            return ""
        blocks = [ctx.to_context_block() for ctx in skill_contexts]
        return "\n\n--- ACTIVE SKILLS ---\n" + "\n\n".join(blocks) + "\n--- END SKILLS ---\n"

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_context(self, skill: "Skill") -> SkillContext | None:
        try:
            skill_id = getattr(skill.id, "value", str(skill.id))
            return SkillContext(
                skill_id=skill_id,
                name=skill.name,
                description=getattr(skill, "description", ""),
                tags=list(getattr(skill, "tags", []) or []),
                instructions=getattr(skill, "instructions", "") or "",
                tools_hint=list(getattr(skill, "tools", []) or []),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SKILLS] Failed to build context for skill: %s", exc)
            return None
