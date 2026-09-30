"""
Conversation Engine — LLM-driven orchestration for JARVIS.

Receives user input, builds prompts via IdentityManager, sends them
to the ModelRouter, parses the structured JSON response, and applies
identity guardrails before returning.

This module does NOT contain any persona, identity, or guardrail logic.
All identity concerns are delegated to the IdentityManager.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from core.cognition.context import ShortTermContext
from core.cognition.dialogue import DialogueState
from core.context_budget import ContextBudget, ContextBudgetManager, estimate_tokens
from core.identity.manager import IdentityManager
from core.model_router import ModelRouter
from core.registry import Registry

logger = logging.getLogger(__name__)


@dataclass
class ConversationResponse:
    """Structured response from the ConversationEngine."""

    type: str  # "RESPONSE", "ACTION", "PLAN", "CLARIFICATION"
    message: str  # The natural language reply to the user
    tool: str | None = None
    action: str | None = None
    parameters: dict[str, Any] | None = None
    reason: str | None = None


class ConversationEngine:
    """The central LLM-driven engine for JARVIS.

    Orchestrates the conversation loop:
        1. Build system prompt via IdentityManager
        2. Build user prompt from context
        3. Send to ModelRouter
        4. Parse structured JSON response
        5. Apply identity guardrails to the message
        6. Return ConversationResponse
    """

    def __init__(
        self,
        model_router: ModelRouter,
        registry: Registry,
        identity: IdentityManager,
        model_selector: Any = None,
    ) -> None:
        self._router = model_router
        self._registry = registry
        self._identity = identity
        from core.routing.model_selector import TaskModelSelector
        from core.context_budget import ContextBudget, ContextBudgetManager, estimate_tokens
        self._model_selector = model_selector or TaskModelSelector()
        self._budget_manager = ContextBudgetManager()
        self._last_budget: ContextBudget | None = None

    @property
    def last_context_budget(self) -> ContextBudget | None:
        """Return the ContextBudget report from the most recent process() call."""
        return self._last_budget

    def process(
        self,
        user_input: str,
        state: Any = None,
        context_package: Any = None,
        requirements: Any = None,
    ) -> ConversationResponse:
        """Process user input through the conversational pipeline.

        Args:
            user_input: The user's message.
            state: Current dialogue state (or context).
            context_package: ContextPackage or dialogue state.
            requirements: Optional explicit InferenceRequirements.

        Returns:
            A ConversationResponse with type, message, and optional tool/action info.
        """
        # Support calling as process(user_input, context, state) or process(user_input, state, context)
        if isinstance(context_package, DialogueState) and not isinstance(state, DialogueState):
            state, context_package = context_package, state
        if state is None:
            state = DialogueState()

        logger.info("ConversationEngine processing input...")

        # Ensure tools from registry are present in context_package if empty
        if context_package is not None and hasattr(context_package, "tool_state"):
            if not context_package.tool_state and self._registry:
                tool_desc = self._registry.describe()
                if tool_desc:
                    context_package.tool_state.append(tool_desc)

        system_prompt = self._identity.build_system_prompt(state, context_package)
        user_prompt = self._build_user_prompt(user_input, context_package)

        # Budget checking & Token estimation
        from core.context_budget import estimate_tokens
        est_sys = estimate_tokens(system_prompt)
        est_user = estimate_tokens(user_prompt)
        total_est = est_sys + est_user

        self._last_budget = ContextBudget(
            max_total_tokens=self._budget_manager.max_total_tokens,
            reserved_output_tokens=self._budget_manager.reserved_output_tokens,
            system_tokens=est_sys,
            user_input_tokens=est_user,
            history_tokens=estimate_tokens("\n".join(getattr(context_package, "recent_conversation", []))) if context_package else 0,
            memory_tokens=sum(estimate_tokens(m) for m in getattr(context_package, "memory_facts", [])) if context_package else 0,
            knowledge_tokens=sum(estimate_tokens(k) for k in getattr(context_package, "pki_knowledge", [])) if context_package else 0,
            mission_tokens=sum(estimate_tokens(m) for m in getattr(context_package, "mission_status", [])) if context_package else 0,
            tool_result_tokens=sum(estimate_tokens(t) for t in getattr(context_package, "tool_state", [])) if context_package else 0,
        )
        try:
            from core.runtime_trace import get_current_trace
            trace = get_current_trace()
            if trace is not None:
                trace.record_context_budget(self._last_budget)
        except Exception:
            pass

        # Determine optimal inference requirements for the task
        reqs = requirements or self._model_selector.select_requirements(user_input)
        if hasattr(reqs, "min_context_length"):
            req_ctx = reqs.min_context_length or 0
            if total_est + 512 > req_ctx:
                from providers.provider_models import InferenceRequirements
                reqs = InferenceRequirements(
                    capabilities=reqs.capabilities,
                    max_latency_ms=reqs.max_latency_ms,
                    max_cost_per_request=reqs.max_cost_per_request,
                    min_context_length=total_est + 512,
                    prefer_local=reqs.prefer_local,
                    prefer_provider=reqs.prefer_provider,
                    task_complexity=reqs.task_complexity,
                    prefer_model=reqs.prefer_model,
                    role=reqs.role,
                )

        try:
            response = self._router.generate(system_prompt, user_prompt, requirements=reqs)
            text = response.text if hasattr(response, "text") else str(response)

            # Extract JSON block if wrapped in markdown
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            cleaned_text = text.strip()
            
            # If the response is not valid JSON, check if it's plain text response
            if not cleaned_text.startswith("{") or not cleaned_text.endswith("}"):
                # Try finding JSON object within text
                first_brace = cleaned_text.find("{")
                last_brace = cleaned_text.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    cleaned_text = cleaned_text[first_brace : last_brace + 1]
                else:
                    # Plain text conversational fallback
                    safe_message = self._identity.apply_guardrails(cleaned_text)
                    return ConversationResponse(
                        type="RESPONSE",
                        message=safe_message,
                    )

            data = None
            # 1. Direct parse attempt
            try:
                data = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # 2. Attempt safe deterministic repairs
                repaired = cleaned_text
                # Remove trailing commas before closing braces/brackets
                repaired = re.sub(r",\s*([\]}])", r"\1", repaired)
                # Escape raw control characters inside strings
                repaired = re.sub(r'(?<!\\)\n', r'\\n', repaired)
                try:
                    data = json.loads(repaired)
                except json.JSONDecodeError:
                    data = None

            # 3. If parsing succeeded and is a valid dictionary
            if isinstance(data, dict):
                # Record state changes
                if data.get("pending_question"):
                    state.pending_question = data["pending_question"]
                else:
                    state.clear_pending()

                # Apply identity guardrails to the message
                raw_message = data.get("message", "I'm not sure how to respond to that.")
                safe_message = self._identity.apply_guardrails(str(raw_message))

                resp_type = str(data.get("type", "RESPONSE")).upper()
                if resp_type not in ["RESPONSE", "ACTION", "PLAN", "CLARIFICATION"]:
                    resp_type = "RESPONSE"

                # Extract tool, action, and parameters
                tool_val = data.get("tool")
                action_val = data.get("action")
                params_val = data.get("parameters", {})

                # Guard: system is an internal response/conclusion pseudo-tool, NEVER an external executable action
                if tool_val == "system":
                    resp_type = "RESPONSE"
                    if not raw_message or raw_message == "I'm not sure how to respond to that.":
                        raw_message = (
                            params_val.get("message")
                            or params_val.get("content")
                            or params_val.get("response")
                            or params_val.get("text")
                            or raw_message
                        )
                        safe_message = self._identity.apply_guardrails(str(raw_message))
                    tool_val = None
                    action_val = None
                    params_val = {}

                # Guard: ACTION must have both valid tool and action strings
                if resp_type == "ACTION":
                    if not isinstance(tool_val, str) or not isinstance(action_val, str) or not isinstance(params_val, dict):
                        logger.warning("Malformed ACTION payload in LLM output: tool=%s, action=%s. Falling back to RESPONSE.", tool_val, action_val)
                        resp_type = "RESPONSE"
                        tool_val = None
                        action_val = None
                        params_val = {}

                return ConversationResponse(
                    type=resp_type,
                    message=safe_message,
                    tool=tool_val if resp_type == "ACTION" else None,
                    action=action_val if resp_type == "ACTION" else None,
                    parameters=params_val if resp_type == "ACTION" else {},
                    reason=data.get("reason"),
                )

            # 4. Safe fallback for malformed JSON: Never execute a tool!
            logger.warning("ConversationEngine could not safely parse JSON from LLM output. Falling back to controlled safe response.")
            # Attempt to extract 'message' key if present
            msg_match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned_text)
            if msg_match:
                extracted_msg = msg_match.group(1).replace(r'\"', '"').replace(r'\n', '\n')
                safe_message = self._identity.apply_guardrails(extracted_msg)
                return ConversationResponse(
                    type="RESPONSE",
                    message=safe_message,
                )

            # If no message could be extracted, return controlled conversational failure
            return ConversationResponse(
                type="RESPONSE",
                message="I'm having trouble formatting my thoughts right now. Could you please rephrase?",
            )

        except Exception as e:
            logger.error("ConversationEngine failed to process: %s", e)
            return ConversationResponse(
                type="RESPONSE",
                message="I'm having trouble thinking clearly right now. Let's try that again.",
            )


    def _build_user_prompt(self, user_input: str, context_package: Any = None) -> str:
        """Build the user prompt."""
        history = ""
        if context_package is not None and hasattr(context_package, "recent_conversation"):
            if context_package.recent_conversation:
                history = "\n".join(context_package.recent_conversation)
        
        prompt = ""
        if history:
            prompt += f"# Recent Conversation\n{history}\n\n"
            
        prompt += f"# User's New Message\nUser: {user_input}\n"
        return prompt
