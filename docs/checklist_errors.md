# Foundation Specification Checklist: Error Model

- [x] **Typed errors**: Supported via `JarvisError` base exception.
- [x] **Error hierarchy**: Extended classes mapping to strict domains (e.g. `NetworkError`, `PluginError`).
- [x] **Categories**: Managed via the `ErrorCategory` Enum.
- [x] **Severity**: Managed via the `ErrorSeverity` Enum.
- [x] **Context capture**: Component and Correlation IDs are pulled directly from `core.telemetry.context` automatically on instantiation.
- [x] **Error chaining**: Supported via the `root_cause` field which preserves inner exceptions.
- [x] **Root cause tracking**: Deeply nested JarvisErrors are serialized sequentially.
- [x] **Retryability**: Controlled via the `retryable` boolean flag (true for Transient/Network, false for Fatal/Config).
- [x] **Recoverability**: Controlled via the `recoverable` boolean flag.
- [x] **Structured serialization**: `to_dict()` safely maps all attributes into an atomic dictionary structure ready for the Logging pipeline.
- [x] **Correlation IDs**: First-class tracking.
- [x] **Automatic logger integration**: `ErrorHandler.setup(logger)` binds to `sys.excepthook` allowing global interception of panics to log via the structured pipeline and flush async queues before termination.
- [x] **Stack traces**: Stack traces are intercepted automatically using `traceback` (including `__traceback__` evaluation on root causes).
- [x] **Metadata**: Stored in a custom dictionary parameter on exception init.
- [x] **Provider-independent design**: No external dependencies beyond the standard library.

### Deliverables Addressed
1. **Repository files**: Placed cleanly in `core/errors`.
2. **Interfaces**: `JarvisError` acts as the canonical interface.
3. **Tests**: Covered under `tests/test_errors.py`.
4. **Foundation Compliance**: Achieved.
