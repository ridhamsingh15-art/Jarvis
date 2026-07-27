import threading
from typing import Any, Callable, Dict, Optional, Type, Set

from .enums import ServiceLifetime
from .exceptions import DependencyResolutionError, CircularDependencyError, ContainerSealedError
from .registration import ServiceRegistration
from .resolver import DependencyResolver


class ServiceScope:
    """
    A localized context for resolving SCOPED dependencies.
    """
    def __init__(self, container: "Container"):
        self.container = container
        self._scoped_instances: Dict[Type, Any] = {}
        self._lock = threading.Lock()

    def resolve(self, interface: Type) -> Any:
        # Resolving via the container, passing self as the active scope
        return self.container.resolve(interface, scope=self)

    def get_instance(self, interface: Type) -> Optional[Any]:
        with self._lock:
            return self._scoped_instances.get(interface)

    def set_instance(self, interface: Type, instance: Any) -> None:
        with self._lock:
            self._scoped_instances[interface] = instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # We could implement IDisposable interfaces here in the future
        self._scoped_instances.clear()


class Container:
    """
    The canonical IoC container for JARVIS AIOS.
    Thread-safe, strict validation, sealed post-bootstrap.
    """
    def __init__(self):
        self._registrations: Dict[Type, ServiceRegistration] = {}
        self._is_sealed: bool = False
        self._singleton_lock = threading.Lock()

    def _assert_not_sealed(self):
        if self._is_sealed:
            raise ContainerSealedError("Cannot mutate a sealed container.")

    def register_singleton(self, interface: Type, implementation: Type) -> None:
        self._assert_not_sealed()
        self._registrations[interface] = ServiceRegistration(
            interface=interface, 
            lifetime=ServiceLifetime.SINGLETON, 
            implementation_type=implementation
        )

    def register_scoped(self, interface: Type, implementation: Type) -> None:
        self._assert_not_sealed()
        self._registrations[interface] = ServiceRegistration(
            interface=interface, 
            lifetime=ServiceLifetime.SCOPED, 
            implementation_type=implementation
        )

    def register_transient(self, interface: Type, implementation: Type) -> None:
        self._assert_not_sealed()
        self._registrations[interface] = ServiceRegistration(
            interface=interface, 
            lifetime=ServiceLifetime.TRANSIENT, 
            implementation_type=implementation
        )

    def register_factory(self, interface: Type, factory: Callable[..., Any], lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT) -> None:
        self._assert_not_sealed()
        self._registrations[interface] = ServiceRegistration(
            interface=interface, 
            lifetime=lifetime, 
            factory=factory
        )

    def register_instance(self, interface: Type, instance: Any) -> None:
        self._assert_not_sealed()
        self._registrations[interface] = ServiceRegistration(
            interface=interface, 
            lifetime=ServiceLifetime.SINGLETON, 
            instance=instance,
            _instance_cache=instance
        )

    def validate(self) -> None:
        """
        Traverses the dependency graph of all registered services.
        Detects missing dependencies and circular loops.
        """
        for interface in self._registrations.keys():
            self._validate_graph(interface, set())

    def seal(self) -> None:
        """
        Validates the dependency graph and seals the container, preventing further modifications.
        """
        self._assert_not_sealed()
        self.validate()
        self._is_sealed = True

    def create_scope(self) -> ServiceScope:
        """Creates a new bounded scope for SCOPED lifetimes."""
        return ServiceScope(self)

    def _validate_graph(self, interface: Type, visited: Set[Type]) -> None:
        if interface in visited:
            cycle = " -> ".join([i.__name__ for i in visited] + [interface.__name__])
            raise CircularDependencyError(f"Circular dependency detected: {cycle}")

        registration = self._registrations.get(interface)
        if not registration:
            # We don't fail here if someone resolves it directly, but we fail if it's a required dependency.
            return

        target = registration.implementation_type or registration.factory
        if not target:
            return  # Instance registration has no deps

        deps = DependencyResolver.get_dependencies(target)
        
        visited.add(interface)
        for param_name, param_type in deps.items():
            if param_type not in self._registrations:
                raise DependencyResolutionError(
                    f"Missing registration for '{param_type.__name__}' required by '{interface.__name__}'"
                )
            self._validate_graph(param_type, visited)
        visited.remove(interface)

    def try_resolve(self, interface: Type, scope: Optional[ServiceScope] = None) -> Optional[Any]:
        try:
            return self.resolve(interface, scope)
        except DependencyResolutionError:
            return None

    def resolve(self, interface: Type, scope: Optional[ServiceScope] = None) -> Any:
        """
        Resolves a service by its interface.
        """
        registration = self._registrations.get(interface)
        if not registration:
            raise DependencyResolutionError(f"No registration found for {interface.__name__}")

        # Singleton fast path
        if registration.lifetime == ServiceLifetime.SINGLETON and registration._instance_cache is not None:
            return registration._instance_cache

        # Scoped fast path
        if registration.lifetime == ServiceLifetime.SCOPED:
            if not scope:
                raise DependencyResolutionError(f"Cannot resolve SCOPED service {interface.__name__} without an active scope.")
            cached = scope.get_instance(interface)
            if cached is not None:
                return cached

        # Resolution (instantiation needed)
        # We need to construct the dependencies first
        target = registration.implementation_type or registration.factory
        
        if not target and registration.instance is not None:
            return registration.instance # Should be hit by fast path, but safety net

        deps = DependencyResolver.get_dependencies(target)
        kwargs = {}
        for param_name, param_type in deps.items():
            kwargs[param_name] = self.resolve(param_type, scope)

        # Thread-safe instantiation for Singletons
        if registration.lifetime == ServiceLifetime.SINGLETON:
            with self._singleton_lock:
                # Double-check locking
                if registration._instance_cache is None:
                    registration._instance_cache = target(**kwargs)
                return registration._instance_cache
                
        # Scoped instantiation
        if registration.lifetime == ServiceLifetime.SCOPED:
            instance = target(**kwargs)
            scope.set_instance(interface, instance)
            return instance

        # Transient instantiation
        return target(**kwargs)

    def dispose(self) -> None:
        """Cleans up the container and allows garbage collection."""
        self._registrations.clear()
        self._is_sealed = False
