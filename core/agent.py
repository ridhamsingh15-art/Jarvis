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
from typing import TYPE_CHECKING

from core.exceptions import JarvisError
from core.executor import Executor
from core.planner import Planner
from core.task import Task, TaskStatus
from core.validator import Validator
from core.execution_summary import ExecutionSummary

if TYPE_CHECKING:
    from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)
_MEMORY_FAILURES = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


import re
import time

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
        
        
        # Fast Intent Router — Stage 1 deterministic, Stage 2 optional LLM for ambiguous inputs
        self._intent_classifier = IntentClassifier(llm_client=llm_client)
        
        # Degradation flags
        self._semantic_search_disabled = False
        self._last_execution_summary: ExecutionSummary | None = None

    @property
    def last_execution_summary(self) -> ExecutionSummary | None:
        """Return the ExecutionSummary from the most recent run() execution."""
        return self._last_execution_summary

    def run(
        self,
        user_input: str,
        on_action: Callable[[str], None] | None = None,
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

        Returns:
            List of Task objects with status, result, and errors.
        """
        req_id = f"req_{int(time.time() * 1000) % 1000000}"
        logger.info("[REQUEST] %s (id=%s)", user_input, req_id)
        start_time = time.time()
        tasks: list[Task] = []
        timings: dict[str, float] = {}
        llm_calls = 0
        tool_action: str | None = None
        executive_brain_used = False
        reasoning_loop_used = False
        mission_control_used = False

        # Signal interactive foreground request to knowledge scheduler
        KnowledgeScheduler.set_interactive_active(True)
        try:
            # Direct inspection command: "jarvis models" or "models"
            if user_input.strip().lower() in {"jarvis models", "models", ":models"}:
                from core.model_manager import ModelManager
                table = ModelManager().format_models_table()
                return [Task(tool="system", action="respond", args={"message": table})]

            # 1. Classification
            logger.info('[REQUEST] "%s"', user_input)
            t0 = time.time()
            intent = self._intent_classifier.classify(user_input)
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
                    response = self._cognitive_manager.process_fast(user_input, intent="chat")
                    llm_calls += 1
                    
                    if response.type == "ACTION" and response.tool and response.action:
                        tool_action = f"{response.tool}.{response.action}"
                        tasks = [
                            Task(tool="system", action="respond", args={"message": response.message}),
                            Task(tool=response.tool, action=response.action, args=response.parameters or {}),
                        ]
                    elif response.type == "PLAN":
                        executive_brain_used = True
                        reasoning_loop_used = True
                        mission_control_used = True
                        logger.info("[PIPELINE] Escalating Conversation to Mission")
                        logger.info("[ExecutiveBrain] ENABLED")
                        logger.info("[ReasoningLoop] ENABLED")
                        logger.info("[MissionControl] ENABLED")
                        tasks = self._handle_mission(user_input, context_str)
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
                elif recall_match:
                    key = recall_match.group(1).strip().lower()
                    val = self._memory.recall_fact(key) if self._memory else None
                    if val:
                        msg = f"Your {key} is {val}."
                        tasks = [Task(tool="system", action="respond", args={"message": msg})]
                        timings["LLM"] = 0.0
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
                    response = self._cognitive_manager.process_fast(user_input, intent="tool")
                    llm_calls += 1
                    if response.type == "ACTION" and response.tool and response.action:
                        tool_action = f"{response.tool}.{response.action}"
                        tasks = [
                            Task(tool="system", action="respond", args={"message": response.message}),
                            Task(tool=response.tool, action=response.action, args=response.parameters or {}),
                        ]
                    else:
                        # 1. Try registry-driven resolution (covers any registered tool)
                        resolved = (
                            self._tool_intelligence.resolve_from_registry(user_input)
                            if self._tool_intelligence else None
                        ) or self._resolve_direct_tool(user_input)
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
                logger.info("[ExecutiveBrain] ENABLED")
                logger.info("[ReasoningLoop] ENABLED")
                logger.info("[MissionControl] ENABLED")
                executive_brain_used = True
                reasoning_loop_used = True
                mission_control_used = True
                t0 = time.time()
                tasks = self._handle_mission(user_input, context_str)
                timings["Planning"] = time.time() - t0
                timings["Reasoning"] = timings["Planning"]
                timings["LLM"] = 0.0

            pipeline_latency = time.time() - pipeline_t0

            # 4. Execution
            t0 = time.time()
            # Separate executable tools from internal response/conclusion tasks.
            # Execute valid tools first according to agent loop, then process response/conclusion.
            exec_tasks = [t for t in tasks if not (t.tool == "system" and t.action == "respond")]
            resp_tasks = [t for t in tasks if (t.tool == "system" and t.action == "respond")]

            results_by_id: dict[int, Task] = {}
            for task in exec_tasks:
                if on_action is not None:
                    on_action(self._action_announcement(task))
                res = self._process_task(task)
                results_by_id[id(task)] = res
                if not tool_action:
                    tool_action = f"{res.tool}.{res.action}"

            # Phase 6: Build ExecutionSummary from executed non-system tools
            executed_tools = [results_by_id.get(id(t), t) for t in exec_tasks]
            summary = ExecutionSummary.from_tasks(executed_tools)
            self._last_execution_summary = summary

            for task in resp_tasks:
                try:
                    res = self._process_task(task, execution_summary=summary)
                except TypeError:
                    res = self._process_task(task)
                results_by_id[id(task)] = res

            results: list[Task] = [results_by_id.get(id(t), t) for t in tasks]
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
            KnowledgeScheduler.set_interactive_active(False)


    def _handle_mission(self, user_input: str, context_str: str) -> list[Task]:
        """Handles complex autonomous missions using the full reasoning loop."""
        tasks = []
        if self._capability_manager:
            # New Intelligent Capability Routing flow
            try:
                plan, profile = self._capability_manager.route(user_input)
                logger.info("Capability Plan: %s (Model: %s)", plan.required_capabilities, profile.name)
                
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
            if not self._cognitive_manager:
                try:
                    tasks = self._planner.plan(user_input, context=self._load_context())
                except JarvisError as exc:
                    logger.error("Planning failed: %s", exc)
                    tasks = [self._error_task("I couldn't plan that request just now.")]
            else:
                response = self._cognitive_manager.process(user_input)
                
                if response.type == "RESPONSE":
                    tasks = [Task(tool="system", action="respond", args={"message": response.message})]
                elif response.type == "ACTION":
                    tool = response.tool or "windows"
                    action = response.action or "open_app"
                    parameters = response.parameters or {}
                    tasks = [
                        Task(tool="system", action="respond", args={"message": response.message}),
                        Task(tool=tool, action=action, args=parameters)
                    ]
                else:
                    try:
                        plan_tasks = self._planner.plan(user_input, context=self._load_context())
                        tasks = [Task(tool="system", action="respond", args={"message": response.message})] + plan_tasks
                    except JarvisError as exc:
                        tasks = [self._error_task("I couldn't plan that request just now. Please try again.")]
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
    def _resolve_direct_tool(user_input: str) -> tuple[str, str, dict] | None:
        """Deterministically resolves common OS and tool actions if LLM returns plain text."""
        lower = user_input.lower().strip()
        # Calculator
        if "calc" in lower or "calculator" in lower:
            return "windows", "open_app", {"app": "calculator"}
        # Notepad
        if "notepad" in lower:
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
    ) -> Task:
        """Validate and execute a single task.

        Args:
            task: A Task in PENDING state.
            execution_summary: Optional ExecutionSummary to ground response tasks.

        Returns:
            The Task with updated status after execution.
        """
        # Handle conversational responses from the LLM directly —
        # these don't go through validation or execution.
        if task.tool == "system" and task.action == "respond":
            raw_msg = (
                task.args.get("message")
                or task.args.get("content")
                or task.args.get("response")
                or task.args.get("text")
                or ""
            )
            initial_claim = str(raw_msg)
            if execution_summary is not None and execution_summary.total_tasks > 0:
                final_message = execution_summary.ground_response(initial_claim)
            else:
                final_message = initial_claim

            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.complete(final_message)
            return task

        try:
            if self._tool_intelligence:
                task = self._tool_intelligence.process(task)
            else:
                self._validator.validate(task)
        except JarvisError as exc:
            logger.warning("Validation failed: %s", exc)
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                task.start()
            task.fail(self._friendly_error_message(str(exc)))
            return task

        result = self._executor.execute(task)
        if result.status == TaskStatus.FAILED:
            logger.warning("Execution failed: %s", result.error)
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
