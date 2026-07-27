import inspect
from typing import Any, Callable, Dict, Optional, Type
from .exceptions import DependencyResolutionError


class DependencyResolver:
    """
    Analyzes constructors and factories to determine required dependencies via type hints.
    """
    @staticmethod
    def get_dependencies(target: Callable[..., Any]) -> Dict[str, Type]:
        """
        Parses the signature of a class __init__ or factory function.
        Returns a mapping of parameter names to their type hints.
        Strict typing is enforced.
        """
        deps = {}
        if isinstance(target, type):
            # Target is a class; inspect __init__ if it exists
            if not hasattr(target, "__init__") or target.__init__ is object.__init__:
                return {}
            signature_target = target.__init__
            is_class = True
        else:
            # Target is a function/factory
            signature_target = target
            is_class = False

        try:
            sig = inspect.signature(signature_target)
        except ValueError:
            # Built-ins without signatures
            return {}

        for name, param in sig.parameters.items():
            if is_class and name == "self":
                continue
            
            # Ignore *args and **kwargs
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            # If the parameter has a default, we consider it optional/satisfied
            if param.default is not inspect.Parameter.empty:
                continue

            if param.annotation is inspect.Parameter.empty:
                raise DependencyResolutionError(
                    f"Parameter '{name}' in '{target.__name__}' lacks a type hint. Strict DI requires type hints."
                )
            
            deps[name] = param.annotation
            
        return deps
