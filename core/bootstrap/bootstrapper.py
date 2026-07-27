from core.config import ConfigManager, ConfigSnapshot, EnvConfigProvider, ConfigSchema, ConfigField, DefaultConfigProvider
from core.telemetry import AsyncLogger, create_logger
from core.errors import ErrorHandler, InternalError
from core.di import Container
from core.events import EventBus
from core.models import Event

from .models import StartupResult
from .runtime import Runtime
from .lifecycle import LifecycleManager

class Bootstrap:
    """
    Executes the strict deterministic startup sequence for JARVIS AIOS.
    """
    
    @classmethod
    def start(cls) -> StartupResult:
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
            
            # 6. Validate container
            container.validate()
            logger.info("DI Container validated successfully.")
            
            # 7. Seal container
            container.seal()
            
            # 8. Initialize Event Bus
            event_bus = container.resolve(EventBus)
            
            # 9. Create LifecycleManager and Runtime
            lifecycle = LifecycleManager(container, event_bus, logger)
            runtime = Runtime(container, event_bus, logger, lifecycle)
            
            # 10. Publish SystemStarted
            event_bus.publish(Event(topic="system.started"))
            logger.info("JARVIS AIOS Runtime initialized successfully.")
            
            return StartupResult(success=True, runtime=runtime)
            
        except Exception as e:
            error_msg = f"Bootstrap failed: {str(e)}"
            
            # Isolate via Error Model
            wrapped_error = InternalError(message=error_msg, root_cause=e)
            
            if logger:
                logger.fatal("Bootstrap Failure", error=wrapped_error.to_dict())
                logger.shutdown()
                
            if container:
                try:
                    container.dispose()
                except Exception:
                    pass
                    
            return StartupResult(success=False, error_message=error_msg)
