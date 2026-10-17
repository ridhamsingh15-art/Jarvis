# Foundation Specification Checklist: Logging Module

- [x] **Structured logging**: Emits JSON (or configured format) with discrete fields for level, timestamp, correlation_id, component, and metadata.
- [x] **Multiple log levels**: `DEBUG, INFO, WARN, ERROR, FATAL` are supported and filterable.
- [x] **Context-aware logging**: Leverages Python `contextvars` to isolate metadata across concurrent workflows safely.
- [x] **Correlation IDs**: First-class support via `set_correlation_id()`.
- [x] **Component names**: First-class support via `set_component_name()`.
- [x] **Timestamping**: ISO-8601 UTC timestamps are applied to every record at generation time (not emit time).
- [x] **Secret masking**: The `LogMasker` deeply inspects records and cross-references them against `ConfigSnapshot` schema fields marked `is_secret=True`, redacting them to `********` before serialization.
- [x] **JSON output**: Native `JsonFormatter`.
- [x] **Console output**: Native `ConsoleSink` and readable `TextFormatter`.
- [x] **File output**: Native `FileSink` that handles append modes safely.
- [x] **Configurable formatting**: Outputs dynamically constructed based on `ConfigSnapshot`.
- [x] **Non-blocking logging**: `AsyncLogger` uses a `queue.Queue` with a background Daemon thread. Invocations like `logger.info()` return almost instantaneously.
- [x] **Thread safety**: Safe for high concurrency; proven via integration tests with 10 threads logging 100 messages each.
- [x] **Graceful shutdown**: `shutdown()` method sets a thread event and drains the queue before closing file handles.

### Deliverables Addressed
1. **Repository files**: Placed cleanly in `core/telemetry`.
2. **Configuration integration**: The factory depends explicitly and solely on `ConfigSnapshot`. No hardcoded configurations exist.
3. **Tests**: Covered under `tests/test_logging.py`.
4. **Foundation Compliance**: Achieved.
