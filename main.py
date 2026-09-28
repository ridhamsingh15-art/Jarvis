"""
Jarvis — Local AI Operating System.

Entry point that wires up all components and launches the
PySide6 desktop GUI by default, or the terminal REPL with --cli.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import NamedTuple, Any

from config.config import load_config
from core.agent import Agent
from core.planner import Planner
from core.registry import Registry
from core.task import TaskStatus
from core.validator import Validator
from memory.memory_manager import MemoryManager
from memory.sqlite_memory import SqliteMemory
from tools.base_tool import BaseTool
from tools.browser import BrowserTool
from tools.file import FileTool
from tools.windows import WindowsTool

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure structured logging for the framework."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Domain builder return types ───────────────────────────────────────────────

class InfraContext(NamedTuple):
    registry: Registry
    gateway: Any          # ModelRouter
    action_registry: Any  # ActionRegistry
    executor: Any         # ExecutionEngine
    planner: Planner
    validator: Validator
    event_bus: Any        # EventBus
    llm_client: Any       # LLMClient
    identity: Any         # IdentityManager


class MemoryContext(NamedTuple):
    sqlite_memory: SqliteMemory
    memory_manager: MemoryManager
    knowledge_manager: Any   # KnowledgeManager
    mission_manager: Any     # MissionManager


class ContentContext(NamedTuple):
    n8n_manager: Any
    script_manager: Any
    sb_manager: Any
    project_manager: Any
    image_manager: Any
    animation_manager: Any
    voice_manager: Any
    video_manager: Any
    music_manager: Any
    subtitle_manager: Any
    thumbnail_manager: Any
    seo_manager: Any
    publishing_manager: Any
    analytics_manager: Any


class CognitionContext(NamedTuple):
    cognitive_manager: Any        # CognitiveManager
    tool_intelligence: Any        # ToolIntelligenceManager
    capability_manager: Any       # CapabilityManager


# ── Sub-builders ──────────────────────────────────────────────────────────────

def _build_infra(config) -> InfraContext:
    """Build core infrastructure: registry, router, executor, event bus."""
    from config.model_config import ModelRouterConfig
    from core.executor.action_registry import ActionRegistry
    from core.executor.executor import ExecutionEngine
    from core.model_router import ModelRouter
    from core.identity.manager import IdentityManager
    from core.llm import LLMClient
    from core.telemetry.levels import LogLevel
    from core.telemetry.logger import AsyncLogger
    from core.events.bus import EventBus
    from providers.fallback_manager import FallbackManager
    from providers.health_monitor import HealthMonitor
    from providers.provider_factory import ProviderFactory
    from providers.provider_registry import ProviderRegistry
    from providers.selection_policy import WeightedScorePolicy
    from unittest.mock import MagicMock

    # Tools
    windows_tool = WindowsTool()
    browser_tool = BrowserTool()
    file_tool = FileTool()

    registry = Registry()
    registry.register(windows_tool)
    registry.register(browser_tool)
    registry.register(file_tool)

    # Provider / model router
    logger.info("Selected provider: %s", config.provider)
    logger.info("Selected model: %s", config.model)
    provider_config = {
        "default_model": config.model,
        "default_embedding_model": config.embedding_model,
        "timeout_seconds": config.request_timeout,
        "max_retries": config.max_retries,
        "retry_backoff_seconds": config.retry_backoff_seconds,
        "models": config.get_role_models(),
    }
    if config.provider == "ollama":
        provider_config["base_url"] = config.ollama_host

    provider = ProviderFactory.create_provider(config.provider, config=provider_config)
    health_monitor = HealthMonitor()
    provider_registry = ProviderRegistry(health_monitor)
    provider_registry.register(provider)

    gateway = ModelRouter(
        config=ModelRouterConfig(prefer_local=True),
        registry=provider_registry,
        selection_policy=WeightedScorePolicy(health_monitor),
        fallback_manager=FallbackManager(),
        health_monitor=health_monitor,
    )

    # Action registry + executor
    action_registry = ActionRegistry()
    for tool_name in registry.list_tools():
        tool = registry.get(tool_name)
        if tool is not None:
            for action_name in tool.get_actions():
                def _make_handler(t: BaseTool, a: str):
                    def handler(_context, **kwargs):
                        return t.execute(a, kwargs)
                    return handler
                action_registry.register(action_name, _make_handler(tool, action_name))
                logger.debug("Bridged action: %s.%s", tool_name, action_name)

    action_count = sum(
        len(t.get_actions())
        for t in (registry.get(name) for name in registry.list_tools())
        if t is not None
    )
    logger.info("Registered %d tool actions into executor", action_count)

    executor = ExecutionEngine(action_registry)

    # Identity / planner / validator
    identity = IdentityManager(
        active_model=config.model,
        active_provider=config.provider,
    )
    planner = Planner(gateway, registry, identity=identity)
    validator = Validator(registry)

    # Event bus
    dummy_masker = MagicMock()
    dummy_masker.mask.side_effect = lambda x: x
    async_logger = AsyncLogger(level=LogLevel.INFO, masker=dummy_masker, outputs=[])
    event_bus = EventBus(logger=async_logger)

    llm_client = LLMClient(config)

    return InfraContext(
        registry=registry,
        gateway=gateway,
        action_registry=action_registry,
        executor=executor,
        planner=planner,
        validator=validator,
        event_bus=event_bus,
        llm_client=llm_client,
        identity=identity,
    )


def _build_memory_stack(config, infra: InfraContext) -> MemoryContext:
    """Build SQLite memory, MemoryManager, KnowledgeManager, MissionManager."""
    from core.knowledge.indexer.manager import KnowledgeManager
    from core.mission.manager import MissionManager
    from core.mission.repository import SqliteMissionRepository

    sqlite_memory = SqliteMemory(config.memory_db_path)
    memory_manager = MemoryManager(sqlite_memory)

    knowledge_manager = KnowledgeManager(config, infra.llm_client, infra.event_bus)
    knowledge_manager.start_background_indexing()

    mission_repo = SqliteMissionRepository(sqlite_memory.get_connection)
    mission_manager = MissionManager(mission_repo, infra.event_bus)

    return MemoryContext(
        sqlite_memory=sqlite_memory,
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        mission_manager=mission_manager,
    )


def _build_content_factory(infra: InfraContext, mem: MemoryContext) -> ContentContext:
    """Build all Content Factory engines and integration managers."""
    from applications.content_factory.image_engine.asset_pipeline import AssetPipeline
    from applications.content_factory.image_engine.manager import ImageEngineManager
    from applications.content_factory.image_engine.planner import ImageGenerationPlanner
    from applications.content_factory.image_engine.quality import ImageQualityEvaluator
    from applications.content_factory.image_engine.renderer import ImageRenderer
    from applications.content_factory.image_engine.scheduler import GenerationScheduler
    from applications.content_factory.image_engine.telemetry import ImageEngineTelemetry
    from applications.content_factory.image_engine.validator import (
        ImageValidator as ImageEngineValidator,
    )

    from applications.content_factory.consistency_engine.manager import ConsistencyEngineManager
    from applications.content_factory.consistency_engine.registry import ConsistencyRegistry
    from applications.content_factory.consistency_engine.character_library import CharacterLibrary
    from applications.content_factory.consistency_engine.environment_library import EnvironmentLibrary
    from applications.content_factory.consistency_engine.object_library import ObjectLibrary
    from applications.content_factory.consistency_engine.asset_matcher import AssetMatcher
    from applications.content_factory.consistency_engine.prompt_enricher import PromptEnricher
    from applications.content_factory.consistency_engine.telemetry import ConsistencyTelemetry
    from applications.content_factory.consistency_engine.validator import ProfileValidator

    from applications.content_factory.animation_engine.manager import AnimationEngineManager
    from applications.content_factory.animation_engine.planner import AnimationGenerationPlanner
    from applications.content_factory.animation_engine.scheduler import AnimationScheduler
    from applications.content_factory.animation_engine.asset_pipeline import AnimationAssetPipeline
    from applications.content_factory.animation_engine.renderer import AnimationRenderer
    from applications.content_factory.animation_engine.quality import AnimationQualityEvaluator
    from applications.content_factory.animation_engine.validator import AnimationValidator
    from applications.content_factory.animation_engine.telemetry import AnimationEngineTelemetry

    from applications.content_factory.voice_engine.manager import VoiceEngineManager
    from applications.content_factory.voice_engine.planner import VoiceGenerationPlanner
    from applications.content_factory.voice_engine.scheduler import VoiceScheduler
    from applications.content_factory.voice_engine.asset_pipeline import VoiceAssetPipeline
    from applications.content_factory.voice_engine.renderer import VoiceRenderer
    from applications.content_factory.voice_engine.quality import VoiceQualityEvaluator
    from applications.content_factory.voice_engine.validator import VoiceValidator
    from applications.content_factory.voice_engine.telemetry import VoiceEngineTelemetry

    from applications.content_factory.video_engine.manager import VideoEngineManager
    from applications.content_factory.video_engine.planner import VideoGenerationPlanner
    from applications.content_factory.video_engine.timeline import TimelineBuilder
    from applications.content_factory.video_engine.assembler import SceneSequencer
    from applications.content_factory.video_engine.ffmpeg_adapter import FFmpegAdapter
    from applications.content_factory.video_engine.renderer import VideoRenderer
    from applications.content_factory.video_engine.validator import VideoValidator
    from applications.content_factory.video_engine.telemetry import VideoEngineTelemetry

    from applications.content_factory.music_engine.manager import MusicEngineManager
    from applications.content_factory.music_engine.planner import MusicGenerationPlanner
    from applications.content_factory.music_engine.generator import MusicGenerator
    from applications.content_factory.music_engine.telemetry import MusicEngineTelemetry

    from applications.content_factory.subtitle_engine.manager import SubtitleEngineManager
    from applications.content_factory.subtitle_engine.planner import SubtitleGenerationPlanner
    from applications.content_factory.subtitle_engine.generator import SubtitleGenerator
    from applications.content_factory.subtitle_engine.telemetry import SubtitleEngineTelemetry

    from applications.content_factory.thumbnail_engine.manager import ThumbnailEngineManager
    from applications.content_factory.thumbnail_engine.planner import ThumbnailGenerationPlanner
    from applications.content_factory.thumbnail_engine.generator import ThumbnailGenerator
    from applications.content_factory.thumbnail_engine.telemetry import ThumbnailEngineTelemetry

    from applications.content_factory.seo_engine.manager import SEOEngineManager
    from applications.content_factory.seo_engine.planner import SEOGenerationPlanner
    from applications.content_factory.seo_engine.generator import SEOGenerator
    from applications.content_factory.seo_engine.telemetry import SEOEngineTelemetry

    from applications.content_factory.publishing_engine.manager import PublishingEngineManager
    from applications.content_factory.publishing_engine.planner import PublishingPlanner
    from applications.content_factory.publishing_engine.adapter import PublishingAdapter
    from applications.content_factory.publishing_engine.telemetry import PublishingEngineTelemetry

    from applications.content_factory.analytics_engine.manager import AnalyticsEngineManager
    from applications.content_factory.analytics_engine.planner import AnalyticsPlanner
    from applications.content_factory.analytics_engine.tracker import AnalyticsTracker
    from applications.content_factory.analytics_engine.telemetry import AnalyticsEngineTelemetry

    from applications.content_factory.project.asset_manager import AssetManager
    from applications.content_factory.project.manager import ProjectManager
    from applications.content_factory.project.registry import ProjectRegistry
    from applications.content_factory.project.storage import ProjectStorage
    from applications.content_factory.project.telemetry import ProjectManagerTelemetry
    from applications.content_factory.project.validator import ProjectValidator
    from applications.content_factory.script_engine.generator import ScriptGenerator
    from applications.content_factory.script_engine.manager import ScriptEngineManager
    from applications.content_factory.script_engine.planner import ScriptPlanner
    from applications.content_factory.script_engine.telemetry import ScriptEngineTelemetry
    from applications.content_factory.storyboard_engine.generator import StoryboardGenerator
    from applications.content_factory.storyboard_engine.manager import StoryboardEngineManager
    from applications.content_factory.storyboard_engine.planner import StoryboardPlanner
    from applications.content_factory.storyboard_engine.telemetry import StoryboardEngineTelemetry

    from core.integrations.n8n.capability import N8nCapabilityManager
    from core.integrations.n8n.client import N8nClient
    from core.integrations.n8n.installer import N8nInstaller
    from core.integrations.n8n.telemetry import N8nTelemetry
    from core.integrations.n8n.workflow_registry import N8nWorkflowRegistry
    from core.integrations.n8n.workflow_runner import N8nWorkflowRunner
    from config.config import load_config as _lc
    config = _lc()

    # n8n
    n8n_client = N8nClient(config)
    n8n_telemetry = N8nTelemetry(infra.event_bus)
    n8n_installer = N8nInstaller(config, infra.event_bus)
    n8n_registry = N8nWorkflowRegistry()
    n8n_runner = N8nWorkflowRunner(n8n_client, mem.mission_manager, n8n_telemetry)
    n8n_manager = N8nCapabilityManager(n8n_installer, n8n_registry, n8n_runner)

    # Script / Storyboard
    script_generator = ScriptGenerator(infra.gateway)
    script_planner = ScriptPlanner(script_generator, ScriptEngineTelemetry(infra.event_bus))
    script_manager = ScriptEngineManager(script_planner, mem.mission_manager)

    sb_generator = StoryboardGenerator(infra.gateway)
    sb_planner = StoryboardPlanner(sb_generator, StoryboardEngineTelemetry(infra.event_bus))
    sb_manager = StoryboardEngineManager(sb_planner, mem.mission_manager)

    # Project Manager
    workspace_dir = Path(config.memory_db_path).parent
    pm_storage = ProjectStorage(root_dir=str(workspace_dir / "projects"))
    pm_registry = ProjectRegistry(pm_storage)
    pm_asset_manager = AssetManager(pm_storage)
    pm_validator = ProjectValidator(pm_storage)
    pm_telemetry = ProjectManagerTelemetry(infra.event_bus)
    project_manager = ProjectManager(pm_storage, pm_registry, pm_asset_manager, pm_validator, pm_telemetry)

    # Consistency Engine
    ce_registry = ConsistencyRegistry()
    ce_validator = ProfileValidator()
    ce_telemetry = ConsistencyTelemetry(infra.event_bus)
    char_library = CharacterLibrary(ce_registry, ce_validator, ce_telemetry)
    env_library = EnvironmentLibrary(ce_registry, ce_validator, ce_telemetry)
    obj_library = ObjectLibrary(ce_registry, ce_validator, ce_telemetry)
    asset_matcher = AssetMatcher(ce_registry)
    prompt_enricher = PromptEnricher()
    consistency_manager = ConsistencyEngineManager(
        char_library, env_library, obj_library, asset_matcher, prompt_enricher, ce_telemetry
    )

    # Image
    image_manager = ImageEngineManager(
        ImageGenerationPlanner(
            ImageRenderer(), ImageQualityEvaluator(), ImageEngineValidator(),
            AssetPipeline(project_manager), GenerationScheduler(max_workers=2),
            ImageEngineTelemetry(infra.event_bus),
            consistency_engine=consistency_manager, max_retries=1,
        ),
        mem.mission_manager, project_manager,
    )

    # Animation
    animation_manager = AnimationEngineManager(
        AnimationGenerationPlanner(
            AnimationRenderer(), AnimationQualityEvaluator(), AnimationValidator(),
            AnimationAssetPipeline(project_manager), AnimationScheduler(max_workers=2),
            AnimationEngineTelemetry(infra.event_bus), max_retries=1,
        ),
        mem.mission_manager, project_manager,
    )

    # Voice
    voice_manager = VoiceEngineManager(
        VoiceGenerationPlanner(
            VoiceRenderer(), VoiceQualityEvaluator(), VoiceValidator(),
            VoiceAssetPipeline(project_manager), VoiceScheduler(max_workers=4),
            VoiceEngineTelemetry(infra.event_bus), max_retries=1,
        ),
        mem.mission_manager, project_manager,
    )

    # Video
    video_timeline = TimelineBuilder(project_manager)
    video_manager = VideoEngineManager(
        VideoGenerationPlanner(
            VideoRenderer(FFmpegAdapter()), SceneSequencer(video_timeline),
            VideoValidator(), project_manager, VideoEngineTelemetry(infra.event_bus),
        ),
        mem.mission_manager, project_manager,
    )

    # Post-production
    music_manager = MusicEngineManager(
        MusicGenerationPlanner(MusicGenerator(), project_manager, MusicEngineTelemetry(infra.event_bus)),
        mem.mission_manager, project_manager,
    )
    subtitle_manager = SubtitleEngineManager(
        SubtitleGenerationPlanner(SubtitleGenerator(), project_manager, SubtitleEngineTelemetry(infra.event_bus)),
        mem.mission_manager, project_manager,
    )
    thumbnail_manager = ThumbnailEngineManager(
        ThumbnailGenerationPlanner(ThumbnailGenerator(), project_manager, ThumbnailEngineTelemetry(infra.event_bus)),
        mem.mission_manager, project_manager,
    )
    seo_manager = SEOEngineManager(
        SEOGenerationPlanner(SEOGenerator(), project_manager, SEOEngineTelemetry(infra.event_bus)),
        mem.mission_manager, project_manager,
    )
    publishing_manager = PublishingEngineManager(
        PublishingPlanner(PublishingAdapter(n8n_runner), project_manager, PublishingEngineTelemetry(infra.event_bus)),
        mem.mission_manager, project_manager,
    )
    analytics_manager = AnalyticsEngineManager(
        AnalyticsPlanner(AnalyticsTracker(), project_manager, AnalyticsEngineTelemetry(infra.event_bus)),
        mem.mission_manager, project_manager,
    )

    return ContentContext(
        n8n_manager=n8n_manager,
        script_manager=script_manager,
        sb_manager=sb_manager,
        project_manager=project_manager,
        image_manager=image_manager,
        animation_manager=animation_manager,
        voice_manager=voice_manager,
        video_manager=video_manager,
        music_manager=music_manager,
        subtitle_manager=subtitle_manager,
        thumbnail_manager=thumbnail_manager,
        seo_manager=seo_manager,
        publishing_manager=publishing_manager,
        analytics_manager=analytics_manager,
    )


def _build_cognition_stack(infra: InfraContext, mem: MemoryContext, content: ContentContext) -> CognitionContext:
    """Build CognitiveManager, ToolIntelligence, and CapabilityManager."""
    from core.capability import (
        Capability, CapabilityManager, CapabilityType, CostTier, LatencyTier, ModelProfile,
    )
    from core.cognition.context import ShortTermContext
    from core.cognition.conversation import ConversationEngine
    from core.cognition.manager import CognitiveManager
    from core.cognition.reflection import CognitiveReflection
    from core.cognition.retrieval import MemoryRetriever
    from core.cognition.workspace_provider import WorkspaceProvider
    from core.cognition.mission_provider import MissionProvider
    from core.cognition.project_provider import ProjectProvider
    from core.cognition.tool_provider import ToolProvider
    from core.cognition.context_orchestrator import ContextOrchestrator
    from core.executive.manager import ExecutiveBrain
    from core.tool_intelligence import ToolIntelligenceManager

    # Context providers
    memory_retriever = MemoryRetriever(infra.llm_client, mem.memory_manager, mem.knowledge_manager)
    context_orchestrator = ContextOrchestrator(
        workspace_provider=WorkspaceProvider(),
        mission_provider=MissionProvider(mem.mission_manager),
        project_provider=ProjectProvider(content.project_manager),
        tool_provider=ToolProvider(infra.registry),
        memory_retriever=memory_retriever,
    )

    executive_brain = ExecutiveBrain(llm_client=infra.llm_client, registry=infra.registry, event_bus=infra.event_bus)

    engine = ConversationEngine(infra.gateway, infra.registry, identity=infra.identity)
    context = ShortTermContext()
    reflection = CognitiveReflection(event_bus=infra.event_bus, llm_client=infra.llm_client, memory_manager=mem.memory_manager)

    cognitive_manager = CognitiveManager(
        conversation_engine=engine,
        reflection=reflection,
        context_orchestrator=context_orchestrator,
        executive_brain=executive_brain,
        context=context,
        event_bus=infra.event_bus,
    )

    tool_intelligence = ToolIntelligenceManager(
        registry=infra.registry,
        core_validator=infra.validator,
        event_bus=infra.event_bus,
    )

    # Capability Router
    qwen_profile = ModelProfile(
        name="qwen3:8b", provider="ollama", reasoning=7, coding=6,
        vision=False, voice=False, multimodal=False,
        context_length=32000, cost=CostTier.FREE, latency=LatencyTier.FAST,
        privacy_local=True,
    )
    capability_manager = CapabilityManager(
        model_router=infra.gateway,
        event_bus=infra.event_bus,
        model_profiles=[qwen_profile],
    )

    # Register tools and capabilities
    for tool_name in infra.registry.list_tools():
        capability_manager.register_capability(
            Capability(name=tool_name, description=infra.registry.get(tool_name).description, type=CapabilityType.TOOL)
        )
    capability_manager.register_capability(Capability(name="memory", description="Long-term user conversation memory", type=CapabilityType.CORE))
    capability_manager.register_capability(Capability(name="planner", description="Multi-step reasoning and execution planner", type=CapabilityType.CORE))
    capability_manager.register_capability(Capability(name="knowledge", description="Personal Knowledge Index for searching user files", type=CapabilityType.CORE))
    capability_manager.register_capability(content.n8n_manager.get_capability_metadata())
    capability_manager.register_capability(content.script_manager.get_capability_metadata())
    capability_manager.register_capability(content.sb_manager.get_capability_metadata())
    capability_manager.register_capability(content.project_manager.get_capability_metadata())
    capability_manager.register_capability(content.image_manager.get_capability_metadata())
    capability_manager.register_capability(content.animation_manager.get_capability_metadata())
    capability_manager.register_capability(content.voice_manager.get_capability_metadata())
    capability_manager.register_capability(content.video_manager.get_capability_metadata())
    capability_manager.register_capability(content.music_manager.get_capability_metadata())
    capability_manager.register_capability(content.subtitle_manager.get_capability_metadata())
    capability_manager.register_capability(content.thumbnail_manager.get_capability_metadata())
    capability_manager.register_capability(content.seo_manager.get_capability_metadata())
    capability_manager.register_capability(content.publishing_manager.get_capability_metadata())
    capability_manager.register_capability(content.analytics_manager.get_capability_metadata())

    return CognitionContext(
        cognitive_manager=cognitive_manager,
        tool_intelligence=tool_intelligence,
        capability_manager=capability_manager,
    )


# ── Top-level assembler ────────────────────────────────────────────────────────

def build_agent() -> dict:
    """Wire up all components and return agent + context.

    Returns a dict with:
        agent: Fully constructed Agent instance.
        config: JarvisConfig (for display purposes).
        registry: Registry (for read-only tool listing).
        memory: SqliteMemory (for read-only memory browsing).
        model_name: Display string for the current model.
        memory_backend: Display string for the memory backend.
        tool_count: Number of registered tools.

    Dependency graph:
        config → infra → memory → content → cognition → Agent
    """
    config = load_config()

    infra   = _build_infra(config)
    mem     = _build_memory_stack(config, infra)
    content = _build_content_factory(infra, mem)
    cog     = _build_cognition_stack(infra, mem, content)

    agent = Agent(
        infra.planner,
        infra.validator,
        infra.executor,
        memory=mem.memory_manager,
        cognitive_manager=cog.cognitive_manager,
        tool_intelligence=cog.tool_intelligence,
        capability_manager=cog.capability_manager,
        knowledge_manager=mem.knowledge_manager,
        n8n_manager=content.n8n_manager,
        script_engine=content.script_manager,
        storyboard_engine=content.sb_manager,
        project_manager=content.project_manager,
        image_engine=content.image_manager,
        animation_engine=content.animation_manager,
        voice_engine=content.voice_manager,
        video_engine=content.video_manager,
        music_engine=content.music_manager,
        subtitle_engine=content.subtitle_manager,
        thumbnail_engine=content.thumbnail_manager,
        seo_engine=content.seo_manager,
        publishing_engine=content.publishing_manager,
        analytics_engine=content.analytics_manager,
        llm_client=infra.llm_client,
    )

    return {
        "agent": agent,
        "config": config,
        "registry": infra.registry,
        "memory": mem.sqlite_memory,
        "model_name": config.model,
        "memory_backend": "SQLite",
        "tool_count": len(infra.registry.list_tools()),
    }


def display_results(tasks: list) -> None:
    """Display task results to the user."""
    for task in tasks:
        if task.status == TaskStatus.COMPLETED:
            print(f"  [OK] {task.result}")
        elif task.status == TaskStatus.FAILED:
            print(f"  [FAIL] {task.error}")
        else:
            status_display = task.status.value if hasattr(task.status, 'value') else str(task.status)
            print(f"  [?] {task.tool}.{task.action} -- {status_display}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Jarvis — Local AI Operating System")
    parser.add_argument(
        "--cli",
        action="store_true",
        default=False,
        help="Launch the terminal REPL instead of the desktop GUI.",
    )
    parser.add_argument(
        "--models",
        action="store_true",
        default=False,
        help="Display installed and configured AI models and their health status.",
    )
    return parser.parse_args()


def repl(agent: Agent) -> None:
    """Run the interactive terminal REPL."""
    print("\n  JARVIS — Local AI Operating System")
    print("  Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_input = input("  You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye.")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("  Goodbye.")
            sys.exit(0)

        results = agent.run(user_input)
        display_results(results)
        print()


def main() -> None:
    """Entry point — launches GUI by default, REPL with --cli, or models status with --models."""
    setup_logging()
    args = parse_args()

    if args.models:
        from core.model_manager import display_model_status
        display_model_status()
        sys.exit(0)

    from core.model_manager import ModelManager
    config = load_config()
    ModelManager(config).startup_health_check()

    ctx = build_agent()

    if args.cli:
        repl(ctx["agent"])
    else:
        from gui import launch_gui
        launch_gui(ctx["agent"], config_ctx=ctx)


if __name__ == "__main__":
    main()
