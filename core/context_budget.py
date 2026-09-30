"""
Deterministic Context Budgeting and Truncation Control for JARVIS AIOS.

Provides token estimation, hard budget boundaries, deterministic component
prioritization, and tool result protection before every LLM invocation.

Security Invariants Enforced:
- MODEL CLAIMS != PROOF
- MODEL != AUTHORIZATION
- TOOL RESULT != INSTRUCTIONS
- Security instructions and untrusted boundaries are NEVER stripped.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from core.task import Task, TaskStatus

logger = logging.getLogger(__name__)

# Default token and character limits
DEFAULT_MAX_CONTEXT_TOKENS = 4096
DEFAULT_RESERVED_OUTPUT_TOKENS = 512
DEFAULT_MAX_TOOL_RESULT_CHARS = 1500
DEFAULT_TOTAL_TOOL_RESULT_CHARS = 3000
DEFAULT_MAX_HISTORY_TOKENS = 600
DEFAULT_MAX_MEMORY_TOKENS = 300
DEFAULT_MAX_KNOWLEDGE_TOKENS = 500


def estimate_tokens(text: str) -> int:
    """Deterministic token estimation without an LLM call.

    Conservative estimation:
    - Typical English/code average ~3.5 to 4 characters per token.
    - Uses max((len(text) + 3) // 4, int(len(text.split()) * 1.3)).
    - Returns 0 for empty/whitespace string, at least 1 for non-empty text.
    """
    if not text or not text.strip():
        return 0
    char_est = (len(text) + 3) // 4
    word_est = int(len(text.split()) * 1.3)
    return max(char_est, word_est, 1)


@dataclass
class ContextBudget:
    """Immutable or observable record of context budgeting for an LLM call."""

    max_total_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    reserved_output_tokens: int = DEFAULT_RESERVED_OUTPUT_TOKENS

    system_tokens: int = 0
    user_input_tokens: int = 0
    tool_result_tokens: int = 0
    history_tokens: int = 0
    memory_tokens: int = 0
    knowledge_tokens: int = 0
    mission_tokens: int = 0
    other_tokens: int = 0

    truncated: bool = False
    truncation_reason: str = ""
    dropped_components: list[str] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return (
            self.system_tokens
            + self.user_input_tokens
            + self.tool_result_tokens
            + self.history_tokens
            + self.memory_tokens
            + self.knowledge_tokens
            + self.mission_tokens
            + self.other_tokens
        )

    @property
    def max_input_budget(self) -> int:
        return max(0, self.max_total_tokens - self.reserved_output_tokens)

    @property
    def remaining_budget(self) -> int:
        return max(0, self.max_input_budget - self.total_input_tokens)

    @property
    def is_over_budget(self) -> bool:
        return self.total_input_tokens > self.max_input_budget

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_total_tokens": self.max_total_tokens,
            "reserved_output_tokens": self.reserved_output_tokens,
            "max_input_budget": self.max_input_budget,
            "total_input_tokens": self.total_input_tokens,
            "remaining_budget": self.remaining_budget,
            "system_tokens": self.system_tokens,
            "user_input_tokens": self.user_input_tokens,
            "tool_result_tokens": self.tool_result_tokens,
            "history_tokens": self.history_tokens,
            "memory_tokens": self.memory_tokens,
            "knowledge_tokens": self.knowledge_tokens,
            "mission_tokens": self.mission_tokens,
            "other_tokens": self.other_tokens,
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
            "dropped_components": list(self.dropped_components),
        }


class ContextBudgetManager:
    """Enforces deterministic context limits, tool result bounding, and component priority."""

    def __init__(
        self,
        max_total_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        reserved_output_tokens: int = DEFAULT_RESERVED_OUTPUT_TOKENS,
        max_tool_result_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS,
        total_tool_result_chars: int = DEFAULT_TOTAL_TOOL_RESULT_CHARS,
    ):
        self.max_total_tokens = max_total_tokens
        self.reserved_output_tokens = reserved_output_tokens
        self.max_tool_result_chars = max_tool_result_chars
        self.total_tool_result_chars = total_tool_result_chars

    # -----------------------------------------------------------------------
    # Tool Result Bounding
    # -----------------------------------------------------------------------

    def format_bounded_tool_result(
        self,
        task: Task,
        max_chars: int | None = None,
    ) -> str:
        """Format a single task result as strictly bounded UNTRUSTED DATA.

        Preserves:
        - <UNTRUSTED_TOOL_RESULT>...</UNTRUSTED_TOOL_RESULT> boundaries
        - tool and action name
        - status (SUCCESS / FAILURE)
        - useful output prefix and suffix while bounding large content
        """
        limit = max_chars or self.max_tool_result_chars
        raw_val = task.result if task.status == TaskStatus.COMPLETED else task.error
        content = str(raw_val if raw_val is not None else "")

        # Strip ANSI escape sequences
        clean = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", content)

        if len(clean) > limit:
            head_len = int(limit * 0.75)
            tail_len = max(0, limit - head_len - 60)
            dropped = len(clean) - head_len - tail_len
            if tail_len > 0:
                clean = (
                    clean[:head_len]
                    + f"\n... [truncated {dropped} chars to fit context budget] ...\n"
                    + clean[-tail_len:]
                )
            else:
                clean = clean[:head_len] + f"\n... [truncated {dropped} chars to fit context budget]"

        status_str = "SUCCESS" if task.status == TaskStatus.COMPLETED else "FAILURE"
        return (
            f"<UNTRUSTED_TOOL_RESULT>\n"
            f"tool: {task.tool}.{task.action}\n"
            f"status: {status_str}\n"
            f"output: {clean}\n"
            f"</UNTRUSTED_TOOL_RESULT>"
        )

    def bound_tool_results_list(
        self,
        tasks: list[Task],
        max_total_chars: int | None = None,
    ) -> tuple[str, bool]:
        """Bound multiple tool results within total tool budget, keeping latest results first."""
        if not tasks:
            return "", False

        total_limit = max_total_chars or self.total_tool_result_chars
        per_result_limit = min(self.max_tool_result_chars, total_limit)

        formatted_results: list[str] = []
        truncated = False

        # Work newest to oldest to prioritize recent results
        current_chars = 0
        kept: list[str] = []
        for task in reversed(tasks):
            entry = self.format_bounded_tool_result(task, max_chars=per_result_limit)
            entry_len = len(entry)
            if current_chars + entry_len <= total_limit or not kept:
                kept.append(entry)
                current_chars += entry_len
            else:
                truncated = True

        # Restore chronological order
        kept.reverse()
        return "\n\n".join(kept), truncated

    # -----------------------------------------------------------------------
    # Feedback Prompt Trimming
    # -----------------------------------------------------------------------

    def fit_feedback_prompt(
        self,
        user_input: str,
        history_summary: str,
        untrusted_obs: str,
        security_instruction: str,
        decision_instruction: str,
        iteration: int,
        max_iterations: int,
    ) -> tuple[str, ContextBudget]:
        """Deterministically fit feedback loop observation prompt within budget.

        Priority Order:
        1. Current user request (NEVER dropped)
        2. Required security instructions (NEVER dropped)
        3. Decision instruction (NEVER dropped)
        4. Untrusted observation (bounded)
        5. Execution history summary (compacted/trimmed if needed)
        """
        budget = ContextBudget(
            max_total_tokens=self.max_total_tokens,
            reserved_output_tokens=self.reserved_output_tokens,
        )

        user_block = f"Original user request: '{user_input}'\n\n"
        budget.user_input_tokens = estimate_tokens(user_block)

        sec_block = f"{security_instruction}\n\n{decision_instruction}"
        budget.system_tokens = estimate_tokens(sec_block)

        # Enforce bounds on observation block
        obs_header = f"Latest tool execution result (Iteration {iteration}/{max_iterations}):\n"
        obs_content = f"{obs_header}{untrusted_obs}\n\n"
        budget.tool_result_tokens = estimate_tokens(obs_content)

        # History summary is lower priority than latest tool result
        hist_header = "Execution history:\n"
        hist_body = history_summary.strip()
        hist_content = f"{hist_header}{hist_body}\n\n" if hist_body else ""
        budget.history_tokens = estimate_tokens(hist_content)

        # Check total
        max_allowed = budget.max_input_budget
        current_total = budget.total_input_tokens

        if current_total > max_allowed:
            budget.truncated = True
            overflow = current_total - max_allowed

            # Step 1: Trim execution history first
            if budget.history_tokens > 0:
                hist_tokens = budget.history_tokens
                if hist_tokens <= overflow:
                    hist_content = "[Execution history trimmed to fit budget]\n\n"
                    overflow -= (hist_tokens - estimate_tokens(hist_content))
                    budget.history_tokens = estimate_tokens(hist_content)
                    budget.dropped_components.append("execution_history")
                else:
                    # Truncate lines from beginning of history
                    lines = hist_body.splitlines()
                    while lines and overflow > 0:
                        dropped_line = lines.pop(0)
                        overflow -= estimate_tokens(dropped_line)
                    hist_content = f"{hist_header}... [earlier tasks omitted]\n" + "\n".join(lines) + "\n\n"
                    budget.history_tokens = estimate_tokens(hist_content)
                    budget.dropped_components.append("earlier_execution_history")

            # Step 2: If still over budget, bound the untrusted observation further
            if overflow > 0 and budget.tool_result_tokens > 200:
                avail_tokens = max(100, budget.tool_result_tokens - overflow)
                max_chars = avail_tokens * 3
                if len(untrusted_obs) > max_chars:
                    # Preserve untrusted XML tags
                    inner = untrusted_obs
                    prefix = "<UNTRUSTED_TOOL_RESULT>\n"
                    suffix = "\n</UNTRUSTED_TOOL_RESULT>"
                    if prefix in inner and suffix in inner:
                        body = inner.split(prefix, 1)[1].rsplit(suffix, 1)[0]
                        body = body[:max_chars] + f"\n... [tool result truncated to fit budget]"
                        untrusted_obs = f"{prefix}{body}{suffix}"
                    else:
                        untrusted_obs = untrusted_obs[:max_chars] + "\n... [truncated]"
                    obs_content = f"{obs_header}{untrusted_obs}\n\n"
                    budget.tool_result_tokens = estimate_tokens(obs_content)
                    budget.dropped_components.append("tool_observation_tail")

            budget.truncation_reason = f"Context exceeded {max_allowed} tokens; trimmed lower-priority history/tool components."

        full_prompt = (
            f"{user_block}"
            f"{hist_content}"
            f"{obs_content}"
            f"{sec_block}"
        )
        return full_prompt, budget

    # -----------------------------------------------------------------------
    # ContextPackage Component Budgeting
    # -----------------------------------------------------------------------

    def budget_context_package(
        self,
        package: Any,
        user_input: str,
        dialogue_state: Any = None,
        max_history_tokens: int = DEFAULT_MAX_HISTORY_TOKENS,
        max_memory_tokens: int = DEFAULT_MAX_MEMORY_TOKENS,
        max_knowledge_tokens: int = DEFAULT_MAX_KNOWLEDGE_TOKENS,
    ) -> ContextBudget:
        """Enforce deterministic token budgets across ContextPackage components."""
        budget = ContextBudget(
            max_total_tokens=self.max_total_tokens,
            reserved_output_tokens=self.reserved_output_tokens,
        )
        budget.user_input_tokens = estimate_tokens(user_input)

        if package is None:
            return budget

        # 1. Budget Knowledge (PKI) - Lowest priority
        pki_list = getattr(package, "pki_knowledge", [])
        if pki_list:
            total_k = 0
            kept_k = []
            for item in pki_list:
                t = estimate_tokens(item)
                if total_k + t <= max_knowledge_tokens:
                    kept_k.append(item)
                    total_k += t
                else:
                    budget.truncated = True
                    budget.dropped_components.append("pki_knowledge")
            package.pki_knowledge = kept_k
            budget.knowledge_tokens = total_k

        # 2. Budget Memory Facts
        mem_list = getattr(package, "memory_facts", [])
        if mem_list:
            total_m = 0
            kept_m = []
            for item in mem_list:
                t = estimate_tokens(item)
                if total_m + t <= max_memory_tokens:
                    kept_m.append(item)
                    total_m += t
                else:
                    budget.truncated = True
                    budget.dropped_components.append("memory_facts")
            package.memory_facts = kept_m
            budget.memory_tokens = total_m

        # 3. Budget Recent Conversation History (Newest first, then re-chronologize)
        conv_list = getattr(package, "recent_conversation", [])
        if conv_list:
            total_h = 0
            kept_h = []
            for item in reversed(conv_list):
                t = estimate_tokens(item)
                if total_h + t <= max_history_tokens:
                    kept_h.append(item)
                    total_h += t
                else:
                    budget.truncated = True
                    budget.dropped_components.append("older_conversation")
            kept_h.reverse()
            package.recent_conversation = kept_h
            budget.history_tokens = total_h

        # 4. Mission & Tool state
        ms_list = getattr(package, "mission_status", [])
        budget.mission_tokens = sum(estimate_tokens(m) for m in ms_list)

        ts_list = getattr(package, "tool_state", [])
        budget.other_tokens = sum(estimate_tokens(t) for t in ts_list)

        return budget
