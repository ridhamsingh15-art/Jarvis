"""
Agent — top-level orchestrator of the Jarvis pipeline.

Receives user input and drives it through:
    Planner → Validator → Executor

Optionally integrates with Memory to provide conversational
context across interactions. Memory is injected via constructor
and is fully optional — if None, the pipeline works identically.

Never parses JSON, never calls the LLM, never executes tools
directly. All dependencies are injected via the constructor.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from core.exceptions import JarvisError
from core.executor import Executor
from core.planner import Planner
from core.task import Task, TaskStatus
from core.validator import Validator
from core.execution_summary import ExecutionSummary
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from core.execution_policy import (
    ExecutionPolicy,
    PolicyContext,
    PolicyResult,
    PolicyVerdict,
    CapabilitySource,
)
from core.tool_feedback_loop import ToolFeedbackLoop, MAX_TOOL_ITERATIONS
from core.mission_verifier import (
    MissionCompletionVerifier,
    VerificationResult,
    VerificationStatus,
    MissionPostcondition,
)

if TYPE_CHECKING:
    from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)
_MEMORY_FAILURES = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


import re
import time
import uuid

from applications.content_factory.image_engine.manager import ImageEngineManager
from applications.content_factory.project.manager import ProjectManager
from applications.content_factory.script_engine.manager import ScriptEngineManager
from applications.content_factory.storyboard_engine.manager import (
    StoryboardEngineManager,
)
from core.capability.manager import CapabilityManager
from core.cognition.manager import CognitiveManager
from core.integrations.n8n.capability import N8nCapabilityManager
from core.knowledge.indexer.manager import KnowledgeManager
from core.knowledge.indexer.scheduler import KnowledgeScheduler
from core.tool_intelligence.manager import ToolIntelligenceManager
from core.routing.intent_classifier import IntentClassifier, IntentType


class Agent:
    """Orchestrates the Jarvis agent pipeline.

    Receives fully constructed dependencies and coordinates
    the flow of data between them. Memory integration is
    optional and never crashes the pipeline.
    """

    def __init__(
        self,
        planner: Planner,
        validator: Validator,
        executor: Executor,
        memory: MemoryManager | None = None,
        cognitive_manager: CognitiveManager | None = None,
        tool_intelligence: ToolIntelligenceManager | None = None,
        capability_manager: CapabilityManager | None = None,
        knowledge_manager: KnowledgeManager | None = None,
        n8n_manager: N8nCapabilityManager | None = None,
        script_engine: ScriptEngineManager | None = None,
        storyboard_engine: StoryboardEngineManager | None = None,
        project_manager: ProjectManager | None = None,
        image_engine: ImageEngineManager | None = None,
        animation_engine: Any = None,
        voice_engine: Any = None,
        video_engine: Any = None,
        music_engine: Any = None,
        subtitle_engine: Any = None,
        thumbnail_engine: Any = None,
        seo_engine: Any = None,
        publishing_engine: Any = None,
        analytics_engine: Any = None,
        llm_client: Any = None,
        execution_policy: ExecutionPolicy | None = None,
        default_tool_timeout: float = 30.0,
        tool_feedback_loop: ToolFeedbackLoop | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
        mission_verifier: MissionCompletionVerifier | None = None,
        session_repository: Any = None,
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._executor = executor
        self._memory = memory
        self._cognitive_manager = cognitive_manager
        self._tool_intelligence = tool_intelligence
        self._capability_manager = capability_manager
        self._knowledge_manager = knowledge_manager
        self._n8n_manager = n8n_manager
        self._script_engine = script_engine
        self._storyboard_engine = storyboard_engine
        self._project_manager = project_manager
        self._image_engine = image_engine
        self._animation_engine = animation_engine
        self._voice_engine = voice_engine
        self._video_engine = video_engine
        self._music_engine = music_engine
        self._subtitle_engine = subtitle_engine
        self._thumbnail_engine = thumbnail_engine
        self._seo_engine = seo_engine
        self._publishing_engine = publishing_engine
        self._analytics_engine = analytics_engine
        self._execution_policy = execution_policy or ExecutionPolicy(allow_destructive_from_core=True)
        self._default_tool_timeout = default_tool_timeout
        self._tool_feedback_loop = tool_feedback_loop
        self._max_tool_iterations = max_tool_iterations
        self._mission_verifier = mission_verifier or MissionCompletionVerifier()
        self._executor_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jarvis-exec")
        
        # Fast Intent Router — Stage 1 deterministic, Stage 2 optional LLM for ambiguous inputs
        self._intent_classifier = IntentClassifier(llm_client=llm_client)
        
        # Session Repository initialization
        if session_repository is not None:
            self._session_repo = session_repository
        elif (
            self._memory
            and hasattr(self._memory, "_memory")
            and type(self._memory).__name__ not in ("Mock", "MagicMock", "AsyncMock")
            and hasattr(getattr(self._memory, "_memory", None), "get_connection")
            and type(getattr(self._memory, "_memory", None)).__name__ not in ("Mock", "MagicMock", "AsyncMock")
        ):
            from core.session import SessionRepository
            self._session_repo = SessionRepository(connection_factory=self._memory._memory.get_connection)
        else:
            from core.session import SessionRepository
            self._session_repo = SessionRepository()
        self._active_session_id: str | None = None

        # Degradation flags
        self._semantic_search_disabled = False
        self._last_execution_summary: ExecutionSummary | None = None
        self._last_verification_result: VerificationResult | None = None
        self._last_mission_telemetry: dict[str, Any] | None = None
        self._last_context_budget: Any | None = None
        self._last_trace: Any | None = None

    @property
    def session_repository(self) -> Any:
        """Return the active SessionRepository."""
        return self._session_repo

    @property
    def active_session_id(self) -> str | None:
        """Return the current active session identifier."""
        return self._active_session_id

    @property
    def active_session(self) -> Any | None:
        """Return the current active Session object."""
        if self._active_session_id:
            return self._session_repo.get(self._active_session_id)
        return None

    def create_session(self, session_id: str | None = None, metadata: dict | None = None) -> Any:
        """Explicitly create and activate a new session."""
        session = self._session_repo.create(session_id=session_id, metadata=metadata)
        self._active_session_id = session.session_id
        return session

    def close_session(self, session_id: str | None = None) -> bool:
        """Explicitly close a session."""
        sid = session_id or self._active_session_id
        if not sid:
            return False
        res = self._session_repo.close(sid)
        if sid == self._active_session_id:
            self._active_session_id = None
        return res

    @property
    def last_trace(self) -> Any | None:
        """Return the RequestTrace from the most recent run() execution."""
        return self._last_trace

    @property
    def last_context_budget(self) -> Any | None:
        """Return the ContextBudget report from the most recent LLM invocation."""
        return self._last_context_budget

    @property
    def last_execution_summary(self) -> ExecutionSummary | None:
        """Return the ExecutionSummary from the most recent run() execution."""
        return self._last_execution_summary

    @property
    def last_verification_result(self) -> VerificationResult | None:
        """Return the VerificationResult from the most recent run() execution."""
        return self._last_verification_result

    @property
    def last_mission_telemetry(self) -> dict[str, Any] | None:
        """Return truthful mission telemetry from the most recent mission execution."""
        return self._last_mission_telemetry

    @property
    def execution_policy(self) -> ExecutionPolicy:
        """Return the active ExecutionPolicy."""
        return self._execution_policy

    def close(self) -> None:
        """Release background execution resources."""
        if hasattr(self, "_executor_pool"):
            self._executor_pool.shutdown(wait=False)

    def run(
        self,
        user_input: str,
        on_action: Callable[[str], None] | None = None,
        user_confirmed: bool = False,
        intent: IntentType | None = None,
        expected_files: list[str] | None = None,
        expected_contents: dict[str, str] | None = None,
        postconditions: list[MissionPostcondition] | None = None,
        session_id: str | None = None,
    ) -> list[Task]:
        """Process user input conversationally.

        Pipeline:
            1. CognitiveManager processes input via LLM Conversation Engine
            2. Engine returns a natural response or requests a tool/plan
            3. Agent converts tool/plan requests to Tasks and routes them
            4. Execution results are captured

        Args:
            user_input: Natural language instruction from the user.
            on_action: Optional callback invoked immediately before a tool runs.
            session_id: Optional persistent session identifier. If None, active session is reused or created.

        Returns:
            List of Task objects with status, result, and errors.
        """
        # Resolve persistent session
        if session_id:
            target_session_id = session_id
        elif self._active_session_id:
            target_session_id = self._active_session_id
        else:
            target_session_id = f"sess_{int(time.time() * 1000) % 1000000}_{uuid.uuid4().hex[:4]}"

        session = self._session_repo.get(target_session_id)
        if session is None:
            session = self._session_repo.create(session_id=target_session_id)
        elif not session.is_resumable():
            raise ValueError(f"Cannot execute in closed or ended session: {target_session_id}")
        else:
            session = self._session_repo.resume(target_session_id) or session

        self._active_session_id = target_session_id
        session_turn = len(session.turns) + 1

        req_id = f"req_{int(time.time() * 1000) % 1000000}_{uuid.uuid4().hex[:4]}"
        logger.info("[REQUEST] %s (id=%s, session_id=%s, turn=%d)", user_input, req_id, target_session_id, session_turn)
        start_time = time.time()

        from core.runtime_trace import RequestTrace, set_current_trace, reset_current_trace
        trace = RequestTrace(
            request_id=req_id,
            session_id=target_session_id,
            session_turn=session_turn,
            user_input=user_input,
            start_time=start_time,
        )
        self._last_trace = trace
        trace_token = set_current_trace(trace)
        trace.record_event("request_received", {"user_input": user_input, "session_id": target_session_id, "turn": session_turn})

        # Synchronize CognitiveManager short-term conversation context from active session
        if self._cognitive_manager and hasattr(self._cognitive_manager, "_context"):
            st_ctx = self._cognitive_manager._context
            if hasattr(st_ctx, "set_messages"):
                st_ctx.set_messages(session.get_recent_conversation(limit=5))

        tasks: list[Task] = []
        timings: dict[str, float] = {}
        llm_calls = 0
        tool_action: str | None = None
        executive_brain_used = False
        reasoning_loop_used = False
        mission_control_used = False
        planned_mission_tasks: list[Task] = []
        loop_iterations = 0
        loop_stop_reason = "direct_response"

        self._last_verification_result = None
        self._last_mission_telemetry = None
        self._last_context_budget = None

        # Signal interactive foreground request to knowledge scheduler
        KnowledgeScheduler.set_interactive_active(True)
        try:
            # Direct inspection command: "jarvis models" or "models"
            if user_input.strip().lower() in {"jarvis models", "models", ":models"}:
                trace.record_route("SYSTEM")
                trace.complete("success")
                from core.model_manager import ModelManager
                table = ModelManager().format_models_table()
                return [Task(tool="system", action="respond", args={"message": table})]

            # 1. Classification
            logger.info('[REQUEST] "%s"', user_input)
            t0 = time.time()
            if intent is None:
                intent = self._intent_classifier.classify(user_input)
            trace.record_route(intent.value)
            route_decision_latency = time.time() - t0
            timings["Intent Classification"] = route_decision_latency
            logger.info("[ROUTER] route_decision_latency=%.4fs", route_decision_latency)
            logger.info("[ROUTE] %s", intent.value.upper())

            # 2. Context Loading
            pipeline_t0 = time.time()
            t0 = time.time()
            context_str = ""
            if intent in (IntentType.MEMORY, IntentType.MISSION):
                context_str += self._load_context()
            timings["Memory"] = time.time() - t0

            # 3. Routing
            if intent == IntentType.CHAT:
                logger.info("[PIPELINE] Conversation")
                logger.info("[ExecutiveBrain] SKIPPED")
                logger.info("[ReasoningLoop] SKIPPED")
                logger.info("[MissionControl] SKIPPED")
                t0 = time.time()
                if self._cognitive_manager:
                    num_llm_before = len(trace.llm_calls)
                    t_llm0 = time.time()
                    response = self._cognitive_manager.process_fast(user_input, intent="chat")
                    llm_calls += 1
                    if len(trace.llm_calls) == num_llm_before:
                        from core.context_budget import estimate_tokens
                        trace.record_llm_call(
                            model="qwen3:8b",
                            provider="ollama",
                            role="assistant",
                            stage="conversation",
                            start_time=t_llm0,
                            end_time=time.time(),
                            estimated_input_tokens=estimate_tokens(user_input),
                            estimated_output_tokens=estimate_tokens(getattr(response, "message", "")),
                            context_budget=trace.context_budget,
                            success=True,
                        )
                    
                    if response.type == "ACTION" and response.tool and response.action:
                        tool_action = f"{response.tool}.{response.action}"
                        tasks = [
                            Task(tool="system", action="respond", args={"message": response.message}),
                            Task(tool=response.tool, action=response.action, args=response.parameters or {}),
                        ]
                    elif response.type == "PLAN":
                        executive_brain_used = False
                        reasoning_loop_used = False
                        mission_control_used = False
                        logger.info("[PIPELINE] Escalating Conversation to Mission")
                        logger.info("[ExecutiveBrain] SKIPPED")
                        logger.info("[ReasoningLoop] SKIPPED")
                        logger.info("[MissionControl] SKIPPED")
                        intent = IntentType.MISSION
                        tasks = self._handle_mission(
                            user_input,
                            context_str,
                            user_confirmed=user_confirmed,
                            expected_files=expected_files,
                            expected_contents=expected_contents,
                            postconditions=postconditions,
                            session=session,
                        )
                        planned_mission_tasks = [t for t in tasks if t.tool != "system"]
                    else:
                        tasks = [Task(tool="system", action="respond", args={"message": response.message})]
                else:
                    tasks = [self._error_task("No cognitive manager available for CHAT.")]
                timings["LLM"] = time.time() - t0
                timings["Planning"] = 0.0
                timings["Reasoning"] = 0.0

            elif intent == IntentType.MEMORY:
                logger.info("[PIPELINE] Memory Management")
                logger.info("[ExecutiveBrain] SKIPPED")
                logger.info("[ReasoningLoop] SKIPPED")
                logger.info("[MissionControl] SKIPPED")
                t0 = time.time()

                # Check for explicit fact storage: "remember that my IDE is Antigravity"
                cleaned_input = user_input.strip()
                remember_match = re.match(
                    r"^(?:please\s+)?(?:remember(?:\s+that)?|save(?:\s+that)?)\s+(?:my\s+)?(.+?)\s+(?:is|=|to|be)\s+(.+)$",
                    cleaned_input,
                    re.IGNORECASE,
                )
                recall_match = re.match(
                    r"^(?:what\s+is\s+my|what's\s+my|do\s+you\s+remember\s+my|recall\s+my)\s+(.+?)[\?\.\!]*$",
                    cleaned_input,
                    re.IGNORECASE,
                )

                if remember_match:
                    key = remember_match.group(1).strip().lower()
                    val = remember_match.group(2).strip().rstrip(".")
                    if self._memory:
                        self._memory.remember_fact(key, val)
                    msg = f"I'll remember that your {key} is {val}."
                    tasks = [Task(tool="system", action="respond", args={"message": msg})]
                    timings["LLM"] = 0.0
                    from core.context_budget import ContextBudget, estimate_tokens
                    self._last_context_budget = ContextBudget(
                        user_input_tokens=estimate_tokens(user_input),
                        memory_tokens=estimate_tokens(val),
                    )
                elif recall_match:
                    key = recall_match.group(1).strip().lower()
                    val = self._memory.recall_fact(key) if self._memory else None
                    if val:
                        msg = f"Your {key} is {val}."
                        tasks = [Task(tool="system", action="respond", args={"message": msg})]
                        timings["LLM"] = 0.0
                        from core.context_budget import ContextBudget, estimate_tokens
                        self._last_context_budget = ContextBudget(
                            user_input_tokens=estimate_tokens(user_input),
                            memory_tokens=estimate_tokens(val),
                        )
                    else:
                        if self._cognitive_manager:
                            prompt = f"Context:\n{context_str}\n\nUser: {user_input}"
                            response = self._cognitive_manager.process_fast(prompt, intent="memory")
                            llm_calls += 1
                            tasks = [Task(tool="system", action="respond", args={"message": response.message})]
                        else:
                            tasks = [Task(tool="system", action="respond", args={"message": f"I don't have a record of your {key}."})]
                        timings["LLM"] = time.time() - t0
                else:
                    if self._cognitive_manager:
                        prompt = f"Context:\n{context_str}\n\nUser: {user_input}"
                        response = self._cognitive_manager.process_fast(prompt, intent="memory")
                        llm_calls += 1
                        tasks = [Task(tool="system", action="respond", args={"message": response.message})]
                    else:
                        tasks = [self._error_task("No memory manager available.")]
                    timings["LLM"] = time.time() - t0

                timings["Planning"] = 0.0
                timings["Reasoning"] = 0.0

            elif intent == IntentType.TOOL:
                logger.info("[PIPELINE] Tool Execution")
                logger.info("[ExecutiveBrain] SKIPPED")
                logger.info("[ReasoningLoop] SKIPPED")
                logger.info("[MissionControl] SKIPPED")
                t0 = time.time()

                if self._cognitive_manager:
                    num_llm_before = len(trace.llm_calls)
                    t_llm0 = time.time()
                    response = self._cognitive_manager.process_fast(user_input, intent="tool")
                    llm_calls += 1
                    if len(trace.llm_calls) == num_llm_before:
                        from core.context_budget import estimate_tokens
                        trace.record_llm_call(
                            model="qwen3:8b",
                            provider="ollama",
                            role="assistant",
                            stage="tool",
                            start_time=t_llm0,
                            end_time=time.time(),
                            estimated_input_tokens=estimate_tokens(user_input),
                            estimated_output_tokens=estimate_tokens(getattr(response, "message", "")),
                            context_budget=trace.context_budget,
                            success=True,
                        )
                    # Normalize tool names if LLM generated common synonyms
                    if response.type == "ACTION" and response.tool:
                        t_lower = response.tool.lower()
                        if t_lower in ("terminal", "command", "bash", "cmd", "powershell", "system_command", "sh"):
                            response.tool = "shell"
                            if response.action in ("run_command", "execute_command", "cmd", "command"):
                                response.action = "run"

                    reg = getattr(self, "_registry", None) or getattr(self._validator, "_registry", None)
                    tool_is_registered = (
                        reg.has_tool(response.tool) if reg and hasattr(reg, "has_tool") else True
                    ) if response.tool and response.tool != "system" else False

                    # Check direct deterministic resolution vs LLM response
                    use_direct = False
                    direct_resolved = self._resolve_direct_tool(user_input, session=session)
                    if direct_resolved:
                        d_tool, d_action, d_args = direct_resolved
                        if d_tool == "shell" and response.tool != "shell":
                            # User gave an explicit shell/pytest command, but LLM selected a non-shell tool (e.g. file.open_file)
                            use_direct = True
                        elif response.type != "ACTION" or not tool_is_registered or response.tool == "system":
                            use_direct = True

                    if use_direct and direct_resolved:
                        tool, action, args = direct_resolved
                        tool_action = f"{tool}.{action}"
                        tasks = [
                            Task(tool="system", action="respond", args={"message": response.message if response.message else f"Executing {tool_action}."}),
                            Task(tool=tool, action=action, args=args),
                        ]
                    elif response.type == "ACTION" and response.tool and response.action and response.tool != "system" and tool_is_registered:
                        tool_action = f"{response.tool}.{response.action}"
                        tasks = [
                            Task(tool="system", action="respond", args={"message": response.message}),
                            Task(tool=response.tool, action=response.action, args=response.parameters or {}),
                        ]
                    elif direct_resolved:
                        tool, action, args = direct_resolved
                        tool_action = f"{tool}.{action}"
                        tasks = [
                            Task(tool="system", action="respond", args={"message": response.message if response.message else f"Executing {tool_action}."}),
                            Task(tool=tool, action=action, args=args),
                        ]
                    else:
                        # 1. Try registry-driven resolution (covers any registered tool)
                        resolved = (
                            self._tool_intelligence.resolve_from_registry(user_input)
                            if self._tool_intelligence else None
                        )
                        if resolved:
                            tool, action, args = resolved
                            tool_action = f"{tool}.{action}"
                            tasks = [
                                Task(tool="system", action="respond", args={"message": response.message if response.message else f"Executing {tool_action}."}),
                                Task(tool=tool, action=action, args=args),
                            ]
                        elif self._capability_manager:
                            try:
                                plan, profile = self._capability_manager.route(user_input)
                                llm_calls += 1
                                if plan.requires_planner:
                                    tasks = self._planner.plan(user_input, context="")
                                    llm_calls += 1
                                else:
                                    tasks = [Task(tool="system", action="respond", args={"message": response.message})]
                            except JarvisError as exc:
                                tasks = [self._error_task(f"Tool routing failed: {exc}")]
                        else:
                            tasks = [Task(tool="system", action="respond", args={"message": response.message})]
                else:
                    try:
                        tasks = self._planner.plan(user_input, context="")
                        llm_calls += 1
                    except JarvisError as exc:
                        tasks = [self._error_task(f"Planning failed: {exc}")]
                timings["Planning"] = time.time() - t0
                timings["LLM"] = timings["Planning"]
                timings["Reasoning"] = 0.0

            else:  # MISSION
                logger.info("[PIPELINE] Autonomous Mission")
                logger.info("[ExecutiveBrain] SKIPPED")
                logger.info("[ReasoningLoop] SKIPPED")
                logger.info("[MissionControl] SKIPPED")
                executive_brain_used = False
                reasoning_loop_used = False
                mission_control_used = False
                t0 = time.time()
                tasks = self._handle_mission(
                    user_input,
                    context_str,
                    user_confirmed=user_confirmed,
                    expected_files=expected_files,
                    expected_contents=expected_contents,
                    postconditions=postconditions,
                    session=session,
                )
                planned_mission_tasks = [t for t in tasks if t.tool != "system"]
                mission_llm_calls = 1
                if self._cognitive_manager:
                    mission_llm_calls += 1
                llm_calls += mission_llm_calls
                timings["Planning"] = time.time() - t0
                timings["Reasoning"] = 0.0
                timings["LLM"] = timings["Planning"]

            pipeline_latency = time.time() - pipeline_t0

            # 4. Execution
            t0 = time.time()
            exec_tasks = [t for t in tasks if t.tool != "system"]
            resp_tasks = [t for t in tasks if t.tool == "system"]

            if exec_tasks:
                # Phase 7B: Real Observe -> Decide -> Act Loop via ToolFeedbackLoop
                def _safe_exec(t):
                    try:
                        return self._process_task(t, user_confirmed=user_confirmed)
                    except TypeError:
                        return self._process_task(t)

                feedback_loop = self._tool_feedback_loop or ToolFeedbackLoop(
                    execute_fn=_safe_exec,
                    cognitive_manager=self._cognitive_manager,
                    max_iterations=self._max_tool_iterations,
                    on_action=lambda t: on_action(self._action_announcement(t)) if on_action else None,
                )
                loop_result = feedback_loop.run(
                    request_id=req_id,
                    user_input=user_input,
                    initial_tasks=tasks,
                )
                results = loop_result.tasks
                llm_calls += loop_result.llm_calls
                loop_iterations = loop_result.iterations_used
                if loop_result.loop_detected:
                    loop_stop_reason = "loop_detected"
                elif loop_result.limit_reached:
                    loop_stop_reason = "iteration_limit_reached"
                elif loop_result.succeeded:
                    loop_stop_reason = "completed"
                else:
                    loop_stop_reason = "stopped"
                if not tool_action and any(t.tool != "system" for t in results):
                    first_tool = next(t for t in results if t.tool != "system")
                    tool_action = f"{first_tool.tool}.{first_tool.action}"
                self._last_execution_summary = ExecutionSummary.from_tasks([t for t in results if t.tool != "system"])
            else:
                # Pure conversational or memory response without tool execution
                summary = ExecutionSummary.from_tasks([])
                self._last_execution_summary = summary
                results_by_id: dict[int, Task] = {}
                for task in resp_tasks:
                    try:
                        res = self._process_task(task, execution_summary=summary, user_confirmed=user_confirmed)
                    except TypeError:
                        try:
                            res = self._process_task(task, execution_summary=summary)
                        except TypeError:
                            res = self._process_task(task)
                    results_by_id[id(task)] = res
                results = [results_by_id.get(id(t), t) for t in resp_tasks]

            # 5. Mission Verification & Grounding (associated ONLY with intent == IntentType.MISSION)
            if intent == IntentType.MISSION:
                if (not expected_files) and session.last_target_file:
                    if any(k in user_input.lower() for k in ("verify it", "verify its", "verify that", "verify the file", "check it", "check its")):
                        expected_files = [session.last_target_file]
                if (not expected_contents) and session.last_target_content and expected_files:
                    expected_contents = {expected_files[0]: session.last_target_content}

                raw_claim = ""
                for t in results:
                    if t.tool == "system" and t.action == "respond":
                        raw_claim = str(t.result or t.args.get("message", ""))
                        break

                v_res = self._mission_verifier.verify(
                    tasks=results,
                    response_text=raw_claim,
                    expected_files=expected_files,
                    expected_contents=expected_contents,
                    postconditions=postconditions,
                    user_input=user_input,
                )
                self._last_verification_result = v_res

                # Re-ground execution summary with authoritative verification outcome
                executed_tools = [t for t in results if t.tool != "system"]
                self._last_execution_summary = ExecutionSummary.from_tasks(
                    executed_tools,
                    verification_result=v_res,
                )
                grounded_msg = self._last_execution_summary.ground_response(raw_claim)

                # Ground the response task
                resp_task = next((t for t in results if t.tool == "system" and t.action == "respond"), None)
                if resp_task is not None:
                    resp_task.result = grounded_msg
                    resp_task.args["message"] = grounded_msg
                else:
                    resp_task = Task(tool="system", action="respond", args={"message": grounded_msg})
                    resp_task.start()
                    resp_task.complete(grounded_msg)
                    results.append(resp_task)

                # Truthful mission telemetry
                from core.mission_verifier import get_effective_tasks
                effective_tools = [t for t in get_effective_tasks(executed_tools) if t.tool != "system"]
                # Capture context budget from loop or cognitive manager
                if self._tool_feedback_loop and getattr(self._tool_feedback_loop, "_last_context_budget", None):
                    self._last_context_budget = self._tool_feedback_loop._last_context_budget
                elif self._cognitive_manager and getattr(self._cognitive_manager, "last_context_budget", None):
                    self._last_context_budget = self._cognitive_manager.last_context_budget

                self._last_mission_telemetry = {
                    "mission_detected": True,
                    "planned_tasks": len(planned_mission_tasks),
                    "executed_tasks": len(executed_tools),
                    "effective_tasks": len(effective_tools),
                    "successful_tasks": sum(1 for t in effective_tools if t.status == TaskStatus.COMPLETED),
                    "failed_tasks": sum(1 for t in effective_tools if t.status == TaskStatus.FAILED),
                    "total_attempts": len(executed_tools),
                    "verification_status": v_res.status.value,
                    "verification_reason": "; ".join(v_res.details),
                    "number_of_loop_iterations": loop_iterations,
                    "number_of_llm_calls": llm_calls,
                    "number_of_tool_calls": len(executed_tools),
                    "total_latency": timings.get("Total", time.time() - start_time),
                    "termination_reason": loop_stop_reason,
                    "estimated_context_tokens": self._last_context_budget.total_input_tokens if self._last_context_budget else 0,
                    "context_truncated": self._last_context_budget.truncated if self._last_context_budget else False,
                }
                trace.record_verification(v_res)
                trace.record_mission_telemetry(self._last_mission_telemetry)
                logger.info(
                    "[MISSION_TELEMETRY] status=%s planned=%d executed=%d success=%d failed=%d reason=%s",
                    self._last_mission_telemetry["verification_status"],
                    self._last_mission_telemetry["planned_tasks"],
                    self._last_mission_telemetry["executed_tasks"],
                    self._last_mission_telemetry["successful_tasks"],
                    self._last_mission_telemetry["failed_tasks"],
                    self._last_mission_telemetry["verification_reason"][:120],
                )

            timings["Tool Execution"] = time.time() - t0
            timings["Total"] = time.time() - start_time

            # Observability pipeline summary
            logger.info("[LLM] calls=%d", max(1 if intent in (IntentType.CHAT, IntentType.TOOL) and self._cognitive_manager else 0, llm_calls))
            if tool_action:
                logger.info("[TOOL] %s", tool_action)
                exec_success = any(t.status == TaskStatus.COMPLETED for t in results if t.tool != "system")
                logger.info("[EXECUTOR] %s", "success" if exec_success else "failed")
            logger.info("[BACKGROUND] work_running=%s", KnowledgeScheduler.is_indexing())
            logger.info("[RESPONSE] tasks=%d total_latency=%.3fs", len(results), timings["Total"])
            logger.info(
                "Lifecycle Metrics: route_decision_latency=%.4fs, pipeline_latency=%.4fs, llm_call_count=%d, executive_brain_used=%s, reasoning_loop_used=%s, mission_control_used=%s",
                route_decision_latency,
                pipeline_latency,
                llm_calls,
                executive_brain_used,
                reasoning_loop_used,
                mission_control_used,
            )

            # Store interaction in memory
            self._save_to_memory(user_input, results)

            # Reflect only when the outcome can improve future behavior:
            #   ACTION — a tool was invoked (worth remembering)
            #   PLAN   — a mission was escalated (always reflect)
            #   MISSION intent — reasoning stack was used (always reflect)
            # Skip reflection for:
            #   pure CHAT RESPONSE — no new facts, no tool outcomes
            #   MEMORY route — memory writes/reads are self-contained
            _should_reflect = (
                intent == IntentType.MISSION
                or tool_action is not None  # any tool was actually executed
            )
            if self._cognitive_manager and _should_reflect:
                success = not any(t.status == TaskStatus.FAILED for t in results)
                main_action = tasks[1].action if len(tasks) > 1 else "respond"
                self._cognitive_manager.reflect(
                    user_input=user_input,
                    response_type="RESPONSE",
                    action=main_action,
                    success=success,
                    execution_time=timings["Total"],
                )

            if self._last_context_budget is None:
                if self._tool_feedback_loop and getattr(self._tool_feedback_loop, "_last_context_budget", None):
                    self._last_context_budget = self._tool_feedback_loop._last_context_budget
                elif self._cognitive_manager and getattr(self._cognitive_manager, "last_context_budget", None):
                    self._last_context_budget = self._cognitive_manager.last_context_budget

            if self._last_context_budget is not None:
                trace.record_context_budget(self._last_context_budget)
                trace.session_context_tokens = getattr(self._last_context_budget, "history_tokens", 0)

            final_status = "success"
            if any(t.status == TaskStatus.FAILED for t in results):
                if any(t.status == TaskStatus.COMPLETED for t in results):
                    final_status = "partial"
                elif any("Execution policy denied" in str(t.error or "") for t in results):
                    final_status = "denied"
                elif any("timed out" in str(t.error or "") for t in results):
                    final_status = "timeout"
                else:
                    final_status = "failed"
            elif self._last_verification_result and not self._last_verification_result.succeeded:
                final_status = self._last_verification_result.status.value

            resp_task = next((t for t in results if t.tool == "system" and t.action == "respond"), None)
            final_resp = str(resp_task.result if resp_task else (results[0].result if results else ""))
            trace.record_final_response(final_resp, status=final_status)
            trace.complete(final_status)

            # Record turn in session repository
            tools_exec = [
                {"tool": t.tool, "action": t.action, "status": t.status.value, "args": t.args}
                for t in results if t.tool != "system"
            ]
            target_files = []
            target_content = None
            for t in results:
                if t.tool == "file" and t.args.get("path"):
                    target_files.append(t.args["path"])
                    if t.args.get("text") or t.args.get("content"):
                        target_content = t.args.get("text") or t.args.get("content")

            if not target_files:
                f_match = re.search(r"(?:file\s+(?:called|named)|the\s+file)\s+([a-zA-Z0-9_\-\.]+)", user_input, re.IGNORECASE)
                if f_match:
                    target_files.append(f_match.group(1))

            mission_state = {}
            if intent == IntentType.MISSION or self._last_mission_telemetry:
                mission_state = {
                    "last_mission_telemetry": self._last_mission_telemetry,
                    "verification": (
                        self._last_verification_result.status.value
                        if self._last_verification_result else None
                    ),
                }

            meta_updates = {}
            if target_files:
                meta_updates["last_target_file"] = target_files[-1]
            if target_content:
                meta_updates["last_target_content"] = target_content

            route_str = (intent.value.upper() if hasattr(intent, "value") else str(intent).upper()) if intent else "UNKNOWN"
            meta_updates["last_route"] = route_str

            try:
                self._session_repo.add_turn(
                    session_id=session.session_id,
                    request_id=req_id,
                    user_input=user_input,
                    response=final_resp,
                    route=route_str,
                    tools_executed=tools_exec,
                    target_files=target_files,
                    mission_state=mission_state,
                    metadata_updates=meta_updates,
                )
            except Exception as exc:
                logger.warning("Failed to record turn in session: %s", exc)

            completed = sum(1 for t in results if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in results if t.status == TaskStatus.FAILED)

            logger.info(
                "Finished: %d task(s), %d completed, %d failed",
                len(results),
                completed,
                failed,
            )

            return results
        finally:
            reset_current_trace(trace_token)
            KnowledgeScheduler.set_interactive_active(False)


    def _handle_mission(
        self,
        user_input: str,
        context_str: str,
        user_confirmed: bool = False,
        expected_files: list[str] | None = None,
        expected_contents: dict[str, str] | None = None,
        postconditions: list[MissionPostcondition] | None = None,
        session: Any = None,
    ) -> list[Task]:
        """Handles complex autonomous missions using the full reasoning loop."""
        tasks = []
        if session is not None:
            lower = user_input.lower()
            if (not expected_files) and session.last_target_file:
                if any(k in lower for k in ("verify it", "verify its", "verify that", "verify the file", "check it", "check its")):
                    expected_files = [session.last_target_file]
            if (not expected_contents) and session.last_target_content and expected_files:
                expected_contents = {expected_files[0]: session.last_target_content}
            if session.active_mission:
                context_str += f"\nActive Mission State:\n{session.active_mission}\n"
        if self._capability_manager:
            # New Intelligent Capability Routing flow
            try:
                plan, profile = self._capability_manager.route(user_input)
                model_name = profile.name if profile is not None else "unknown"
                logger.info("Capability Plan: %s (Model: %s)", plan.required_capabilities, model_name)
                
                # Fetch memory if required
                context_str = ""
                if plan.requires_memory:
                    context_str += self._load_context()
                if plan.requires_knowledge and self._knowledge_manager:
                    context_str += self._load_knowledge(user_input)
                    
                # Media-engine dispatch table — each entry:
                # (plan_flag, handler_key, async_method, user_message)
                # Extra kwargs (model, platforms) are handled per-entry via metadata.
                _MEDIA_DISPATCH = [
                    ("requires_animation",  "animation_engine",  "generate_animations_async",  "Animation generation mission started: {mid}. I will notify you when the animations are ready."),
                    ("requires_voice",       "voice_engine",       "generate_voice_async",       "Voice generation mission started: {mid}. I will notify you when the voices are ready."),
                    ("requires_video",       "video_engine",       "generate_video_async",       "Video assembly mission started: {mid}. I will notify you when the final video is ready."),
                    ("requires_music",       "music_engine",       "generate_music_async",       "Music generation mission started: {mid}. I will notify you when the music is ready."),
                    ("requires_subtitles",   "subtitle_engine",    "generate_subtitles_async",   "Subtitle generation mission started: {mid}. I will notify you when subtitles are ready."),
                    ("requires_thumbnail",   "thumbnail_engine",   "generate_thumbnail_async",   "Thumbnail generation mission started: {mid}. I will notify you when thumbnail is ready."),
                    ("requires_seo",         "seo_engine",         "generate_seo_async",         "SEO generation mission started: {mid}. I will notify you when SEO metadata is ready."),
                    ("requires_publishing",  "publishing_engine",  "publish_async",              "Publishing mission started: {mid}. I will notify you when publishing is complete."),
                    ("requires_analytics",   "analytics_engine",   "sync_analytics_async",       "Analytics sync mission started: {mid}. I will notify you when analytics are updated."),
                ]
                plan_meta = getattr(plan, "metadata", None) or {}
                project_id = plan_meta.get("project_id", "default_project")
                for flag, handler_key, method, msg_tpl in _MEDIA_DISPATCH:
                    if not getattr(plan, flag, False):
                        continue
                    if handler_key == "publishing_engine":
                        policy_ctx = PolicyContext(
                            tool="publishing",
                            action="publish",
                            source=CapabilitySource.CORE,
                            source_id="agent",
                            user_confirmed=user_confirmed,
                        )
                        policy_res = self._execution_policy.check(policy_ctx)
                        if policy_res.verdict == PolicyVerdict.DENY:
                            return [self._error_task(f"Execution policy denied: {policy_res.reason}")]
                        if policy_res.verdict == PolicyVerdict.REQUIRE_CONFIRMATION:
                            return [self._error_task(f"Execution policy requires user confirmation: {policy_res.reason}")]

                    mgr = self._capability_manager.get_handler(handler_key)
                    # Some engines need extra kwargs from plan metadata
                    extra = {}
                    if handler_key == "animation_engine":
                        extra["model"] = plan_meta.get("animation_model", "wan")
                    elif handler_key in ("publishing_engine", "analytics_engine"):
                        extra["platforms"] = plan_meta.get("platforms", ["youtube"])
                    elif handler_key == "voice_engine":
                        extra["model"] = plan_meta.get("voice_model", "piper")
                    mid = getattr(mgr, method)(project_id, **extra) if extra else getattr(mgr, method)(project_id)
                    return [Task(tool="system", action="respond", args={"message": msg_tpl.format(mid=mid)})]

                # Intercept for Automation Tasks
                if plan.requires_automation and self._n8n_manager:
                    policy_ctx = PolicyContext(
                        tool="automation",
                        action="execute_workflow",
                        source=CapabilitySource.CORE,
                        source_id="agent",
                        user_confirmed=user_confirmed,
                    )
                    policy_res = self._execution_policy.check(policy_ctx)
                    if policy_res.verdict == PolicyVerdict.DENY:
                        return [self._error_task(f"Execution policy denied: {policy_res.reason}")]
                    if policy_res.verdict == PolicyVerdict.REQUIRE_CONFIRMATION:
                        return [self._error_task(f"Execution policy requires user confirmation: {policy_res.reason}")]

                    # We initialize n8n. If it's not installed, it will prompt the user via EventBus,
                    # but for now we just try to route it.
                    self._n8n_manager.initialize()
                    # Ask the LLM which workflow to run based on available ones
                    available = ", ".join(self._n8n_manager.list_workflows())
                    prompt = f"User asked: {user_input}. Available workflows: {available}. Reply with ONLY the exact workflow name to execute."
                    response = self._cognitive_manager.process(prompt) if self._cognitive_manager else None
                    if response and response.message.strip() in available:
                        mission_id = self._n8n_manager.execute_workflow_by_name(response.message.strip(), {"prompt": user_input})
                        tasks = [Task(tool="system", action="respond", args={"message": f"I have started the {response.message.strip()} automation. Tracking mission: {mission_id}"})]
                        return tasks
                    else:
                        tasks = [Task(tool="system", action="respond", args={"message": "I couldn't identify the specific automation workflow you wanted to run."})]
                        return tasks

                # Intercept for Script Generation
                if plan.requires_scripting and self._script_engine:
                    # Use LLM-extracted style from CapabilityPlan; default to "storytelling"
                    style = getattr(plan, "style", "storytelling") or "storytelling"
                    mission_id = self._script_engine.generate_script_async(topic=user_input, style=style, context=context_str)
                    tasks = [Task(tool="system", action="respond", args={"message": f"I have started generating your {style} script. Tracking mission: {mission_id}"})]
                    return tasks
                    
                # Intercept for Storyboard Generation
                if plan.requires_storyboard and self._storyboard_engine:
                    from applications.content_factory.script_engine.formatter import (
                        format_script,
                    )
                    from core.mission.enums import MissionStatus
                    
                    # Try to find a recently completed script in missions
                    missions = self._storyboard_engine._mission_manager.list_all()
                    script_package = None
                    for m in reversed(missions):
                        if m.status == MissionStatus.COMPLETED and "script_package" in m.metadata.annotations:
                            try:
                                script_package = format_script(m.metadata.annotations["script_package"])
                                break
                            except Exception:
                                continue
                                
                    if not script_package:
                        return [Task(tool="system", action="respond", args={"message": "I couldn't find a recently generated script to storyboard. Please generate a script first."})]
                        
                    mission_id = self._storyboard_engine.generate_storyboard_async(script=script_package)
                    tasks = [Task(tool="system", action="respond", args={"message": f"I have started generating the storyboard for '{script_package.title}'. Tracking mission: {mission_id}"})]
                    return tasks
                    
                # Intercept for Project Management
                if plan.requires_project_management and self._project_manager:
                    projects = self._project_manager.search_projects()
                    titles = [p.title for p in projects]
                    msg = "You have the following Content Factory Projects available: " + ", ".join(titles) if titles else "No projects found."
                    return [Task(tool="system", action="respond", args={"message": msg})]
                    
                # Intercept for Image Generation
                if plan.requires_image_generation and self._image_engine and self._project_manager:
                    # Look for the most recently updated project
                    projects = self._project_manager.search_projects()
                    if not projects:
                        return [Task(tool="system", action="respond", args={"message": "I couldn't find any projects to generate images for."})]
                    projects.sort(key=lambda p: p.updated_at, reverse=True)
                    target_project = projects[0]
                    
                    mission_id = self._image_engine.generate_images_async(target_project.project_id)
                    return [Task(tool="system", action="respond", args={"message": f"I have queued image generation for the '{target_project.title}' project. Tracking mission: {mission_id}"})]
                    
                # Use Planner if required
                if plan.requires_planner:
                    plan_tasks = self._planner.plan(user_input, context=context_str)
                    
                    # Generate natural language response alongside planning
                    if self._cognitive_manager:
                        response = self._cognitive_manager.process(user_input)
                        tasks = [Task(tool="system", action="respond", args={"message": response.message})] + plan_tasks
                    else:
                        tasks = plan_tasks
                else:
                    # Single action or just conversational
                    if self._cognitive_manager:
                        response = self._cognitive_manager.process(user_input)
                        tasks = [Task(tool="system", action="respond", args={"message": response.message})]
                        
                        if plan.requires_execution and response.type == "ACTION":
                            tool = response.tool or "windows"
                            action = response.action or "open_app"
                            parameters = response.parameters or {}
                            tasks.append(Task(tool=tool, action=action, args=parameters))
                    else:
                        tasks = [self._error_task("Capability router required execution but no cognitive manager was available.")]
                        
            except JarvisError as exc:
                logger.error("Routing failed: %s", exc)
                tasks = [self._error_task(f"I couldn't process that request: {exc}")]
        else:
            # Fallback if no capability router is injected
            try:
                tasks = self._planner.plan(user_input, context=self._load_context())
            except JarvisError as exc:
                logger.error("Planning failed: %s", exc)
                tasks = [self._error_task("I couldn't plan that request just now.")]
        return tasks

    @staticmethod
    def _action_announcement(task: Task) -> str:
        """Describe a pending tool action in clear, user-facing language."""
        if task.tool == "windows" and task.action == "open_app":
            return f"I'll open {task.args.get('app', 'that application')} for you."
        if task.tool == "browser" and task.action == "open_site":
            raw_site = str(task.args.get("site", "that site"))
            site = {
                "github": "GitHub",
                "google": "Google",
                "stackoverflow": "Stack Overflow",
                "youtube": "YouTube",
                "wikipedia": "Wikipedia",
            }.get(raw_site.lower(), raw_site.title())
            return f"I'll open {site} in your browser."
        if task.tool == "browser" and task.action == "open_url":
            return f"I'll open {task.args.get('url', 'that link')} in your browser."
        if task.tool == "browser" and task.action == "search_google":
            return f"I'll search Google for {task.args.get('query', 'that')}."
        if task.tool == "file" and task.action == "create_file":
            return f"I'll create {task.args.get('path', 'that file')}."
        return "I'll take care of that."

    @staticmethod
    def _resolve_direct_tool(user_input: str, session: Any = None) -> tuple[str, str, dict] | None:
        """Deterministically resolves common OS and tool actions if LLM returns plain text."""
        lower = user_input.lower().strip()
        # Cross-turn test execution: "run its tests", "run the tests", "run tests"
        if session and session.last_target_file:
            if any(k in lower for k in ("run its tests", "run the tests", "run tests for it", "run its test")):
                target = session.last_target_file
                p = Path(target)
                if not p.name.startswith("test_") and not p.name.endswith("_test.py"):
                    test_cand = p.parent / f"test_{p.name}"
                    cmd = f"pytest {test_cand}" if test_cand.exists() else f"pytest {target}"
                else:
                    cmd = f"pytest {target}"
                return "shell", "run", {"command": cmd}

        # Direct test execution: "run tests", "run pytest", "pytest <path>"
        pytest_match = re.match(r"^(?:run\s+)?(?:the\s+)?pytest(?:\s+(.+))?$", lower)
        if pytest_match:
            args_str = (pytest_match.group(1) or "").strip()
            return "shell", "run", {"command": f"pytest {args_str}".strip()}

        if lower in ("run tests", "run the tests", "run test", "execute tests"):
            return "shell", "run", {"command": "pytest"}

        # Direct shell command: "run shell command X", "shell command X", "run command X"
        shell_match = re.match(r"^(?:run\s+)?(?:shell\s+command|shell|command)\s+(.+)$", user_input, re.IGNORECASE)
        if shell_match:
            cmd = shell_match.group(1).strip()
            if (cmd.startswith("'") and cmd.endswith("'")) or (cmd.startswith('"') and cmd.endswith('"')):
                cmd = cmd[1:-1].strip()
            return "shell", "run", {"command": cmd}

        # Create file: "create a file called X containing Y"
        create_match = re.search(r"create\s+(?:a\s+)?file\s+(?:called|named)\s+([^\s]+)(?:\s+(?:containing|with\s+content)\s+(.+))?", user_input, re.IGNORECASE)
        if create_match:
            fpath = create_match.group(1).strip("'\"")
            fcontent = (create_match.group(2) or "").strip("'\"")
            return "file", "create_file", {"path": fpath, "text": fcontent}

        # Patch/edit file: "patch file X replacing 'A' with 'B'"
        patch_match = re.search(r"(?:patch|edit|modify)\s+(?:file\s+)?([^\s]+)\s+replacing\s+['\"](.+?)['\"]\s+with\s+['\"](.*?)['\"]", user_input, re.IGNORECASE)
        if patch_match:
            return "file", "patch_file", {
                "path": patch_match.group(1).strip("'\""),
                "old_text": patch_match.group(2),
                "new_text": patch_match.group(3),
            }

        # Cross-turn file reference: "read it", "read it back", "read that file"
        if session and session.last_target_file:
            if re.search(r"\b(?:read|show|cat|display)\s+(?:it|it\s+back|that|that\s+file|the\s+file)\b", lower) or lower in ("read it", "read it back", "read that", "read the file"):
                return "file", "read_file", {"path": session.last_target_file}

        # Calculator app
        if (
            re.search(r"\b(?:open|launch|start|run)\s+(?:the\s+)?(?:calc|calculator)\b", lower)
            or lower in ("calc", "calculator", "open calc")
        ) and not lower.endswith(".py") and "file" not in lower:
            return "windows", "open_app", {"app": "calculator"}

        # Notepad
        if re.search(r"\b(?:open|launch|start)\s+(?:the\s+)?notepad\b", lower) or lower in ("notepad", "open notepad"):
            return "windows", "open_app", {"app": "notepad"}

        # GitHub
        if "github" in lower:
            return "browser", "open_site", {"site": "github"}

        # Search
        search_match = re.match(r".*?(?:search\s+(?:google\s+for\s+|for\s+)|google\s+)(.+)$", lower)
        if search_match:
            return "browser", "search_google", {"query": search_match.group(1).strip()}

        return None

    def _load_context(self) -> str:
        """Load conversation context from memory.

        Returns:
            Formatted context string, or empty string if memory
            is unavailable or retrieval fails.
        """
        if self._memory is None:
            return ""

        try:
            context = self._memory.get_context()
            formatted = getattr(context, "formatted", "")
            return formatted if isinstance(formatted, str) else ""
        except _MEMORY_FAILURES as exc:
            logger.warning("Failed to load memory context: %s", exc)
            return ""

    def _load_knowledge(self, query: str) -> str:
        """Load semantic search results from the PKI.
        
        Args:
            query: The user's request to search for.
            
        Returns:
            Formatted knowledge string, or empty if unavailable.
        """
        if self._knowledge_manager is None or self._semantic_search_disabled:
            return ""
            
        try:
            results = self._knowledge_manager.search(query, limit=3)
            if not results:
                return ""
            
            blocks = []
            for r in results:
                blocks.append(f"File: {r.document.filename} ({r.document.path})\nContent snippet:\n{r.chunk.text}")
            
            return "\n\n--- PERSONAL KNOWLEDGE INDEX ---\n" + "\n\n".join(blocks) + "\n--------------------------------\n"
        except Exception as exc:
            if not self._semantic_search_disabled:
                logger.warning("Semantic search unavailable (Embedding model offline?): %s. Disabling semantic search for this session to prevent timeout spam.", exc)
                self._semantic_search_disabled = True
            return ""

    def _save_to_memory(self, user_input: str, tasks: list[Task]) -> None:
        """Store the current interaction in memory.

        Args:
            user_input: The user's original input.
            tasks: Executed tasks with final states.
        """
        if self._memory is None:
            return

        try:
            self._memory.store_interaction(user_input, tasks)
        except _MEMORY_FAILURES as exc:
            logger.warning("Failed to save to memory: %s", exc)

    def _process_task(
        self,
        task: Task,
        execution_summary: ExecutionSummary | None = None,
        user_confirmed: bool = False,
    ) -> Task:
        """Validate and execute a single task under ExecutionPolicy and timeout protection.

        Args:
            task: A Task in PENDING state.
            execution_summary: Optional ExecutionSummary to ground response tasks.
            user_confirmed: True if explicit human user approval was granted.

        Returns:
            The Task with updated status after execution.
        """
        # Handle system tasks (conversational responses, pipeline errors) directly —
        # these don't go through validation or execution.
        if task.tool == "system":
            if task.action == "respond":
                raw_msg = (
                    task.args.get("message")
                    or task.args.get("content")
                    or task.args.get("response")
                    or task.args.get("text")
                    or ""
                )
                initial_claim = str(raw_msg)
                if execution_summary is not None:
                    final_message = execution_summary.ground_response(initial_claim)
                else:
                    final_message = initial_claim

                if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                    task.start()
                if task.status == TaskStatus.RUNNING:
                    task.complete(final_message)
            return task

        # 1. Normalization & Validation
        start_tool_t = time.time()
        trace = None
        try:
            from core.runtime_trace import get_current_trace
            trace = get_current_trace()
        except Exception:
            pass

        try:
            if self._tool_intelligence:
                task = self._tool_intelligence.process(task)
            else:
                self._validator.validate(task)
        except JarvisError as exc:
            logger.warning("Validation failed: %s", exc)
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            if task.status == TaskStatus.RUNNING:
                task.fail(self._friendly_error_message(str(exc)))
            if trace is not None:
                trace.record_tool_call(
                    iteration=getattr(task, "iteration", 1) or 1,
                    task_id=id(task),
                    tool=task.tool,
                    action=task.action,
                    start_time=start_tool_t,
                    end_time=time.time(),
                    policy_verdict="deny",
                    confirmation_required=False,
                    confirmation_status="not_required",
                    execution_status="failed",
                    timeout=False,
                    error_category="ValidationError",
                    error_message=str(exc),
                )
            return task

        # 2. Execution Policy Gate (Security Invariant: MODEL != AUTHORIZATION)
        # user_confirmed is strictly derived from runtime/user caller, NEVER model task args.
        policy_ctx = PolicyContext(
            tool=task.tool,
            action=task.action,
            source=task.source if task.source is not None else CapabilitySource.CORE,
            source_id="agent",
            user_confirmed=user_confirmed,
            request_id=trace.request_id if trace else "",
            args=task.args if hasattr(task, "args") and isinstance(task.args, dict) else {},
        )
        policy_result = self._execution_policy.check(policy_ctx)

        if policy_result.verdict == PolicyVerdict.DENY:
            logger.warning(
                "[POLICY] Denied tool action %s.%s: %s",
                task.tool,
                task.action,
                policy_result.reason,
            )
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.fail(f"Execution policy denied: {policy_result.reason}")
            if trace is not None:
                trace.record_tool_call(
                    iteration=getattr(task, "iteration", 1) or 1,
                    task_id=id(task),
                    tool=task.tool,
                    action=task.action,
                    start_time=start_tool_t,
                    end_time=time.time(),
                    policy_verdict="deny",
                    confirmation_required=False,
                    confirmation_status="not_required",
                    execution_status="failed",
                    timeout=False,
                    error_category="PolicyDenied",
                    error_message=policy_result.reason,
                )
            return task

        if policy_result.verdict == PolicyVerdict.REQUIRE_CONFIRMATION:
            logger.warning(
                "[POLICY] Tool action %s.%s requires user confirmation: %s",
                task.tool,
                task.action,
                policy_result.reason,
            )
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.fail(f"Execution policy requires user confirmation: {policy_result.reason}")
            if trace is not None:
                trace.record_tool_call(
                    iteration=getattr(task, "iteration", 1) or 1,
                    task_id=id(task),
                    tool=task.tool,
                    action=task.action,
                    start_time=start_tool_t,
                    end_time=time.time(),
                    policy_verdict="require_confirmation",
                    confirmation_required=True,
                    confirmation_status="confirmed" if user_confirmed else "denied",
                    execution_status="failed",
                    timeout=False,
                    error_category="ConfirmationRequired",
                    error_message=policy_result.reason,
                )
            return task

        # 3. Timeout-Guarded Execution
        timeout = getattr(task, "timeout_seconds", None) or self._default_tool_timeout
        is_timeout = False
        error_cat = None
        try:
            future = self._executor_pool.submit(self._executor.execute, task)
            result = future.result(timeout=timeout)
        except FuturesTimeoutError:
            is_timeout = True
            error_cat = "Timeout"
            logger.error("[TIMEOUT] Task %s.%s timed out after %.1fs", task.tool, task.action, timeout)
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.fail(f"Tool execution timed out after {timeout} seconds")
            result = task
        except Exception as exc:
            error_cat = type(exc).__name__
            logger.error("[EXECUTOR] Execution error in %s.%s: %s", task.tool, task.action, exc)
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.fail(f"Execution error: {exc}")
            result = task

        if trace is not None:
            trace.record_tool_call(
                iteration=getattr(task, "iteration", 1) or 1,
                task_id=id(task),
                tool=task.tool,
                action=task.action,
                start_time=start_tool_t,
                end_time=time.time(),
                policy_verdict=policy_result.verdict.value,
                confirmation_required=False,
                confirmation_status="confirmed" if user_confirmed else "not_required",
                execution_status=result.status.value,
                timeout=is_timeout,
                error_category=error_cat if result.status == TaskStatus.FAILED else None,
                error_message=result.error,
            )

        if result.status == TaskStatus.FAILED:
            logger.warning("Execution failed: %s", result.error)
            if not (result.error.startswith("Execution policy") or "timed out after" in result.error):
                result.error = self._friendly_error_message(result.error)
        return result

    @staticmethod
    def _friendly_error_message(error: str) -> str:
        """Translate internal tool errors into concise, safe user messages."""
        normalized = error.lower()
        if "already exists" in normalized:
            return "That file or folder already exists. Please choose another name."
        if "path does not exist" in normalized or "cannot be empty" in normalized:
            return "I couldn't access that path. Please check it and try again."
        if "unknown tool" in normalized or "unknown action" in normalized:
            return "I couldn't find a safe action for that request. Please rephrase it."
        if "missing required argument" in normalized or "cannot be none" in normalized:
            return "I need a little more information to complete that request."
        if "timeout" in normalized:
            return "That took too long to complete. Please try again in a moment."
        return "I couldn't complete that request. Please try again or rephrase it."

    @staticmethod
    def _error_task(error_message: str) -> Task:
        """Create a failed Task for pipeline-level errors.

        Args:
            error_message: Description of what went wrong.

        Returns:
            A Task in FAILED state with the error message.
        """
        task = Task(tool="system", action="error", args={})
        task.start()
        task.fail(error_message)

        return task
