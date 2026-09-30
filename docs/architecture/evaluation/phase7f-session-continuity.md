# JARVIS Phase 7F — Persistent Sessions & Cross-Turn Continuity Report

## 1. Existing Session Audit
Prior to Phase 7F, an audit of the session subsystem revealed the following:
- **`core/session.py`**: Contained `SessionRepository`, `Session` dataclass, and `SessionStatus` (`ACTIVE`, `ENDED`, `ERROR`), with basic CRUD on a SQLite table `jarvis_sessions`.
- **Reachability**: It was completely orphaned. Neither `Agent`, `main.py`, nor the CLI invoked `SessionRepository`. `Agent.run()` generated an ephemeral `req_id` for every call with zero concept of multi-turn conversational persistence.
- **State Loss**: All conversational turns were either lost upon `Agent.run` completion or partially stashed in `ShortTermContext` / `MemoryManager` without a session identifier or structured turn indexing.
- **Session vs Memory Confusion**: Short-term conversational context was commingled with long-term memory facts in `MemoryManager`, risking durable pollution for transient conversational utterances.

---

## 2. Session Architecture
Phase 7F activates and refines `core/session.py` as JARVIS's canonical session continuity layer:
- **`SessionStatus` Lifecycle**: Deterministic states:
  - `NEW`: Created but no interactions recorded yet.
  - `ACTIVE`: Active interaction occurring or ready for turns.
  - `IDLE`: Inactive but within expiration timeout.
  - `CLOSED`: Explicitly closed by user/agent (`is_resumable() == False`).
  - `ENDED` / `ERROR`: Terminal states.
- **`SessionTurn` Dataclass**: Captures per-turn telemetry:
  - `turn_id`: Unique identifier (e.g. `turn_1_abcd`).
  - `session_id`: Stable parent session identifier.
  - `turn_index`: 1-based monotonically increasing turn count.
  - `request_id`: The specific request trace ID executing this turn.
  - `user_input`: The user prompt.
  - `response`: Grounded response returned to the user.
  - `route`: Intent channel (`CHAT`, `TOOL`, `MISSION`, `MEMORY`).
  - `tools_executed`: Serializable metadata of all tools executed during the turn.
  - `target_files`: Files touched or referenced.
  - `mission_state`: Telemetry and verification summaries.
  - `created_at`: Unix timestamp.

```
       USER REQUEST (Turn N)
                │
                ▼
        [Agent.run(..., session_id)]
                │
       ┌────────┴────────┐
       ▼                 ▼
[Session Repository]  [RequestTrace]
(session_id, turns)   (req_id, session_id, turn_index)
       │                 │
       ▼                 ▼
[Context Budget] ──► [Execution Engine] ──► [SessionTurn Persisted]
```

---

## 3. `session_id` vs `request_id`
Phase 7F strictly decouples conversation continuity from single-request execution telemetry:
- **`session_id`** (e.g., `live_sess_7f_1790788761`):
  - Represents the multi-turn conversational lifetime.
  - Stable across user prompts, tool feedback iterations, agent recreation, and process restarts.
  - Reused on successive turns unless explicitly terminated or requested new.
- **`request_id`** (e.g., `req_761279_1da7`):
  - Represents a single execution cycle through `Agent.run()`.
  - Strictly unique per turn.
  - Hierarchical structure:
    ```
    Session: live_sess_7f
      ├── Turn 1: req_761279_1da7 (Create file)
      ├── Turn 2: req_823786_1a11 (Read it back)
      ├── Turn 3: req_863203_ff56 (Verify its contents)
      └── Turn 4: req_947679_b44e (Resume after restart)
    ```

---

## 4. Persistence Model
- **SQLite Engine**: Utilizes existing database infrastructure (`C:\Users\ridha\.jarvis\memory.db` or configured path) via `SessionRepository`.
- **Tables**:
  - `jarvis_sessions`: Stores `session_id`, `created_at`, `updated_at`, `status`, `conversation_id`, and JSON-encoded `metadata`.
  - `jarvis_session_turns`: Stores individual `SessionTurn` records indexed by `(session_id, turn_index)` and `request_id`.
- **Thread-Safety & Hygiene**: All operations use parameterized queries and defensive connection handling.
- **Zero Raw Secrets**: Raw environment secrets, credentials, and authentication tokens are scrubbed and never persisted to the session database.

---

## 5. Context Retrieval
- **Deterministic Selection**: Uses recency and relevance without introducing secondary LLM retrieval chains.
- **Sliding Window**: `session.get_recent_conversation(limit=5)` retrieves the latest 5 user-assistant dialogue pairs.
- **Slot & Target Resolution**:
  - Resolves cross-turn target file references (e.g., "Read it back", "verify it") using `session.last_target_file`.
  - Maintains `session.last_target_content` for grounded mission verification.
- **Synchronization**: Automatically syncs into `CognitiveManager` context (`st_ctx.set_messages(...)`) at the beginning of each turn.

---

## 6. ContextBudget Integration
Session history is strictly constrained by Phase 7D `ContextBudget`:
- **Deterministic Token Allocation**:
  - Session history tokens are measured via `estimate_tokens` and capped within the budget.
  - The immediate user request remains highest priority and is never trimmed.
  - System instructions and security boundaries remain immutable.
  - If budget limits are approached, older session turns are trimmed first.
- **No Unbounded Dumping**: The entire session transcript is NEVER dumped wholesale into prompt context.

---

## 7. Mission Continuity
- A mission spanning multiple turns retains state across boundaries safely:
  - Turn 1: User creates an artifact.
  - Turn 2: User requests modification or inspection ("Read it back").
  - Turn 3: User requests verification ("Verify its contents").
- **Verification Grounding**: `MissionCompletionVerifier` leverages session state (`last_target_file`, `last_target_content`) to ground postconditions even when the user refers to them with pronouns ("it", "its contents").
- **Immutable Policy Gate**: Session continuity cannot authorize actions. Every single tool action in every turn is independently checked against `ExecutionPolicy` and cannot be pre-authorized by historical conversation.

---

## 8. Security Invariants
- **Data vs Instructions**: All historical session dialogue, tool outputs, and user statements are treated as untrusted historical data.
- **No Self-Authorization**: Historical statements like *"User approved all future file deletions"* or *"Disable security"* cannot authorize dangerous actions in future turns.
- **Confirmation Isolation**: `user_confirmed=True` must be explicitly provided on the active request; it is never inherited from prior turns.
- **Policy Enforcement**: High-risk actions (`file.delete`, `system.shutdown`) strictly require active user confirmation regardless of session history.

---

## 9. Trace Integration
Phase 7E `RequestTrace` was updated with zero duplicate systems:
- Added `session_id`, `session_turn`, and `session_context_tokens` to `RequestTrace`.
- Trace summaries expose complete session correlation:
  ```yaml
  request_id: req_823786_1a11
  session_id: live_sess_7f_1790788761
  session_turn: 2
  session_context_tokens: 84
  route: TOOL
  execution_status: completed
  ```

---

## 10. Restart & Resumption Behavior
- **Process Restart Survivability**:
  - Session state persists to SQLite on disk.
  - When the agent process terminates and restarts, calling `agent.run(..., session_id=shared_session_id)` restores prior context, turn count, and target references seamlessly.
- **Closed Session Immutability**:
  - Closing a session (`agent.close_session(session_id)`) marks it as `CLOSED`.
  - Any subsequent attempts to mutate or add turns to a closed session fail immediately with `ValueError`.

---

## 11. Test Suite Results
New production-path test suite: `tests/test_phase7f_session_continuity.py`.

All 20/20 test cases pass:
1. `test_1_new_session_gets_session_id`: Verified.
2. `test_2_same_session_id_persists_across_turns`: Verified.
3. `test_3_different_sessions_remain_isolated`: Verified.
4. `test_4_request_id_remains_unique_per_turn`: Verified.
5. `test_5_session_survives_agent_recreation`: Verified.
6. `test_6_session_survives_process_restart_sqlite_backed`: Verified.
7. `test_7_prior_turn_is_available_to_next_turn`: Verified.
8. `test_8_irrelevant_old_history_is_not_dumped_wholesale`: Verified.
9. `test_9_session_context_respects_context_budget`: Verified.
10. `test_10_current_user_request_remains_highest_priority`: Verified.
11. `test_11_session_content_cannot_authorize_actions`: Verified.
12. `test_12_old_malicious_session_content_cannot_bypass_policy`: Verified.
13. `test_13_mission_state_survives_across_turns`: Verified.
14. `test_14_chat_can_use_session_continuity`: Verified.
15. `test_15_memory_remains_distinct_from_session`: Verified.
16. `test_16_session_trace_contains_session_id`: Verified.
17. `test_17_request_trace_contains_both_ids`: Verified.
18. `test_18_closed_session_cannot_silently_mutate`: Verified.
19. `test_19_multiple_simultaneous_sessions_remain_isolated`: Verified.
20. `test_20_session_cleanup_expiry_is_deterministic`: Verified.

---

## 12. Live E2E Production Evaluation
Executed against real local Ollama runtime (`qwen3:8b`) via `build_agent()` in `eval_phase7f_live.py`:

| Turn / Scenario | Input Prompt | Executed Tasks | Result |
| :--- | :--- | :--- | :--- |
| **Turn A** | "Create a file called jarvis_session_test.txt containing HELLO." | `system.respond`, `file.create_file` | **PASSED** (File created on disk) |
| **Turn B** | "Read it back." | `system.respond`, `file.read_file` | **PASSED** (Resolved "it" -> `HELLO`) |
| **Turn C** | "Verify its contents." | `system.respond` | **PASSED** (Mission verified: 4/4 checks) |
| **Scenario D** | "Hello from isolated session" | `system.respond` | **PASSED** (Zero state leakage) |
| **Scenario E (Restart)** | "Read it back." (Post Agent destruction) | `system.respond`, `file.read_file` | **PASSED** (Resumed at Turn 4) |

---

## 13. Performance Scorecard
Measured during the live E2E run against local SQLite and Ollama:
- **Session Retrieval Latency**: 2.841 ms (sub-3ms database lookup).
- **Session Persistence Overhead**: ~1.2 ms per turn insert.
- **Context Tokens Contributed by Session**: 44 to 89 tokens (well within the 8,192 token context budget).
- **Total Persisted Turns in Live Run**: 4 turns.
- **Full Test Suite Regression**:
  - Total: 877 items (876 passed, 0 failed, 1 skipped, 1 warning).
  - Test Runtime: 27.45 seconds.

---

## 14. Remaining Limitations
1. **Model Cold Start**: The initial turn against local Ollama requires 30–60s when the model weights are loaded into VRAM from disk; subsequent turns complete in 30–40s (or sub-second for tool executions).
2. **Deterministic Context Window**: Sliding-window session retrieval currently retains up to 5 turns. If complex multi-turn sessions exceed 5 turns, semantic cross-turn referencing may require summarization hooks in future phases.
