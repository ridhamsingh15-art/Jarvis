# Engineering Standards

This document defines the minimum working agreement for changes to JARVIS AIOS. It is intentionally practical and applies to solo work as well as future collaborators.

## Definition of done

A change is ready to merge when all applicable conditions are met:

1. The behavior and scope are documented.
2. The implementation is the smallest coherent change that solves the problem.
3. Regression tests cover the intended behavior and meaningful failure paths.
4. CI-equivalent checks pass, or an explicit, evidence-backed exception is recorded.
5. Security, privacy, and compatibility implications are reviewed.
6. Diagnostics are useful but do not disclose secrets or unnecessary user data.
7. Documentation and configuration examples match actual behavior.
8. The diff contains no unrelated edits, generated files, local state, or credentials.
9. A reviewer can understand the intent without reconstructing the entire conversation that led to the change.
10. The change can be rolled back without losing unrelated work.

## Architecture boundaries

- **Interface layer:** CLI and GUI collect intent and present status; they should not bypass policy.
- **Agent/orchestration layer:** plans and coordinates work but does not make model output inherently trusted.
- **Policy/validation layer:** checks tool names, arguments, permissions, scope, and risk before execution.
- **Tool adapters:** perform narrowly defined side effects and return bounded, structured outcomes.
- **Verification layer:** checks postconditions independently where practical.
- **Providers:** isolate model-specific APIs, timeouts, retries, and errors behind stable contracts.
- **Persistence:** keeps durable state explicit, bounded, and subject to privacy/retention decisions.
- **Observability:** records task IDs, timing, outcomes, and safe diagnostics without secret values or full private content by default.

These are logical boundaries, not a claim that every module is already perfectly separated. When changing boundaries, document the dependency direction and add contract tests.

## Reliability expectations

- Every external call has a bounded timeout and clear failure behavior.
- Retries are bounded and only used when repeating the operation is safe.
- State-changing operations should be idempotent where possible or explicitly report partial completion.
- Cancellation, denial, timeout, and verification failure are distinct outcomes.
- A successful tool response is not equivalent to successful completion of the user goal.
- Live integrations are tested separately from mocks and do not run in normal CI unless safely provisioned.

## Security expectations

- Default to local-only behavior where practical and make cloud/network paths explicit.
- Validate again at the last trusted boundary before side effects.
- Use allowlists and least privilege rather than attempting to enumerate every dangerous input.
- Treat model output, retrieved documents, web pages, OCR, shell output, and external tool results as untrusted.
- Fail closed on authorization or validation uncertainty.
- Never place secrets in source control, examples, test fixtures, screenshots, or logs.
- Keep remote execution and federation opt-in until their authentication and threat models have been independently reviewed.

## Test layers

| Layer | Purpose | Examples |
| --- | --- | --- |
| Unit | Deterministic logic and edge cases | URL validation, parsing, policy decisions |
| Contract | Stable boundaries between modules | Provider interface, tool result schema |
| Integration | Multiple real components with external boundaries mocked or controlled | Agent to router to tool adapter |
| Live smoke | Verify an actual local service or desktop path | Local Ollama, guarded desktop observation |
| Release | Verify packaging and installation from a clean environment | Fresh Windows VM, dependency check |

Test reports must state which layer ran. Never describe a mocked boundary as a live end-to-end test.

## Current known gaps

See [Production readiness](PRODUCTION_READINESS.md). The broad codebase has lint debt, and clean-install, dependency scanning, hosted CI, remote MCP stress tests, and independent security review remain open. This standard is a target and does not imply those gaps are already closed.
