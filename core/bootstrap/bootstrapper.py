from pathlib import Path

from core.config import (
    ConfigField,
    ConfigManager,
    ConfigSchema,
    ConfigSnapshot,
    DefaultConfigProvider,
    EnvConfigProvider,
)
from core.di import Container
from core.errors import ErrorHandler, InternalError
from core.events import EventBus
from core.models import Event
from core.telemetry import AsyncLogger, create_logger

from .lifecycle import LifecycleManager
from .models import StartupResult
from .runtime import Runtime


class Bootstrap:
    """
    Executes the strict deterministic startup sequence for JARVIS AIOS.
    """
    
    @classmethod
    def start(cls) -> StartupResult:
        # Delay autonomy imports until bootstrap is fully initialized; autonomy
        # implements RuntimeComponent and therefore depends on runtime interfaces.
        from config.config import load_config as load_application_config
        from core.autonomy import (
            AutonomousGoalManager,
            DAGGoalScheduler,
            DefaultGoalEvaluator,
        )
        from core.autonomy.factory import create_autonomous_goal_manager
        from core.autonomy.mission_adapter import (
            CrashSafeGoalStepExecutor,
            ExecutionBackedGoalPlanner,
        )
        from core.registry import Registry
        from tools.browser import BrowserTool
        from tools.codex_desktop import CodexDesktopTool
        from tools.file import FileTool
        from tools.windows import WindowsTool

        logger = None
        container = None
        
        try:
            # 1. Load configuration
            schema = ConfigSchema({
                "log_level": ConfigField(type_=str, default="INFO"),
                "debug": ConfigField(type_=bool, default=False)
            })
            config_manager = ConfigManager(schema)
            config_manager.add_provider(EnvConfigProvider())
            config_manager.add_provider(DefaultConfigProvider({"log_level": "INFO"}))
            config = config_manager.load()
            
            # 2. Initialize logging
            logger = create_logger(config)
            logger.info("Starting JARVIS AIOS Bootstrap sequence...")
            
            # 3. Install global error handling
            ErrorHandler.setup(logger)
            logger.info("Global error handling installed.")
            
            # 4. Create DI container
            container = Container()
            
            # 5. Register Foundation services
            container.register_instance(ConfigSnapshot, config)
            container.register_instance(AsyncLogger, logger)
            container.register_singleton(EventBus, EventBus)

            # 6. Wire the durable autonomy service into the application container.
            # Its agent settings are intentionally loaded from config.config; the
            # Foundation ConfigSnapshot remains responsible for AIOS core settings.
            event_bus = container.resolve(EventBus)
            autonomy_config = load_application_config()
            # Keep the model-visible capability manifest and the crash-safe
            # executor backed by the same explicit registry. Shell remains
            # governed by the dedicated restricted ShellTool and is not added
            # to model-generated plans.
            tool_registry = Registry()
            for tool in (FileTool(workspace_root=Path(__file__).resolve().parents[2]), BrowserTool(), WindowsTool(), CodexDesktopTool()):
                tool_registry.register(tool)
            goal_manager = create_autonomous_goal_manager(
                planner=ExecutionBackedGoalPlanner(tool_registry=tool_registry),
                scheduler=DAGGoalScheduler(),
                evaluator=DefaultGoalEvaluator(),
                event_bus=event_bus,
                logger=logger,
                config=autonomy_config,
                step_executor=CrashSafeGoalStepExecutor(tool_registry=tool_registry),
            )
            container.register_instance(AutonomousGoalManager, goal_manager)
            
            # 7. Validate container
            container.validate()
            logger.info("DI Container validated successfully.")
            
            # 8. Seal container
            container.seal()
            
            # 9. Event Bus is already resolved and shared with autonomy.
            
            # 10. Create LifecycleManager and Runtime
            lifecycle = LifecycleManager(container, event_bus, logger)
            runtime = Runtime(container, event_bus, logger, lifecycle)
            
            # 11. Publish SystemStarted
            event_bus.publish(Event(topic="system.started"))
            logger.info("JARVIS AIOS Runtime initialized successfully.")
            
            return StartupResult(success=True, runtime=runtime)
            
        except Exception as e:  # noqa: BLE001
            error_msg = f"Bootstrap failed: {e!s}"
            
            # Isolate via Error Model
            wrapped_error = InternalError(message=error_msg, root_cause=e)
            
            if logger:
                logger.fatal("Bootstrap Failure", error=wrapped_error.to_dict())
                logger.shutdown()
                
            if container:
                try:
                    container.dispose()
                except Exception:  # noqa: S110, BLE001
                    pass
                    
            return StartupResult(success=False, error_message=error_msg)
