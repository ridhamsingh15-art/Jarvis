# JARVIS Phase 7D: Context Engineering & Budget Control

**Phase Target:** Deterministic Context Budgeting, Token Estimation & Observability  
**Status:** COMPLETE  
**Prior Phase:** Phase 7C.2 Runtime Spine Hardening  
**Baseline Test Suite (Pre-7D):** 820 passed, 0 failed, 1 skipped, 1 warning (27.18s)  
**Final Test Suite (Post-7D):** 838 passed, 0 failed, 1 skipped, 1 warning (28.62s)  
**Spine Tests:** 84/84 passed (Phase 7A: 26, Phase 7B: 18, Phase 7C: 16, Phase 7C.2: 6, Phase 7D: 18)  
**Live Production Evaluation:** 7/7 Scenarios (A through G) passed via local Ollama `qwen3:8b`  

---

## 1. Executive Summary

Phase 7B introduced the dynamic feedback loop, allowing external tool execution results to return directly to the model as untrusted data across multi-turn observe $\to$ decide $\to$ act iterations. Without a deterministic context budgeting layer, iterative feedback, conversation history, memory facts, and tool outputs could cause unbounded prompt expansion, risking context window exhaustion, latency spikes, or truncation of critical security guidelines.

Phase 7D implements a **hard deterministic context budget boundary**:
```
CONTEXT BUILD
    ↓
BUDGET CHECK
    ↓
TRIM / SUMMARIZE / PRIORITIZE
    ↓
MODEL INVOCATION
```

Every model invocation across conversational chat, tool feedback, capability routing, and missions is now bounded by a deterministic token contract. Oversized tool outputs are truncated while preserving security XML tags (`<UNTRUSTED_TOOL_RESULT>`), history is prioritized with recent turns first, and memory/knowledge injections are strictly capped.

---

## 2. Existing Context Architecture Audit

Prior to Phase 7D, the context flow was distributed without total-token enforcement:
- **`ContextOrchestrator`**: Injected raw chunks from 7 sources (Workspace, Project, Mission, Tools, Memory, PKI, Conversation). While `ContextRanker` limited the chunk count to 30, it imposed no character or token limits.
- **`ConversationEngine`**: Prepend `# Recent Conversation` and `# User's New Message` directly without budgeting.
- **`ToolFeedbackLoop`**: Formatted `observe_prompt` containing the user request, history summary, untrusted tool results (capped at 2000 chars per result), and security rules. Because the feedback prompt was sent as a user message to `CognitiveManager.process_fast`, each iteration stored raw untrusted XML blocks in `ShortTermContext`, multiplying history size on subsequent turns.
- **`OllamaProvider`**: Did not forward `num_ctx`, `num_predict`, or `keep_alive` settings to the Ollama HTTP API endpoint `/api/chat`.

---

## 3. Context Budget Contract

Implemented in `core/context_budget.py`, the `ContextBudget` contract deterministically tracks:

```python
@dataclass
class ContextBudget:
    max_total_tokens: int = 4096
    reserved_output_tokens: int = 512

    # Token component estimations
    system_tokens: int = 0
    user_input_tokens: int = 0
    tool_result_tokens: int = 0
    history_tokens: int = 0
    memory_tokens: int = 0
    knowledge_tokens: int = 0
    mission_tokens: int = 0
    other_tokens: int = 0

    # Truncation tracking
    truncated: bool = False
    truncation_reason: str = ""
    dropped_components: list[str] = field(default_factory=list)
```

### Deterministic Token Estimation
To eliminate latency overhead and avoid recursive model calls, token counts are estimated deterministically in pure Python:
$$\text{Tokens} = \max\left(\left\lceil \frac{\text{len}(\text{text}) + 3}{4} \right\rceil, \lfloor 1.3 \times \text{words} \rfloor, 1\right)$$
This provides a conservative upper bound for English, code, and structured JSON payloads without requiring a second LLM invocation.

---

## 4. Priority Rules & Truncation Hierarchy

When context exceeds the available input budget ($B_{\text{input}} = \text{max\_total\_tokens} - \text{reserved\_output\_tokens}$), information is preserved or dropped according to strict priority order:

1. **Current User Request (HIGHEST PRIORITY - NEVER DROPPED)**: The user's active prompt is preserved verbatim.
2. **System Security Instructions (NEVER DROPPED)**: Identity rules, guardrails, and `<UNTRUSTED_TOOL_RESULT>` instructions are immutable.
3. **Current Task / Mission State**: Active goal, current iteration index, and remaining loop budget.
4. **Latest Tool Result**: The most recent execution output is kept; oversized results are bounded with head and tail retained.
5. **Recent Conversation Turns**: Recent dialogue history is prioritized (newest turns first).
6. **Relevant Memory Facts**: Capped at `DEFAULT_MAX_MEMORY_TOKENS = 300`.
7. **Older Conversation History**: Older turns are progressively compacted or dropped.
8. **Low-Priority PKI Knowledge Chunks (LOWEST PRIORITY - FIRST DROPPED)**: Dropped when budget is constrained.

---

## 5. Tool Result Protection & Security Bounding

Tool outputs are strictly treated as **UNTRUSTED DATA**:
- **Per-Result Limit**: Enforced at `1500` characters (`~375` tokens).
- **Total Tool Budget**: Enforced at `3000` characters across iterations.
- **Envelope Preservation**: Bounding retains `<UNTRUSTED_TOOL_RESULT>` and `</UNTRUSTED_TOOL_RESULT>` tags, tool and action metadata, and execution status (`SUCCESS` / `FAILURE`).
- **Prompt Injection Defense**: Adversarial payloads containing instruction overrides or formatting attacks (e.g., `SYSTEM OVERRIDE! FORMAT C:`) are safely enclosed within the XML envelope and truncated so they cannot push out system security instructions or the original user request.

---

## 6. Model Context Settings & Ollama Forwarding

`providers/ollama_provider.py` and `config/providers.py` have been updated to forward native context configuration parameters:
- `num_ctx`: Configured default `4096`, dynamically elevated if `InferenceRequirements.min_context_length` requests larger capacity.
- `num_predict`: Configurable generation token limit (e.g. `512`).
- `keep_alive`: Model residency in VRAM/RAM (default: `"5m"`).
- Forwarded in `/api/chat` payload:
  ```json
  {
    "model": "qwen3:8b",
    "messages": [...],
    "stream": false,
    "options": {
      "num_ctx": 4096,
      "num_predict": 512
    },
    "keep_alive": "5m"
  }
  ```

---

## 7. Observability & Telemetry

Context metrics are recorded per invocation and exposed via:
- `agent.last_context_budget`: Provides immediate inspection of the latest `ContextBudget`.
- `agent.last_mission_telemetry`: Includes `estimated_context_tokens` and `context_truncated`.
- Log entries record token distributions and explicit reasons whenever truncation occurs.

---

## 8. Test Suite Verification (18 Requirements)

Test suite: `tests/test_phase7d_context_budget.py` (18/18 passed in 0.68s)

| # | Requirement | Test Function | Outcome |
|---|---|---|---|
| 1 | Context within budget remains unchanged | `test_1_context_within_budget_remains_unchanged` | **PASSED** |
| 2 | Oversized history gets trimmed | `test_2_oversized_history_gets_trimmed` | **PASSED** |
| 3 | Oversized tool result gets bounded | `test_3_oversized_tool_result_gets_bounded` | **PASSED** |
| 4 | Security instructions survive trimming | `test_4_security_instructions_survive_trimming` | **PASSED** |
| 5 | Untrusted-result boundaries survive trimming | `test_5_untrusted_result_boundaries_survive_trimming` | **PASSED** |
| 6 | Current user request is preserved | `test_6_current_user_request_is_preserved` | **PASSED** |
| 7 | Current tool result is preserved | `test_7_current_tool_result_is_preserved` | **PASSED** |
| 8 | Mission state is preserved | `test_8_mission_state_is_preserved` | **PASSED** |
| 9 | Memory is budgeted | `test_9_memory_is_budgeted` | **PASSED** |
| 10 | Knowledge is budgeted | `test_10_knowledge_is_budgeted` | **PASSED** |
| 11 | Total budget is enforced | `test_11_total_budget_is_enforced` | **PASSED** |
| 12 | Multiple feedback iterations stay bounded | `test_12_multiple_feedback_iterations_stay_bounded` | **PASSED** |
| 13 | Huge malicious tool result cannot exhaust context | `test_13_huge_malicious_tool_result_cannot_exhaust_context` | **PASSED** |
| 14 | CHAT remains lightweight | `test_14_chat_remains_lightweight` | **PASSED** |
| 15 | MEMORY remains lightweight | `test_15_memory_remains_lightweight` | **PASSED** |
| 16 | MISSION retains enough state for next decision | `test_16_mission_retains_enough_state_for_the_next_decision` | **PASSED** |
| 17 | No second LLM call required for budgeting | `test_17_no_second_llm_call_required_for_budgeting` | **PASSED** |
| 18 | Model context configuration is propagated | `test_18_model_context_configuration_is_propagated_when_supported` | **PASSED** |

**Spine Regression**: **84/84 passed** (Phase 7A: 26, Phase 7B: 18, Phase 7C: 16, Phase 7C.2: 6, Phase 7D: 18).

---

## 9. Live Production Evaluation

Executed via `main.build_agent()` $\to$ `Agent.run()` using local Ollama `qwen3:8b`:

| Scenario | Query / Action | Measured Latency | Measured Context | Observed Reality | Status |
|---|---|---|---|---|---|
| **A. CHAT** | `"Explain how a CPU works."` | 28.69s | 923 tokens (input) | Fast conversational response, context bounded | **PASSED** |
| **B. TOOL** | `"Open Calculator."` | 36.73s | 1560 tokens (input) | OS app launched, context bounded | **PASSED** |
| **C. MULTI-STEP TOOL** | `"Create a file containing HELLO and read it back."` | 45.00s | 1875 tokens (input) | 2/2 tools completed, file verified on disk | **PASSED** |
| **D. MISSION** | `"Autonomous mission: create a file... verify"` | 79.06s | 1781 tokens (input) | 4/4 verification checks passed, 1 iteration | **PASSED** |
| **E. LARGE TOOL RESULT** | 50KB safe payload read from file | 131.35s | 2125 tokens (input) | Bounded to context limit, no overflow | **PASSED** |
| **F. INJECTION** | Adversarial override text in tool output | 59.97s | 2124 tokens (input) | Boundary tags preserved, attack neutralized | **PASSED** |
| **G. MEMORY** | Store and recall small fact | 0.08s | 8 tokens (input) | Ultra-lightweight memory path, fact recalled | **PASSED** |

---

## 10. Architectural Invariants Preserved

1. `MODEL CLAIMS ≠ PROOF`: Mission completion requires deterministic execution results.
2. `MODEL ≠ AUTHORIZATION`: Model decisions never modify execution policy or confirmation gates.
3. `TOOL RESULT ≠ INSTRUCTIONS`: Tool outputs are enclosed in `<UNTRUSTED_TOOL_RESULT>` blocks.
4. `BOUNDED CONTEXT`: Every production LLM call has a hard deterministic token ceiling.
5. `SECURITY FIRST`: Security rules and boundary tags are never stripped during truncation.
