import threading

import pytest

from core.di import (
    CircularDependencyError,
    Container,
    ContainerSealedError,
    DependencyResolutionError,
    ServiceLifetime,
)


# Dummy interfaces and classes for testing
class ILogger: pass
class IConfig: pass
class IDatabase: pass

class ConsoleLogger(ILogger): pass

class Config(IConfig):
    def __init__(self, logger: ILogger):
        self.logger = logger

class Database(IDatabase):
    def __init__(self, config: IConfig, logger: ILogger):
        self.config = config
        self.logger = logger

def test_transient_resolution():
    container = Container()
    container.register_transient(ILogger, ConsoleLogger)
    container.register_transient(IConfig, Config)
    container.seal()
    
    config1 = container.resolve(IConfig)
    config2 = container.resolve(IConfig)
    
    # Transient should return new instances
    assert config1 is not config2
    assert isinstance(config1.logger, ConsoleLogger)


def test_singleton_resolution():
    container = Container()
    container.register_singleton(ILogger, ConsoleLogger)
    container.register_singleton(IConfig, Config)
    container.seal()
    
    config1 = container.resolve(IConfig)
    config2 = container.resolve(IConfig)
    
    # Singleton should return the exact same instance
    assert config1 is config2
    assert config1.logger is config2.logger
    
    # Direct logger resolution should be the same as injected logger
    direct_logger = container.resolve(ILogger)
    assert direct_logger is config1.logger


def test_scoped_resolution():
    container = Container()
    container.register_scoped(ILogger, ConsoleLogger)
    container.seal()
    
    with container.create_scope() as scope1:
        log1 = scope1.resolve(ILogger)
        log2 = scope1.resolve(ILogger)
        assert log1 is log2 # Same instance within the scope
        
    with container.create_scope() as scope2:
        log3 = scope2.resolve(ILogger)
        assert log3 is not log1 # Different instance across scopes
        
    with pytest.raises(DependencyResolutionError):
        # Resolving a scoped service without a scope throws
        container.resolve(ILogger)


def test_circular_dependency_validation():
    class A: pass
    class B: pass
    class C: pass
    
    A.__init__ = lambda self, b: None
    A.__init__.__annotations__ = {'b': B}
    B.__init__ = lambda self, c: None
    B.__init__.__annotations__ = {'c': C}
    C.__init__ = lambda self, a: None
    C.__init__.__annotations__ = {'a': A}
    
    container = Container()
    container.register_transient(A, A)
    container.register_transient(B, B)
    container.register_transient(C, C)
    
    with pytest.raises(CircularDependencyError) as exc:
        container.seal()
        
    assert "Circular dependency detected" in str(exc.value)


def test_missing_dependency_validation():
    container = Container()
    container.register_transient(IConfig, Config)
    # ILogger is missing
    
    with pytest.raises(DependencyResolutionError):
        container.seal()


def test_seal_prevents_mutation():
    container = Container()
    container.seal()
    
    with pytest.raises(ContainerSealedError):
        container.register_transient(ILogger, ConsoleLogger)


def test_factory_registration():
    container = Container()
    
    def config_factory(logger: ILogger) -> IConfig:
        return Config(logger)
        
    container.register_singleton(ILogger, ConsoleLogger)
    container.register_factory(IConfig, config_factory, ServiceLifetime.SINGLETON)
    container.seal()
    
    config = container.resolve(IConfig)
    assert isinstance(config, Config)
    assert isinstance(config.logger, ConsoleLogger)


def test_thread_safe_singleton():
    container = Container()
    
    class SlowSingleton:
        instance_count = 0
        def __init__(self):
            import time
            time.sleep(0.1) # Simulate slow initialization
            SlowSingleton.instance_count += 1
            
    container.register_singleton(SlowSingleton, SlowSingleton)
    container.seal()
    
    # Resolve concurrently
    threads = []
    results = []
    
    def worker():
        results.append(container.resolve(SlowSingleton))
        
    for _ in range(10):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # All threads should receive the exact same object despite the slow initialization gap
    assert SlowSingleton.instance_count == 1
    assert len({id(r) for r in results}) == 1
