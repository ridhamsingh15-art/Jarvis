"""
Prompt builder — constructs system prompts from identity context.

Composes the identity statement, persona traits, behavioural rules,
model disclosure policy, and response schema into a complete system
prompt. This is the ONLY place where system prompts are assembled.
"""

from typing import Any

from core.cognition.dialogue import DialogueState
from core.cognition.context_models import ContextPackage
from core.identity.models import IdentityContext


class PromptBuilder:
    """Builds system prompts by composing identity context with runtime state.

    This class replaces the inline _build_system_prompt() methods that
    were previously scattered across ConversationEngine and Planner.
    """

    def __init__(self, identity_context: IdentityContext) -> None:
        self._context = identity_context

    def build_conversation_prompt(self, state: DialogueState, context_package: Any = None) -> str:
        """Build the full system prompt for the ConversationEngine."""
        identity = self._build_identity_section()
        behaviour = self._build_behaviour_section()
        disclosure = self._build_disclosure_section()
        dialogue = self._build_dialogue_section(state)
        instructions = self._build_instructions_section()
        schema = self._build_response_schema()

        context_sections = []
        if isinstance(context_package, str):
            if context_package.strip():
                context_sections.append(f"# Available Tools\n{context_package}")
        elif context_package is not None:
            if getattr(context_package, "identity_context", None):
                context_sections.append(f"# Identity Context\n{context_package.identity_context}")
            if getattr(context_package, "memory_facts", None):
                facts = "\n".join(f"- {f}" for f in context_package.memory_facts)
                context_sections.append(f"# Relevant User Facts\n{facts}")
            if getattr(context_package, "pki_knowledge", None):
                pki = "\n".join(f"- {p}" for p in context_package.pki_knowledge)
                context_sections.append(f"# PKI Results\n{pki}")
            if getattr(context_package, "active_projects", None):
                proj = "\n".join(f"- {p}" for p in context_package.active_projects)
                context_sections.append(f"# Active Projects\n{proj}")
            if getattr(context_package, "workspace_state", None):
                ws = "\n".join(f"- {w}" for w in context_package.workspace_state)
                context_sections.append(f"# Workspace State\n{ws}")
            if getattr(context_package, "mission_status", None):
                ms = "\n".join(f"- {m}" for m in context_package.mission_status)
                context_sections.append(f"# Mission Status\n{ms}")
            if getattr(context_package, "tool_state", None):
                tools = "\n".join(f"- {t}" for t in context_package.tool_state)
                context_sections.append(f"# Available Tools\n{tools}")

        context_str = "\n\n".join(context_sections)
        context_block = f"{context_str}\n\n" if context_str else ""

        return (
            f"{identity}\n\n{behaviour}\n\n{disclosure}\n\n"
            f"{context_block}"
            f"{dialogue}\n\n{instructions}\n\n{schema}"
        )


    def build_planner_prompt(self, tool_descriptions: str, context: str) -> str:
        """Build the system prompt for the Planner.

        Args:
            tool_descriptions: Formatted tool descriptions from Registry.
            context: Optional conversation history.

        Returns:
            Complete system prompt string for planning.
        """
        return f"""{self._context.identity_statement}

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

    def _build_identity_section(self) -> str:
        """Build the identity and persona section."""
        traits_text = ", ".join(t.name for t in self._context.traits)
        return f"""{self._context.identity_statement}

Your core traits: {traits_text}."""

    def _build_behaviour_section(self) -> str:
        """Build the behavioural rules section."""
        rules_text = "\n".join(
            f"- {rule.rule}" for rule in self._context.rules
        )
        return f"""# Behavioural Rules
{rules_text}"""

    def _build_disclosure_section(self) -> str:
        """Build the model disclosure policy section."""
        return f"""# Model Disclosure
- Your current reasoning engine is: {self._context.active_model} (via {self._context.active_provider}).
- When asked "which model are you using?", answer honestly with the above.
- When asked "which model do you prefer?", explain that you select the most appropriate reasoning engine based on the task — not personal preference.
- You are JARVIS. The model is your internal engine, not your identity."""

    def _build_tools_section(self, tools_info: str) -> str:
        """Build the available tools section."""
        return f"""# Available Tools
{tools_info}"""

    def _build_dialogue_section(self, state: Any = None) -> str:
        """Build the current dialogue state section."""
        pending = getattr(state, "pending_question", None) or "None"
        last_tool = getattr(state, "last_tool_invoked", None) or "None"
        return f"""# Current Dialogue State
- Pending Question (you asked this last): {pending}
- Last Tool Invoked: {last_tool}"""

    def _build_instructions_section(self) -> str:
        """Build the orchestration instructions section."""
        return """# Instructions
1. Read the user's message, dialogue history, and available tools.
2. If the user is greeting you, having a conversation, or asking a question, select type "RESPONSE" and provide a helpful, natural response in "message".
3. If the user is requesting an action achievable with one of the available tools, select type "ACTION", specifying "tool", "action", and valid "parameters".
4. If the user's request is ambiguous or missing critical details needed to safely proceed, select type "CLARIFICATION" and ask the clarifying question in "message".
5. If the user's request is a large, complex multi-stage project or mission (e.g. build an entire documentary, build and launch a SaaS, multi-step code generation), select type "PLAN" so the executive planning engine can orchestrate it."""

    def _build_response_schema(self) -> str:
        """Build the response JSON schema section."""
        return """You MUST respond with a raw JSON object (do not wrap in markdown) matching this schema:
{
    "type": "RESPONSE" | "ACTION" | "PLAN" | "CLARIFICATION",
    "message": "Your natural language response to the user. Always include this.",
    "tool": "tool_name_if_action",
    "action": "action_name_if_action",
    "parameters": {"param1": "value1"},
    "reason": "Brief internal reason for your decision.",
    "pending_question": "If you are asking the user a question, store the internal variable name here (e.g. 'user_name'). Otherwise null."
}"""
