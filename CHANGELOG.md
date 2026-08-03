# Change Log

Date: 2026-08-04

This entry covers only the stabilization work performed for this audit; it
does not claim ownership of pre-existing uncommitted changes.

| File | Change | Impact and compatibility |
| --- | --- | --- |
| `core/telemetry/context.py` | Added a safe default path for metadata in new threads. | Fixes concurrent logging; public API unchanged. |
| `core/cognition/classifier.py` | Added high-confidence recognition of common conversational and identity/name requests, known sites, URLs, and searches. | Avoids unnecessary model planning; unknown input retains the existing model fallback. |
| `core/agent.py` | Preserved the classifier-selected tool and added natural direct responses for common conversation and identity/name questions. | Browser actions no longer become Windows actions; existing Windows defaults remain. |
| `tests/test_conversation_routing.py` | Added routing and response regressions. | Test-only coverage. |
| `headless_smoke.py` | Repaired stale imports and lint issues. | Script now type-checks against the current package layout. |
| `smoke_test.py` | Repaired lint and runtime-nullability issues. | Script now type-checks cleanly. |
