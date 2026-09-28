"""
Execution Summary & Result Grounding — Phase 6 implementation.

Implements the deterministic result grounding contract:
    EXECUTION FACTS > MODEL CLAIMS

Aggregates tool execution facts, isolates them from model claims or hallucinations,
and synthesizes authoritative natural-language conclusions grounded purely
in verified execution realities.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from core.task import Task, TaskStatus

logger = logging.getLogger(__name__)

# Pattern to detect when a model falsely claims failure
_FAILURE_CLAIM_PATTERN = re.compile(
    r"\b(could\s+not|couldn\'t|failed\s+to|unable\s+to|cannot|can\'t|error|was\s+not\s+able)\b",
    re.IGNORECASE,
)

# Pattern to detect when a model falsely claims success
_SUCCESS_CLAIM_PATTERN = re.compile(
    r"\b(done|created|written|fixed|opened|completed|success|successfully|here\s+is\s+the|has\s+been)\b",
    re.IGNORECASE,
)


def _sanitize_output(val: Any, max_len: int = 300) -> str:
    """Sanitize and safely truncate tool outputs to prevent injection attacks."""
    if val is None:
        return ""
    text = str(val).strip()
    # Normalize newlines
    text = re.sub(r"[\r\n]+", " ", text)
    # Strip any terminal escape sequences
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    if len(text) > max_len:
        text = text[:max_len] + "... [truncated]"
    return text


@dataclass(frozen=True)
class TaskExecutionRecord:
    """Immutable record of an individual tool task's execution reality."""

    task_id: int
    tool: str
    action: str
    status: TaskStatus
    result: Any | None = None
    error: str | None = None
    args: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def failed(self) -> bool:
        return self.status == TaskStatus.FAILED

    @property
    def skipped(self) -> bool:
        return self.status in (TaskStatus.PENDING, TaskStatus.RETRYING)


@dataclass
class ExecutionSummary:
    """Authoritative aggregation of execution facts for a set of tasks."""

    records: list[TaskExecutionRecord] = field(default_factory=list)
    completed: list[TaskExecutionRecord] = field(default_factory=list)
    failed: list[TaskExecutionRecord] = field(default_factory=list)
    skipped: list[TaskExecutionRecord] = field(default_factory=list)
    total_tasks: int = 0
    all_succeeded: bool = False
    all_failed: bool = False
    is_partial: bool = False
    verification_passed: bool | None = None
    verification_details: list[str] = field(default_factory=list)

    @classmethod
    def from_tasks(
        cls,
        tasks: list[Task],
        verification_result: Any | None = None,
    ) -> ExecutionSummary:
        """Construct an ExecutionSummary from a list of executed tasks.

        Filters out internal system pseudo-tasks so only true OS/external
        capabilities form the factual basis.
        """
        exec_tasks = [t for t in tasks if t.tool != "system"]
        records = [
            TaskExecutionRecord(
                task_id=id(t),
                tool=t.tool,
                action=t.action,
                status=t.status,
                result=t.result,
                error=t.error,
                args=dict(t.args) if t.args else {},
            )
            for t in exec_tasks
        ]

        completed = [r for r in records if r.succeeded]
        failed = [r for r in records if r.failed]
        skipped = [r for r in records if r.skipped]

        total = len(records)
        all_succeeded = total > 0 and len(completed) == total
        all_failed = total > 0 and len(failed) == total
        is_partial = total > 1 and len(completed) > 0 and (len(failed) > 0 or len(skipped) > 0)

        v_passed = None
        v_details = []
        if verification_result is not None:
            v_passed = getattr(verification_result, "succeeded", False)
            v_details = getattr(verification_result, "details", [])

        return cls(
            records=records,
            completed=completed,
            failed=failed,
            skipped=skipped,
            total_tasks=total,
            all_succeeded=all_succeeded,
            all_failed=all_failed,
            is_partial=is_partial,
            verification_passed=v_passed,
            verification_details=v_details,
        )

    def ground_response(self, initial_claim: str = "") -> str:
        """Synthesize an authoritative, grounded response from execution facts.

        Enforces: EXECUTION FACTS > MODEL CLAIMS.
        """
        # 1. No tool actions executed (pure conversational message)
        if self.total_tasks == 0:
            return initial_claim.strip() if initial_claim else "Done."

        # 2. Check mission verification override if verification failed explicitly
        if self.verification_passed is False:
            details_str = "; ".join(self.verification_details) if self.verification_details else "Verification checks failed"
            return f"Action was attempted, but mission verification failed: {details_str}."

        # 3. All tools succeeded
        if self.all_succeeded:
            return self._build_success_response(initial_claim)

        # 4. All tools failed
        if self.all_failed:
            return self._build_failure_response(initial_claim)

        # 5. Partial execution (some succeeded, some failed or skipped)
        return self._build_partial_response(initial_claim)

    def _build_success_response(self, initial_claim: str) -> str:
        """Build response when all tools succeeded."""
        # Detect multi-tool combo: create/write file + read/open file
        create_rec = next(
            (r for r in self.completed if r.tool == "file" and r.action in ("create_file", "write_file")),
            None,
        )
        read_rec = next(
            (r for r in self.completed if r.tool == "file" and r.action in ("read_file", "open_file")),
            None,
        )

        if create_rec and read_rec and len(self.completed) == 2:
            path = create_rec.args.get("path") or read_rec.args.get("path") or "file"
            read_out = _sanitize_output(read_rec.result)
            if read_out and not read_out.startswith("Opened '"):
                return f"Done — created {path} and read it back. Content: '{read_out}'."
            return f"Done — created {path} and opened it successfully."

        # Single task success
        if len(self.completed) == 1:
            rec = self.completed[0]
            return self._format_single_success(rec)

        # Multi-task general success
        items = [self._format_task_summary(r) for r in self.completed]
        return "Done — completed all actions:\n" + "\n".join(f"- {it}" for it in items)

    def _build_failure_response(self, initial_claim: str) -> str:
        """Build response when all tools failed (model claims of success are discarded)."""
        if len(self.failed) == 1:
            rec = self.failed[0]
            err = rec.error or "an error occurred"
            target = rec.args.get("path") or rec.args.get("filepath") or rec.args.get("app")
            target_str = f" on '{target}'" if target else ""
            return f"I couldn't complete {rec.tool}.{rec.action}{target_str}: {err}"

        items = []
        for r in self.failed:
            target = r.args.get("path") or r.args.get("filepath") or r.args.get("app")
            target_str = f" on '{target}'" if target else ""
            items.append(f"{r.tool}.{r.action}{target_str}: {r.error or 'Failed'}")
        return "I couldn't complete the requested actions:\n" + "\n".join(f"- {it}" for it in items)

    def _build_partial_response(self, initial_claim: str) -> str:
        """Build response for partial multi-tool execution."""
        lines = ["Partially completed:"]
        if self.completed:
            succeeded_str = ", ".join(self._format_task_summary(r) for r in self.completed)
            lines.append(f"Completed: {succeeded_str}")
        if self.failed:
            failed_items = []
            for r in self.failed:
                target = r.args.get("path") or r.args.get("filepath") or r.args.get("app")
                target_str = f" on '{target}'" if target else ""
                failed_items.append(f"{r.tool}.{r.action}{target_str} ({r.error or 'Failed'})")
            lines.append(f"Failed: {', '.join(failed_items)}")
        if self.skipped:
            skipped_str = ", ".join(f"{r.tool}.{r.action}" for r in self.skipped)
            lines.append(f"Not executed: {skipped_str}")
        return "\n".join(lines)

    @staticmethod
    def _format_single_success(rec: TaskExecutionRecord) -> str:
        """Format a single successful action into concise, grounded language."""
        tool = rec.tool
        action = rec.action
        path = rec.args.get("path") or rec.args.get("filepath")
        res_str = _sanitize_output(rec.result)

        if tool == "file":
            if action == "create_file":
                if "created file:" in res_str.lower():
                    return f"Done — {res_str}."
                return f"Done — created file: {path or 'file'}."
            if action == "write_file":
                return f"Done — wrote changes to {path or 'file'}."
            if action in ("read_file", "open_file"):
                if res_str.startswith("Opened '") and res_str.endswith("'"):
                    return f"Done — opened {path or 'file'}."
                return f"Done — read '{path or 'file'}'. Content: '{res_str}'."
            if action == "list_directory":
                return f"Done — {res_str}"

        if tool == "windows" and action == "open_app":
            app = rec.args.get("app", "application")
            return f"Done — opened {app}."

        if tool == "browser":
            target = rec.args.get("site") or rec.args.get("url") or rec.args.get("query")
            return f"Done — opened {target} in browser."

        if res_str:
            return f"Done — {tool}.{action} completed: {res_str}."
        return f"Done — {tool}.{action} completed successfully."

    @staticmethod
    def _format_task_summary(rec: TaskExecutionRecord) -> str:
        """Brief label for multi-task lists."""
        tool_action = f"{rec.tool}.{rec.action}"
        path = rec.args.get("path") or rec.args.get("filepath") or rec.args.get("app")
        if path:
            return f"{tool_action} on {path}"
        res = _sanitize_output(rec.result, max_len=60)
        if res:
            return f"{tool_action} ({res})"
        return tool_action
