# Foundation Specification Checklist: Event Bus

- [x] **Publish/Subscribe**: Handled gracefully via the `EventBus` facade tying into a `HandlerRegistry`.
- [x] **Typed events**: Payloads are strictly typed using `core.models.Event`.
- [x] **Synchronous handlers**: Natively supported.
- [x] **Asynchronous handlers**: Async coroutine handling supported and differentiated via `inspect.iscoroutinefunction()`.
- [x] **Multiple subscribers**: Yes, multiple matching subs are supported.
- [x] **Event priorities**: The `HandlerRegistry` orders matches by integer priority logic.
- [x] **Ordered dispatch per event**: Achieved successfully by iterating through the sorted `HandlerRegistry`.
- [x] **Thread safety**: Locks guard the `HandlerRegistry` subscriptions array.
- [x] **Wildcard subscriptions**: Natively supported (e.g. `system.*` or `system.**` using dynamic Regex compiling).
- [x] **Once-only subscriptions**: Setting `once_only=True` triggers `self._registry.unsubscribe()` pre-dispatch.
- [x] **Handler unsubscription**: Explicitly handled via tracking unique UUID `subscription_id`s.
- [x] **Graceful shutdown**: The bus supports `shutdown()` to aggressively clear subscriptions preventing leaks.
- [x] **Error isolation**: Handled in `EventDispatcher`. Panics are caught, mapped to `InternalError`, logged to the async daemon via `AsyncLogger`, and bypassed safely.

### Deliverables Addressed
1. **Repository files**: Cleanly encapsulated within `core/events/`.
2. **Interfaces / Bases**: `EventHandler` and `AsyncEventHandler` defined cleanly.
3. **Tests**: Validated thoroughly in `tests/test_event_bus.py`.
4. **Foundation Compliance**: Achieved securely mapping `Event` models across subsystems avoiding direct coupling perfectly.
