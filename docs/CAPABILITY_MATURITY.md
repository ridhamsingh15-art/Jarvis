# JARVIS Capability Maturity Ledger

**Purpose:** Track the full JARVIS vision one capability at a time. Do not begin implementation on the next capability until the current capability's acceptance gate is satisfied and recorded here.

**Scoring note:** This is a transparent engineering rubric, not a universal objective percentage. Weights total 100%. Maturity scores are evidence-based engineering judgments. A capability can be marked 100% only when all of its scoped acceptance criteria are documented, executed, and passing; this does not mean the software is bug-free or production-ready.

## Scoring model

Weighted points = `weight × maturity / 100`.

- **0%:** no implementation/evidence found in the reviewed project state.
- **25%:** concept or narrow/experimental implementation; major acceptance cases absent.
- **50%:** partly functional; key integrations or failure cases unverified.
- **75%:** substantial implementation and regression coverage; material gaps remain.
- **100%:** all capability-specific acceptance criteria are documented, executed, and passing; relevant limitations are fixed or expressly excluded from the scoped requirement.

## Full vision scorecard

These are the current evidence-based maturity estimates. Revise each capability only when its acceptance gate is closed.

| # | Capability | Weight | Maturity now | Status |
|---:|---|---:|---:|---|
| 1 | Core conversational agent and orchestration | 10% | 100% | **ACCEPTED — gate complete** |
| 2 | Best-model strategy and provider routing | 8% | 100% | **ACCEPTED — gate complete** |
| 3 | Planning, reasoning and multi-step execution | 9% | 100% | **ACCEPTED - gate complete** |
| 4 | Computer use: files, shell, browser and applications | 10% | 100% | **ACCEPTED - gate complete** |
| 5 | Long-term personal memory | 7% | 50% | QUEUED |
| 6 | Adaptive personality and personalization | 4% | 25% | QUEUED |
| 7 | Voice input and output | 7% | 0% | QUEUED |
| 8 | Screen-aware perception and context | 7% | 25% | QUEUED |
| 9 | REA: research and JARVIS auditing workflow | 6% | 25% | QUEUED |
| 10 | Autonomous goals, background tasks and schedules | 6% | 75% | QUEUED |
| 11 | Safety, permissions and approvals | 8% | 50% | QUEUED |
| 12 | Durable persistence and crash recovery | 6% | 75% | QUEUED |
| 13 | Testing, independent verification and observability | 4% | 75% | QUEUED |
| 14 | GUI and user experience | 3% | 75% | QUEUED |
| 15 | Extensible tools, skills and integrations | 3% | 50% | QUEUED |
| 16 | Deployment and operational management | 2% | 50% | QUEUED |
| | **Total** | **100%** | | |

Initial weighted baseline: **54.25 / 100**. Current weighted score after accepting Gates 1-4: **73.00 / 100**. These are rubric-based progress estimates, not objective proof that the overall vision is complete.

## Gate 1 — Core conversational agent and orchestration

### Scope

Cover the main Agent request path and coordination layer. Do not treat voice, complete model/provider selection, full screen perception, or the separate durable Mission Control capability as complete just because the Agent can route to those systems.

### Acceptance criteria

1. **Request/session lifecycle:** normal chat/tool/memory/mission routes preserve session/turn state and usable conversation context; optional memory or persistence errors do not create false tool success.
2. **Task-state discipline:** only runnable tasks are dispatched; terminal tasks are not re-executed or transitioned twice; retryable failures use legal state transitions; active tasks owned by another execution are not mutated.
3. **Bounded orchestration:** model-directed execution remains behind the canonical Agent processing/policy boundary; iteration ceilings and duplicate-action detection stop loops; malformed task arguments do not crash loop fingerprinting.
4. **Uncertain side effects:** callback exceptions, invalid callback returns, and side-effecting timeouts become explicit `OUTCOME UNKNOWN`; no automatic retry, subsequent model-directed action, or later preplanned batch action occurs after uncertainty.
5. **Truthful responses:** uncertain outcomes override optimistic model claims; broken callback contracts cannot be reported as success; skipped tasks do not inflate actual execution counts.
6. **Trace and diagnostics:** request trace records route, outcome-unknown status and final response; telemetry does not classify uncertain operations as plain success.
7. **Regression acceptance:** focused tests, broader Agent/planner/parser/router/session/runtime acceptance, targeted Ruff and compile checks, complete repository test suite, and review of all skips. No claim of zero bugs or full repository audit is implied.
8. **Preservation:** no staging, commit, push, reset, stash, or rewriting unrelated user work without explicit permission.

### Gate 1 worklog

- **2026-10-18 — accepted at 100% within this gate's scope.** Hardened `core/tool_feedback_loop.py` to stop on `OUTCOME UNKNOWN`, prevent automatic retry/model continuation, annotate later preplanned tasks as not executed, handle invalid callback returns/exceptions, preserve completed/running task state, and create deterministic cycle-safe task fingerprints.
- Added `core/action_safety.py` with an explicit read-only allowlist and narrowly scoped pre-side-effect failure classification for `file.open_file`. Generic mutation errors (including permission errors) remain uncertain; only documented pre-launch path/type/blocked checks use ordinary bounded recovery.
- Hardened `core/executor/executor.py`, legacy `core/executor.py`, `core/agent.py`, and `core/execution_summary.py` so handler exceptions after possible side effects are recorded as `OUTCOME UNKNOWN`, optimistic model claims cannot conceal them, callback faults are not retried because of internal `TypeError`, and uncertain result summaries preserve target names and partial-completion facts.
- Added regressions in `tests/test_tool_feedback_loop.py`, `tests/test_agent_timeout_isolation.py`, and `tests/test_executor_reexecution_guard.py` for no-retry behavior, no follow-on batch action, already-terminal tasks, invalid callback results, malformed args, safe read-only recovery, and truthfulness of final responses.
- Focused final grounding/orchestration/executor regression set: **88 passed**. Expanded Agent/execution-path suite: **315 passed**.
- Final full repository test run: **1,431 passed, 8 skipped, 0 failed in 103.67s**. The 8 skips were reviewed: 1 directory-symlink test skipped because the environment disallows creating symlinks; 7 POSIX-specific shell tests skipped on Windows (1 POSIX absolute-path-vs-Windows-switch case, 4 POSIX parameter-expansion cases, 1 POSIX shell-quoting case, and 1 POSIX absolute-path-handling case). No failing tests remain.
- Runtime smoke check: `SMOKE_TEST=PASS`; `main.py --help`, `mission_crash_safe.py --help`, and `mission_control.cli --help` exited successfully; whole-package `compileall` passed. Targeted Ruff on the touched modules passed. `git diff --check` passed; Git emitted existing LF-to-CRLF conversion warnings only.
- Scope boundary: Gate 1 acceptance covers the conversational Agent orchestration seam, not the later provider-routing, computer-use capability depth, voice, screen awareness, or production-readiness release gate. Those remain queued rows and are not implied complete by this acceptance record.

## Gate 2 — Best-model strategy and provider routing

### Scope

Accept the provider-selection and model-routing layer for the configured provider adapters currently shipped by JARVIS: Ollama, Google Gemini API, and MiniMax API. This gate does not claim that external provider availability, account entitlements, live billing, vision/screen input, voice, or provider adapters not present in the repository have been verified. Those are separate operational or future-capability concerns.

### Acceptance criteria

1. **Validated provider topology:** JARVIS_PROVIDER must name a supported adapter; JARVIS_FALLBACK_PROVIDERS is an explicit, ordered opt-in; duplicates, unknown fallbacks, and primary/fallback duplication fail fast. Role-provider overrides must refer to the primary or an explicitly enabled fallback.
2. **Privacy by default:** the default registry contains the configured primary provider only. Cloud fallback providers are not silently enabled. Missing credentials for optional fallbacks omit those providers with a warning; missing credentials for the selected primary fail clearly.
3. **Role-aware provider/model mapping:** general, reasoning, coding, and fast roles resolve to provider-native model IDs. Explicit request provider/model choices are preserved. The supported adapters' capability declarations are tested; text-only adapters do not claim the image transport needed for vision/screen understanding.
4. **Safe fallback routing:** only registered, healthy providers capable of the request are candidates. Providers are ranked by configured/request preference, locality/privacy preference, health, measured latency, and known cost estimates. Provider errors update health and use only the configured candidate chain.
5. **Constraints are not silently ignored:** request output-token bounds propagate to provider APIs; measured latency ceilings filter providers already observed to exceed the ceiling; known insufficient context windows are filtered. A cost ceiling for cloud generation requires a finite output-token bound and known pricing. Unknown prices or estimator failures are not treated as free. Cost is a conservative preflight estimate, not a billing guarantee. Cold-start latency and unknown context metadata remain explicitly unknown rather than being presented as measured facts.
6. **One gateway contract:** runtime LLMClient generation and embeddings use the shared ModelGateway implementation by default, including CLI/Mission Control instances created separately. The direct Ollama-only path must be explicitly requested and cannot override a cloud-primary configuration.
7. **No accidental external requests in acceptance tests:** configuration, routing, fallback, cost/context/latency filtering, and provider HTTP payload contracts are covered by mocked offline tests. Live credential use is not required or performed by this gate.
8. **Regression acceptance:** all targeted routing/provider/integration tests, whole-package compile, runtime smoke, supported CLI help checks, targeted Ruff, diff check, and complete repository test suite pass; existing skips are reviewed.
9. **Preservation and publication:** no generated codebase dump or temporary audit script is included. Provider changes are published as a separate commit from the baseline; no history rewrite or destructive cleanup is performed.

### Gate 2 worklog

- **2026-10-18 — accepted at 100% within this gate's scope.** Added a reusable runtime provider registry/gateway path, provider-role defaults and overrides, explicit opt-in fallback configuration, startup validation, and routing through LLMClient by default.
- Routed model choices by semantic role and actual declared capability. Updated Gemini and MiniMax adapters to honor role/explicit model overrides; added max_output_tokens, validated inference bounds, provider context metadata, rolling successful-latency observations, and selection ranking based on preference, health, latency, and known cost.
- Cost ceilings fail closed for unknown cloud model prices and require a bounded output for cloud text generation. Unknown context metadata remains unknown. This is preflight estimation, not a provider invoice guarantee.
- Aligned default model IDs with the official provider catalogs: Gemini gemini-3.8-flash, reasoning/coding gemini-4-argon, and embedding gemini-embedding-2; MiniMax MiniMax-M3 for general/reasoning/coding and MiniMax-M2.7-highspeed for fast requests. Gemini's scheduled future standard rates and MiniMax's documented M3 context-tier rates are intentionally used conservatively in estimates. References: https://ai.google.dev/gemini-api/docs/models, https://ai.google.dev/gemini-api/docs/pricing, https://platform.minimax.io/docs/pricing/overview.
- Added offline regression coverage for provider topology, credential handling, role overrides, primary/fallback selection, LLMClient routing, cost/context/latency budgets, current default model IDs, and capability metadata. Focused provider/routing/integration suite: **152 passed**.
- Final full repository test run after model-default updates: **1,480 passed, 8 skipped, 0 failed in 95.36s**. The 8 skips are the known Windows symlink/POSIX-shell skips recorded in Gate 1; no failing tests remain.
- Whole-package compileall passed. Runtime smoke reported SMOKE_TEST=PASS with no external or state-changing actions. main.py --help, mission_crash_safe.py --help, and mission_control.cli --help passed. Targeted Ruff and git diff --check passed (Git emitted line-ending conversion warnings only).
- **Operational boundary:** no live Gemini/MiniMax request or charge was made because live credentials/account access were not part of offline acceptance. Availability, quotas, account entitlements, and real billing must be checked when a provider is deliberately configured. Screen/voice capabilities remain separate rows.

## Gate 3 - Planning, reasoning and multi-step execution

**Status: ACCEPTED at 100% within this gate's documented scope (2026-10-18).** All acceptance criteria below were executed and passed; explicit boundaries remain documented.

### Scope

Accept the planning/reasoning seam used to turn a user goal into a validated sequence, critique it, verify declared tool requirements, and refuse to present an unverified draft as executable. Also accept the model-driven objective planner's bounded dependency-graph validation and its tested integration with the crash-safe objective runner. Keep provider-routing implementation details under Gate 2, general computer-use capability depth under Gate 4, durable storage/recovery guarantees under Gate 12, and release/observability depth under Gate 13.

This gate does not claim arbitrary mission dispatch: ReasoningManager currently has no mission registry wired into its verifier, so a plan that declares required missions must fail verification and end safely in clarification rather than being approved. It does not claim live provider availability or live model accuracy; model planning acceptance uses mocked responses and temporary test workspaces.

### Acceptance criteria

1. **Bounded model planning:** planner input and output are size-bounded; output must match a typed JSON schema, use supported context labels, and provide 1-32 concise ordered steps unless clarification is requested. Invalid output, provider exceptions, or overlong responses produce a clarification plan with no steps rather than an apparently runnable generic task.
2. **Critique fails closed:** malformed critique JSON, missing/wrongly typed decision fields, or invalid clarification data never count as approval.
3. **Plan verification:** the verifier checks step count/content and field types, supported context labels, available declared tools, and registry verification errors. Required missions cannot be marked available without a connected mission registry.
4. **Bounded deliberation:** iteration limits must be valid and bounded. A plan is returned for downstream execution only after critique and verification both pass. Clarification and iteration-exhaustion results contain no steps or declared tool requirements.
5. **Model-driven objective graph:** novel objectives plan only against the currently registered action catalog. The whole graph is validated before execution: tool/action allowlists, argument names/types, mutation restrictions, unique step IDs, dependencies, output references, dependency ordering and cycle rejection. Ambiguous destructive requests and unsupported objectives fail closed.
6. **Multi-step integration evidence:** a mocked model plan can resolve a prior step's verified result reference in a later step and complete through the crash-safe objective runner in a temporary workspace; no live provider call or real user-data mutation is required.
7. **Regression acceptance:** focused planning/reasoning/objective-runner tests, relevant collaboration/agent-loop tests, whole-package compile, full repository suite, targeted Ruff, smoke and supported CLI checks pass. Existing skips and platform boundaries are reviewed and reported.
8. **Preservation:** changes stay within Gate 3 plus its tests and this ledger; accepted Gates 1-2 stay accepted; do not reset, rewrite history, or include generated codebase dumps or scratch scripts in commits.

### Gate 3 worklog

- Gate opened on 2026-10-18. Baseline verified at commit 09576fc35c632ad238e1ec641e403587bead956b; branch feature/jarvis-control-center was clean and matched origin before changes.
- Baseline focused tests: tests/test_planner.py, tests/test_objective_planner.py, tests/test_reasoning.py, and tests/test_reasoning_loop.py: **33 passed**.
- **2026-10-18 - accepted at 100% within the documented scope.** Hardened the reasoning planner to enforce bounded input/output, JSON schema and field validation, supported context labels, step-count and length limits, and an explicit non-executable clarification result on model/provider/parse failure. A clarification response discards all proposed steps and tool requirements.
- Hardened the critic so malformed JSON, wrong-typed booleans, unsupported fields, invalid clarification data, and overlong output cannot be treated as approval. Hardened the verifier to validate step/list structure, supported context labels, registered-tool availability, registry failures, and unconnected mission requirements.
- Reworked the deliberation loop to validate iteration bounds (1-10) and return a downstream plan only after critique and verification pass. If no valid plan is established within the iteration budget, it returns a clarification result with no executable steps or declared tool requirements.
- Added tests in tests/test_reasoning_planning_acceptance.py for malformed plan output, unsupported schema values, clarification behavior, malformed critic output, missing tools, disconnected mission registry behavior, iteration exhaustion, and invalid iteration bounds.
- Focused planning/reasoning/mission-objective/collaboration/agent-loop tests: **61 passed in 3.03s**.
- Final full repository suite: **1,489 passed, 8 skipped, 0 failed in 103.54s**. The 8 skips match the previously reviewed Windows environment boundaries: 1 directory-symlink test skipped because symlink creation is not permitted and 7 POSIX-only shell tests skipped on Windows (path semantics, parameter expansion, shell quoting, and POSIX path handling).
- Whole-package compileall passed. Runtime smoke returned **SMOKE_TEST=PASS; no external or state-changing actions were executed**. main.py --help, mission_crash_safe.py --help, and mission_control.cli --help passed. Targeted Ruff passed; git diff --check passed with only Git LF-to-CRLF conversion warnings.
- The objective planner's existing regression suite validates dependency ordering, output-reference ancestry and path semantics, cycle/undeclared-reference rejection, unsupported actions, and a two-step output-reference flow executed through the crash-safe objective runner in a temporary workspace. Its model responses are mocked; no live provider requests or user-data mutation were made.
- **Boundary kept explicit:** a mission registry is not currently wired to the reasoning verifier, so required_missions fails verification instead of being assumed available. Live provider/model quality, computer-use coverage, durable mission recovery guarantees, and broad release observability remain outside this gate.
- Capability 3 is accepted; Gate 4 remains queued and was not started.

## Gate 4 - Computer use: files, shell, browser and applications

**Status: ACCEPTED at 100% within this gate's documented scope (2026-10-18).** All capability-specific acceptance criteria below were executed and passed. Explicit limits on direct browser verification and platform-specific tests remain recorded.

### Scope

Accept first-party local tool access across FileTool, ShellTool, BrowserTool, and WindowsTool, along with the crash-safe mission verifier that validates browser destinations and bounded file-read output. Preserve the existing ExecutionPolicy, registry/validator, shell sandbox, sensitive-path checks, workspace boundaries, process-tree termination, credential environment filtering, Codex desktop confirmation posture, and crash-safe mission execution.

This gate does not claim that every browser page can be inspected: page-level assertions require the crash-safe verifier and an enabled, accessible local Chromium inspection endpoint. A successful browser API call proves the launch request was accepted, not that the page loaded. Likewise, a Windows process launch proves only that the launch request was accepted; app readiness is checked separately where the crash-safe runner supports it.

### Acceptance criteria

1. **Direct-call contract:** each first-party tool rejects malformed action names, non-object argument payloads, missing required arguments, and unknown fields before dispatch. Tool-specific values such as paths, URLs, app names, and commands receive explicit validation; malformed inputs must not reach browser/process/file side effects.
2. **Browser destination safety:** one shared target builder/validator is used by the direct BrowserTool and crash-safe browser verifier. Only valid HTTP(S) destinations are supported; embedded credentials, malformed ports/hosts, control characters, backslash/whitespace ambiguity, unsupported schemes, and overlong URLs are rejected. Successful direct launch messages explicitly distinguish request acceptance from page-load/content verification.
3. **Bounded file output:** text reads are capped at 64,000 characters with an explicit truncation marker; directory listings return at most 200 entries and explicitly indicate truncation. The crash-safe verifier checks the same bounded read projection against current disk content. Path-resolution failures, non-text files, invalid patch value types, sensitive paths, protected paths, and workspace escapes fail closed.
4. **Restricted shell invariants:** the direct shell dispatcher applies the action schema and requires a non-empty command. Existing command-risk checks, cwd/workspace validation, environment secret filtering, timeouts, output caps, and process-tree lifetime protection remain intact and covered by regressions.
5. **Application-launch integrity:** the Windows tool accepts only a known application key, uses a fixed executable mapping without shell execution or model-supplied command arguments, and does not claim app readiness solely because process launch was accepted.
6. **Crash-safe integration:** browser URL verification and bounded file-read verification agree with the actual tool contracts. Existing guarded Codex desktop delegation and mission-runner execution flow are covered by their current mocked/temporary-workspace regression tests.
7. **Regression acceptance:** focused computer-use/file/browser/shell/policy/mission/Codex tests, the Capability 1-3 regression suites, whole-package compilation, safe smoke test, supported CLI help checks, targeted Ruff, staged diff check, and the full repository suite pass. Existing skips and platform limitations are reviewed.
8. **Preservation and publication:** Capabilities 1-3 remain accepted; changes are scoped to the computer-use tools, their crash-safe verification seam, tests, and this ledger. Do not include generated codebase dumps, environment files, or temporary scripts in commits.

### Gate 4 worklog

- Gate opened on 2026-10-18. Baseline verified at commit fa50400221e11550febbe81ea3c15f7f30743152; branch feature/jarvis-control-center was clean and matched origin before changes.
- Baseline focused computer-use/file/browser/shell/policy set: **197 passed, 8 skipped in 2.45s**.
- **2026-10-18 - accepted at 100% within the documented scope.** Added BaseTool.validate_action_call for shared runtime validation of action names, JSON-object argument envelopes, required arguments, and unknown fields. Applied it to FileTool, BrowserTool, WindowsTool, and ShellTool; kept ShellTool's compatibility action alias and reject empty commands before execution.
- Added a shared HTTP(S) URL normalizer and browser-target builder used by direct browser actions and the crash-safe browser verifier. It rejects embedded credentials, unsupported URL schemes, malformed host/port values, control characters, whitespace/backslash ambiguity, and overlong URLs. Direct BrowserTool success messages now state that they represent an accepted open request, not page-load/content verification. Legacy friendly-domain normalization (such as youtube.com) remains supported.
- Bounded FileTool text reads to 64,000 characters and directory listings to 200 entries, with explicit truncation markers. Updated the crash-safe independent read verifier to compare the exact bounded projection. Hardened path-resolution errors, UTF-8 handling, and patch argument types; preserved existing sensitive-path and workspace containment checks.
- Kept the create_file ActionDefinition strict (text is the declared optional input) so ToolIntelligenceManager still normalizes the legacy content alias into text; FileTool direct/isolated calls preserve the old content alias and the crash-safe verifier checks the correct postcondition.
- Tightened Windows app-launch argument handling and use of fixed allowlisted commands with Popen([...], shell=False). The result message explicitly avoids claiming app readiness merely because the launch request was accepted.
- Added tests/test_computer_use_acceptance.py for URL normalization/rejection, direct-call schemas, shared browser verification, bounded output, shell call validation, Windows fixed mappings, and Validator/Registry contract alignment. Expanded computer-use/mission integrations: **270 passed, 8 skipped in 34.70s**. Reproduced prior full-suite failure regressions: **65 passed in 3.01s**; parameter-normalization/crash-stage/acceptance follow-up: **35 passed in 1.39s**.
- Final full repository test run: **1,514 passed, 8 skipped, 0 failed in 99.46s**. The 8 skips are platform-specific: 1 directory-symlink test skipped because symlink creation is unavailable in this environment, plus 7 POSIX-only shell tests skipped on Windows (path semantics, POSIX parameter expansion, shell quoting, and POSIX absolute-path handling).
- Whole-package compileall passed. Safe runtime smoke reported **SMOKE_TEST=PASS; no external or state-changing actions were executed**. main.py --help, mission_crash_safe.py --help, and mission_control.cli --help passed. Targeted Ruff passed; git diff --check passed with Git's LF-to-CRLF warnings only.
- **Scope boundaries remain explicit:** direct BrowserTool confirms only that the default-browser open request was accepted. Browser page/DOM assertions require the crash-safe verifier and an available local Chromium inspection endpoint; Windows process-name checks cannot prove readiness for an application already running. Live page interaction, every possible app, always-on screen perception, and general unrestricted automation are not claimed by this gate.
- Capability 4 is accepted. Capability 5 remains queued and was not started.

## Operating rule

Work one row at a time in the displayed order. For each row: inspect code and callers, reproduce defects, apply focused fixes, add/adjust regression tests, run relevant integration/release checks, and record actual output. Only set maturity to 100% and start the next row when the current gate's evidence is complete.