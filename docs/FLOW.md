# 🔄 Execution Flow

> Complete execution flow from User Input to Response.

---

## Overview

Every interaction in Jarvis follows a deterministic pipeline:

```
User Input → Agent → Planner → LLM → Parser → Normalizer → Tasks
                                                                │
                                          ┌─────────────────────┘
                                          ▼
                                   Validator → Executor → Registry → Tool → Response
```

This document traces the complete journey of a user request through the system.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Complete Execution Flow                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 1. USER INPUT                                            │       │
│  │    "open calculator and search google for Python"        │       │
│  └────────────────────────┬─────────────────────────────────┘       │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 2. AGENT (Orchestrator)                                   │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ a. Load context from Memory                     │    │       │
│  │    │    MemoryManager.get_context() → MemoryContext   │    │       │
│  │    │    Returns formatted conversation history        │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ b. Delegate to Planner                          │    │       │
│  │    │    planner.plan(user_input, context=context)     │    │       │
│  │    └────────────────────┬────────────────────────────┘    │       │
│  └─────────────────────────┼────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 3. PLANNER                                                │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ a. Build system prompt                          │    │       │
│  │    │    - Query Registry.describe() for tool list    │    │       │
│  │    │    - Inject tool descriptions + context         │    │       │
│  │    │    - Format _SYSTEM_PROMPT_TEMPLATE             │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ b. Call LLM                                     │    │       │
│  │    │    llm.generate(system_prompt, user_input)      │    │       │
│  │    │    → sends to Ollama → returns raw text         │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ c. Parse JSON                                   │    │       │
│  │    │    parse_json(raw_response)                     │    │       │
│  │    │    - Strip <think>...</think> blocks            │    │       │
│  │    │    - Remove markdown code fences                │    │       │
│  │    │    - Extract first JSON object or array         │    │       │
│  │    │    - json.loads() → dict or list[dict]          │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ d. Normalize                                    │    │       │
│  │    │    normalize(parsed)                            │    │       │
│  │    │    - Map tool aliases → canonical names         │    │       │
│  │    │    - Map action aliases → canonical actions     │    │       │
│  │    │    - Map arg aliases → canonical arg names      │    │       │
│  │    │    - Lowercase all values                       │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ e. Create Tasks                                 │    │       │
│  │    │    For each normalized dict → Task(PENDING)     │    │       │
│  │    │    Returns list[Task]                           │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  └──────────────────────────────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 4. AGENT — Per-Task Processing Loop                       │       │
│  │                                                           │       │
│  │    for each task in tasks:                                │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ a. VALIDATOR                                    │    │       │
│  │    │    validator.validate(task)                     │    │       │
│  │    │    - Check: registry.has_tool(task.tool)?       │    │       │
│  │    │    - Check: task.action in tool.get_actions()?  │    │       │
│  │    │    - On failure: ValidationError → task FAILED  │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  │                         │                                 │       │
│  │                         ▼ (if valid)                      │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ b. EXECUTOR                                     │    │       │
│  │    │    executor.execute(task)                       │    │       │
│  │    │    - task.start()        → PENDING → RUNNING   │    │       │
│  │    │    - registry.get_executor(task.tool)           │    │       │
│  │    │    - tool.execute(task.action, task.args)       │    │       │
│  │    │    - task.complete(result) or task.fail(error)  │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  │                         │                                 │       │
│  │                         ▼                                 │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ c. REGISTRY → TOOL                              │    │       │
│  │    │    registry._tools["windows"] → WindowsTool     │    │       │
│  │    │    WindowsTool.execute("open_app", {"app":"calc"})│   │       │
│  │    │    → subprocess.Popen("calc")                   │    │       │
│  │    │    → "Opened calculator"                        │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  └──────────────────────────────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 5. AGENT — Post-Processing                                │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ a. Save to Memory                               │    │       │
│  │    │    memory.store_interaction(user_input, tasks)   │    │       │
│  │    │    → Serialize tasks → MemoryEntry → SQLite     │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  │    ┌─────────────────────────────────────────────────┐    │       │
│  │    │ b. Return Results                               │    │       │
│  │    │    return list[Task] with final states           │    │       │
│  │    └─────────────────────────────────────────────────┘    │       │
│  └──────────────────────────────────────────────────────────┘       │
│                            │                                        │
│                            ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ 6. RESPONSE                                               │       │
│  │    GUI: Chat bubble / task cards displayed                │       │
│  │    CLI: "✓ Opened calculator"                             │       │
│  └──────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Concrete Example

### Input: `"open calculator and search google for Python tutorials"`

#### Step 1 — Agent Receives Input

```python
agent.run("open calculator and search google for Python tutorials")
```

#### Step 2 — Memory Context Loading

```python
context = memory_manager.get_context()
# Returns: "Previous conversation:\n- User: open notepad\n  Result: Opened notepad"
```

#### Step 3 — Planner Builds System Prompt

```
You are Jarvis, an AI operating system.

You must ONLY use the tools listed below.
Return ONLY valid JSON — no explanation, no markdown, no code fences.

Available tools:

Tool: windows
Description: Control Windows desktop applications
Actions:
  - open_app: Opens a Windows application. Requires 'app' argument. Known apps: notepad, calculator, ...

Tool: browser
Description: Open websites, URLs, and perform Google searches
Actions:
  - open_url: Opens a URL in the default browser. Requires 'url' argument.
  - open_site: Opens a known website by name. Requires 'site' argument. ...
  - search_google: Searches Google with a query. Requires 'query' argument.

Tool: file
Description: Manage files and directories on the local filesystem
Actions:
  - list_directory: Lists contents of a directory. Requires 'path' argument.
  ...

Previous conversation:
- User: open notepad
  Result: Opened notepad
```

#### Step 4 — LLM Response

```json
[
  {"tool": "windows", "action": "open_app", "args": {"app": "calculator"}},
  {"tool": "browser", "action": "search_google", "args": {"query": "Python tutorials"}}
]
```

#### Step 5 — Parser

- Strips any `<think>...</think>` blocks
- Removes any ` ```json ` fences
- Extracts JSON array
- Returns `list[dict]`

#### Step 6 — Normalizer

```python
# Input:  {"tool": "windows", "action": "open_app", "args": {"app": "calculator"}}
# Output: {"tool": "windows", "action": "open_app", "args": {"app": "calculator"}}
# (already canonical — no changes needed)
```

#### Step 7 — Task Creation

```python
Task(tool="windows", action="open_app", args={"app": "calculator"}, status=PENDING)
Task(tool="browser", action="search_google", args={"query": "python tutorials"}, status=PENDING)
```

#### Step 8 — Validation (Task 1)

```python
validator.validate(task1)
# ✓ registry.has_tool("windows") → True
# ✓ "open_app" in windows_tool.get_actions() → True
```

#### Step 9 — Execution (Task 1)

```python
executor.execute(task1)
# task.start()  → status = RUNNING
# tool = registry.get_executor("windows")  → WindowsTool
# result = tool.execute("open_app", {"app": "calculator"})
#   → subprocess.Popen("calc")
#   → "Opened calculator"
# task.complete("Opened calculator")  → status = COMPLETED
```

#### Step 10 — Validation & Execution (Task 2)

```python
# Same flow for search_google
# → webbrowser.open("https://www.google.com/search?q=python+tutorials")
# → "Searched Google for 'python tutorials'"
```

#### Step 11 — Memory Storage

```python
memory_manager.store_interaction(
    "open calculator and search google for Python tutorials",
    [task1, task2]
)
# → MemoryEntry(summary="open calculator and search... → 2 completed")
# → SQLite INSERT
```

#### Step 12 — Response

```
  ✓ Opened calculator
  ✓ Searched Google for 'python tutorials'
```

---

## GUI-Specific Flow

When running in GUI mode, the flow has additional steps for threading and UI updates:

```
┌────────────────────────────────────────────────────────┐
│                   GUI Execution Flow                    │
│                                                        │
│  InputWidget                                           │
│  ├── User types message + presses Enter                │
│  ├── message_submitted signal → ChatView._on_send      │
│  │                                                     │
│  ChatView._on_send                                     │
│  ├── Append user bubble to ChatWidget                  │
│  ├── Disable InputWidget                               │
│  ├── Show ThinkingIndicator (animated)                 │
│  ├── Emit status_changed("thinking") → Footer          │
│  ├── Create _AgentWorker on QThread                    │
│  │   └── worker.run() calls agent.run() on bg thread   │
│  │                                                     │
│  _AgentWorker (background thread)                      │
│  ├── Runs full pipeline (steps 2-11 above)             │
│  ├── Emits finished(tasks, duration) signal            │
│  │                                                     │
│  ChatView._on_results (main thread, via signal)        │
│  ├── Remove ThinkingIndicator                          │
│  ├── Display results as bubbles or TaskCards           │
│  ├── Emit status_changed("idle") → Footer              │
│  ├── Emit response_time(duration) → Footer             │
│  ├── Re-enable InputWidget                             │
│  └── Cleanup worker + thread                           │
└────────────────────────────────────────────────────────┘
```

---

## Error Flow

Errors are handled at every stage without crashing the pipeline:

```
┌─────────────────────────────────────────────────────────┐
│                     Error Handling                       │
│                                                         │
│  LLM Unreachable                                        │
│  └── LLMConnectionError → Agent catches JarvisError     │
│      └── Returns [Task(status=FAILED, error="...")]     │
│                                                         │
│  Invalid JSON from LLM                                  │
│  └── ParseError → Agent catches JarvisError             │
│      └── Returns [Task(status=FAILED, error="...")]     │
│                                                         │
│  Unknown Tool/Action                                    │
│  └── ValidationError → Agent catches JarvisError        │
│      └── task.fail(str(exc))                            │
│                                                         │
│  Tool Execution Failure                                 │
│  └── ExecutionError → Executor catches                  │
│      └── task.fail(str(exc))                            │
│                                                         │
│  Unexpected Exception                                   │
│  └── Executor catches Exception                         │
│      └── task.fail(f"Unexpected error: {exc}")          │
│                                                         │
│  Memory Failure                                         │
│  └── Warning logged, pipeline continues normally        │
└─────────────────────────────────────────────────────────┘
```

---

## Task State Machine

```
                    ┌──────────┐
    Task created ──▶│ PENDING  │
                    └────┬─────┘
                         │ start()
                         ▼
                    ┌──────────┐
                    │ RUNNING  │
                    └──┬────┬──┘
           complete()  │    │  fail()
                       ▼    ▼
                 ┌────────┐ ┌────────┐
                 │COMPLETED│ │ FAILED │
                 └────────┘ └────────┘
                      (terminal states)
```

Invalid transitions raise `InvalidStateError`:
- `PENDING → COMPLETED` ❌
- `PENDING → FAILED` ❌
- `COMPLETED → anything` ❌
- `FAILED → anything` ❌
