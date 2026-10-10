# Production readiness gates

This is a working assessment, not a certification.

## Verified in the October 10, 2026 maintenance pass

- [x] Python modules compile.
- [x] The Codex/Nuphus desktop path was exercised end to end; a read-only Chrome accessibility inspection completed successfully.
- [x] Codex desktop timeout is bounded at the tool level and given a longer deadline in the agent executor.
- [x] Sensitive-file opening is rejected by the file tool.
- [x] Natural-language command routing has regression tests for app aliases, screenshots, volume requests, and file-name/site-name ambiguity.
- [x] Named-file creation resolves into a configured safe workspace; when the configured root is inside the protected source tree, new files default to Documents\JARVIS instead.
- [x] Live end-to-end command “Open Calculator and Paint” opened both responsive Windows applications.
- [x] Live file creation and read-back completed through JARVIS; disk contents matched the requested exact text.
- [x] Persistent experience learning is wired into the Agent: privacy-reduced TOOL/MISSION outcomes are saved to local SQLite and retrieved as bounded, explicitly advisory history for similar future requests. It does not auto-execute learned plans or retrain the model.
- [x] Live local-model run: repeat “Open Calculator” requests recorded successful outcomes; a later request's first model input contained historical context and the action completed.
- [x] Authenticated live MCP smoke test passed discovery, tool listing, a real read-only tool call, and the autonomous task path on an ephemeral loopback port.
- [x] Non-zero shell exit codes become failed tasks, and bounded diagnostics remain available to the feedback loop as untrusted data.
- [x] Shell execution no longer uses `shell=True`; the default path is allowlisted and output/timeouts are bounded.
- [x] Dotenv loading preserves process-environment precedence and does not log secret values.
- [x] Invalid numeric/mode/provider configuration falls back safely.
- [x] Full pytest suite after desktop-bridge hardening: 1,173 passed in 27.01 seconds; the four focused bridge/routing modules passed 50 tests in 0.83 seconds.
- [x] Targeted Ruff checks for the bridge guard and Codex desktop boundary pass; repository-wide undefined-name check (`F821`) passes.
- [ ] Whole-tree Ruff currently reports 1,229 findings across the broad repository; establish ownership and baseline, then reduce this debt in reviewed, bounded changes.
- [x] `pip check` reports no broken requirements in the current environment.
- [x] `git diff --check` passed (Git reported only expected LF/CRLF working-copy warnings).

## Not yet production-ready

- [ ] Establish a clean, repeatable install from a blank Windows VM using only declared runtime and development dependencies.
- [x] Add a Windows CI workflow for Python 3.12 with dependency consistency, compilation, targeted lint and regression tests (hosted workflow execution still pending).
- [ ] Add dependency vulnerability scanning and license inventory; verify the CI workflow on a hosted runner.
- [ ] Establish a baseline for repository-wide Ruff and mypy findings; the wider codebase still contains pre-existing static-analysis debt.
- [ ] Add a signed build/release process, versioned changelog, provenance/SBOM and rollback instructions.
- [ ] Define dependency update cadence and emergency security-patch process.
- [ ] Threat-model and independently test file, shell, browser, remote MCP and federation boundaries.
- [ ] Verify remote MCP TLS/authentication behavior under misconfiguration, token rotation, replay, rate limiting and concurrent load.
- [ ] Test desktop automation recovery after approval cancellation, UI hangs, Codex timeout, Nuphus crash and Windows session lock.
- [ ] Add accessibility, localization, installer/updater, logging retention, crash reporting and operational support policies.
- [ ] Define privacy/data retention, consent and compliance requirements for each deployment jurisdiction before marketing or deployment.
- [ ] Conduct an external security review before calling the product enterprise- or multinational-ready.

## Acceptance principle

A green test suite proves only the scenarios exercised by those tests. Production readiness requires clean-install validation, independent security review, observability, release controls and operational ownership. Do not market JARVIS as error-free or security-certified until those gates are completed.
