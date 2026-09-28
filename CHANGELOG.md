# Change Log

Date: 2026-08-04

This entry covers only the stabilization work performed for this audit; it
does not claim ownership of pre-existing uncommitted changes.

| File | Change | Impact and compatibility |
| --- | --- | --- |
| `core/telemetry/context.py` | Added a safe default path for metadata in new threads. | Fixes concurrent logging; public API unchanged. |
| `core/cognition/classifier.py` | Added high-confidence recognition of common conversational and identity/name requests, known sites, URLs, and searches. | Avoids unnecessary model planning; unknown input retains the existing model fallback. |
| `core/agent.py` | Preserved the classifier-selected tool and added natural direct responses for common conversation and identity/name questions. | Browser actions no longer become Windows actions; existing Windows defaults remain. |
| `gui/views/chat_view.py` | Added a pre-execution announcement signal from the background agent worker. | Users now see an action acknowledgement before a tool runs; existing synchronous callers remain compatible. |
| `providers/minimax_provider.py`, `providers/provider_factory.py`, `config/providers.py` | Added an opt-in MiniMax chat provider and factory registration. | No behavior changes unless `JARVIS_PROVIDER=minimax` is selected and `MINIMAX_API_KEY` is configured. |
| `core/__init__.py` | Replaced eager `Agent` import with a lazy export. | Removes a provider-model circular import while preserving `from core import Agent`. |
| `memory/base_memory.py`, `memory/sqlite_memory.py`, `memory/memory_manager.py` | Added persistent key/value personal facts to the active SQLite memory backend. | Explicit user memories survive a new memory-manager instance; conversation history remains compatible. |
| `tests/test_personal_memory.py` | Added persistence, recall, and safe-error-message regression coverage. | Test-only coverage. |
| `tests/test_minimax_provider.py` | Added MiniMax request, authentication, and health-check coverage. | Test-only coverage. |
| `tests/test_conversation_routing.py` | Added routing, response, and pre-execution announcement regressions. | Test-only coverage. |
| `headless_smoke.py` | Repaired stale imports and lint issues. | Script now type-checks against the current package layout. |
| `smoke_test.py` | Repaired lint and runtime-nullability issues. | Script now type-checks cleanly. |
