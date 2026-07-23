# 📦 Modules Reference

> Detailed reference for every module in the Jarvis framework.

---

## Table of Contents

- [config/](#config)
- [core/](#core)
- [tools/](#tools)
- [memory/](#memory)
- [gui/](#gui)

---

## config/

### `config.py` — Configuration Management

**Purpose**: Loads and holds all application settings in a single immutable dataclass. Environment variables override defaults.

#### Public Classes

| Class | Description |
|---|---|
| `JarvisConfig` | Frozen dataclass containing all configuration parameters |

#### `JarvisConfig` Fields

| Field | Type | Default | Env Variable |
|---|---|---|---|
| `model` | `str` | `"qwen3:8b"` | `JARVIS_MODEL` |
| `ollama_host` | `str` | `"http://localhost:11434"` | `OLLAMA_HOST` |
| `max_retries` | `int` | `3` | `JARVIS_MAX_RETRIES` |
| `request_timeout` | `int` | `30` | `JARVIS_TIMEOUT` |
| `memory_db_path` | `str` | `~/.jarvis/memory.db` | `JARVIS_MEMORY_DB` |

#### Public Functions

| Function | Signature | Description |
|---|---|---|
| `load_config` | `() → JarvisConfig` | Loads config from env vars with defaults |

#### Dependencies

- `os` (stdlib)
- `pathlib` (stdlib)
- `dataclasses` (stdlib)

#### Future Improvements

- [ ] TOML/YAML config file support
- [ ] Config validation with error messages
- [ ] Hot-reload configuration
- [ ] Per-tool configuration sections

---

## core/

### `agent.py` — Pipeline Orchestrator

**Purpose**: Top-level coordinator that receives user input and drives it through the full pipeline: Planner → Validator → Executor. Never parses JSON, never calls the LLM, never executes tools directly.

#### Public Classes

| Class | Description |
|---|---|
| `Agent` | Orchestrates the Jarvis agent pipeline |

#### Public Methods

| Method | Signature | Description |
|---|---|---|
| `run` | `(user_input: str) → list[Task]` | Process user input through the full pipeline |

#### Key Internal Methods

| Method | Description |
|---|---|
| `_load_context` | Loads conversation history from memory |
| `_save_to_memory` | Stores current interaction in memory |
| `_process_task` | Validates and executes a single task |
| `_error_task` | Creates a failed task for pipeline-level errors |

#### Dependencies

- `Planner`, `Validator`, `Executor` — injected via constructor
- `MemoryManager` — optional, injected via constructor
- `JarvisError` — for pipeline-level error handling

#### Future Improvements

- [ ] Parallel task execution
- [ ] Task dependency graphs
- [ ] Retry logic for failed tasks
- [ ] Streaming task updates

---

### `planner.py` — Intent-to-Task Conversion

**Purpose**: Converts natural language into structured `Task` objects by building prompts, calling the LLM, parsing JSON, normalizing aliases, and creating tasks.

#### Public Classes

| Class | Description |
|---|---|
| `Planner` | Converts natural language into a list of Task objects |

#### Public Methods

| Method | Signature | Description |
|---|---|---|
| `plan` | `(user_input: str, context: str = "") → list[Task]` | Full planning pipeline |

#### Internal Pipeline

```
_build_system_prompt() → LLM.generate() → parse_json() → normalize() → _create_tasks()
```

#### Dependencies

- `LLMClient` — for model inference
- `Registry` — for dynamic prompt building
- `parse_json` — from `parser.py`
- `normalize` — from `normalizer.py`

#### Future Improvements

- [ ] Multi-turn planning (ask clarifying questions)
- [ ] Task priority/ordering hints
- [ ] Cost estimation before execution
- [ ] Fallback planning for parse failures

---

### `parser.py` — JSON Extraction

**Purpose**: Extracts structured JSON from raw LLM text that may contain markdown fences, thinking blocks (`<think>...</think>`), or other noise. Purely syntactic — no business logic.

#### Public Functions

| Function | Signature | Description |
|---|---|---|
| `parse_json` | `(text: str) → dict \| list[dict]` | Extract and parse JSON from raw LLM output |

#### Handles

- Qwen3 `<think>...</think>` blocks
- Markdown code fences (` ```json `, ` ``` `)
- Extracts first JSON object or array

#### Dependencies

- `json`, `re` (stdlib)
- `ParseError` from `exceptions.py`

#### Future Improvements

- [ ] Support YAML output fallback
- [ ] Partial JSON recovery
- [ ] Multiple JSON extraction
- [ ] Confidence scoring for extracted JSON

---

### `normalizer.py` — Alias Resolution

**Purpose**: Maps raw AI output to the internal canonical schema. Resolves tool aliases, action aliases, and argument aliases. Pure data transformation — never executes anything.

#### Public Functions

| Function | Signature | Description |
|---|---|---|
| `normalize` | `(raw: dict \| list[dict]) → list[dict]` | Normalize parsed LLM output into canonical action dicts |

#### Alias Maps

**Tool Aliases** (12 aliases → 3 canonical names):
```
application, app, desktop, program, system → windows
web, internet, chrome, edge, firefox       → browser
folder, directory, filesystem, files, folders, fs → file
```

**Action Aliases** (17 aliases → 10 canonical actions):
```
open, launch, start, run           → open_app
search, google, search_web         → search_google
navigate, go_to, browse            → open_url
visit                              → open_site
ls, dir, list, list_files          → list_directory
mkdir, make_folder, create_directory, new_folder → create_folder
rm, remove                         → delete
mv                                 → move
cp, duplicate                      → copy
```

**Argument Aliases** (17 aliases → 5 canonical names):
```
name, program, application, app_name → app
link, address, website, webpage      → url
site_name, website_name              → site
search_query, search_term, search, text → query
folder, directory, file_path, folder_path, dir, source, from → path
destination, target, to             → dest
```

#### Dependencies

- None (pure Python only)

#### Future Improvements

- [ ] Fuzzy matching for close-but-not-exact aliases
- [ ] Configurable alias files
- [ ] Tool-specific alias scoping
- [ ] Learning from user corrections

---

### `validator.py` — Safety Gate

**Purpose**: Checks that every Task references a known tool and a valid action for that tool. Rejects anything unknown before it can reach the Executor.

#### Public Classes

| Class | Description |
|---|---|
| `Validator` | Validates Task objects against the Registry |

#### Public Methods

| Method | Signature | Description |
|---|---|---|
| `validate` | `(task: Task) → Task` | Validate tool and action existence |

#### Validation Checks

1. **Tool exists** — `registry.has_tool(task.tool)`
2. **Action exists** — `task.action in registry.get_actions(task.tool)`

#### Dependencies

- `Registry` — for tool/action lookup
- `ValidationError` from `exceptions.py`

#### Future Improvements

- [ ] Argument type validation
- [ ] Required argument checks
- [ ] Permission/capability checks
- [ ] Rate limiting per tool

---

### `executor.py` — Task Runner

**Purpose**: Runs validated Task objects against registered tools. Manages the `PENDING → RUNNING → COMPLETED/FAILED` lifecycle transition.

#### Public Classes

| Class | Description |
|---|---|
| `Executor` | Executes validated Task objects using registered tools |

#### Public Methods

| Method | Signature | Description |
|---|---|---|
| `execute` | `(task: Task) → Task` | Execute a single validated task |

#### Error Handling

| Exception | Handling |
|---|---|
| `ExecutionError` | Task marked as FAILED with error message |
| Any `Exception` | Caught, logged with traceback, task FAILED |

#### Dependencies

- `Registry` — for tool lookup via `get_executor()`
- `ExecutionError` from `exceptions.py`

#### Future Improvements

- [ ] Execution timeout per task
- [ ] Parallel execution for independent tasks
- [ ] Retry with exponential backoff
- [ ] Execution sandboxing

---

### `registry.py` — Tool Registry

**Purpose**: Single source of truth for available tools. Holds all registered `BaseTool` instances and provides lookup, validation, and description generation.

#### Public Classes

| Class | Description |
|---|---|
| `Registry` | Manages tool registration, lookup, and description generation |

#### Public Methods

| Method | Signature | Description |
|---|---|---|
| `register` | `(tool: BaseTool) → None` | Register a tool instance |
| `has_tool` | `(name: str) → bool` | Check if a tool is registered |
| `get_executor` | `(name: str) → Optional[BaseTool]` | Get tool instance for execution |
| `get_actions` | `(name: str) → dict[str, str]` | Get actions for a tool |
| `list_tools` | `() → list[str]` | List all registered tool names |
| `describe` | `() → str` | Generate tool descriptions for LLM prompts |

#### Dependencies

- `BaseTool` from `tools.base_tool`

#### Future Improvements

- [ ] Tool versioning
- [ ] Dynamic unregister
- [ ] Plugin directory scanning
- [ ] Tool capability queries

---

### `task.py` — Work Unit

**Purpose**: Dataclass representing a single unit of work in the pipeline. Carries tool, action, arguments, status, result, and error. State transitions are guarded.

#### Public Classes

| Class | Description |
|---|---|
| `Task` | One executable unit of work |
| `TaskStatus` | Lifecycle states enum (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`) |

#### Task Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `tool` | `str` | required | Tool name (e.g. `"windows"`) |
| `action` | `str` | required | Action name (e.g. `"open_app"`) |
| `args` | `dict` | `{}` | Action arguments |
| `status` | `TaskStatus` | `PENDING` | Current lifecycle state |
| `result` | `Any` | `None` | Execution result |
| `error` | `str` | `""` | Error message |

#### State Machine

```
PENDING ──▶ RUNNING ──▶ COMPLETED
                  └──▶ FAILED
```

#### Public Methods

| Method | Signature | Description |
|---|---|---|
| `start` | `() → None` | PENDING → RUNNING |
| `complete` | `(result: Any) → None` | RUNNING → COMPLETED |
| `fail` | `(error: str) → None` | RUNNING → FAILED |
| `is_terminal` | `→ bool` (property) | Whether task is COMPLETED or FAILED |

#### Dependencies

- `InvalidStateError` from `exceptions.py`

---

### `llm.py` — Ollama Client

**Purpose**: Pure I/O boundary to Ollama. Sends prompts and returns raw text. No parsing, no normalizing, no planning logic.

#### Public Classes

| Class | Description |
|---|---|
| `LLMClient` | Thin wrapper around Ollama chat API |

#### Public Methods

| Method | Signature | Description |
|---|---|---|
| `generate` | `(system_prompt: str, user_prompt: str) → str` | Send prompts, return raw response |

#### Dependencies

- `ollama` SDK (`chat`, `ResponseError`, `RequestError`)
- `JarvisConfig` for model name and host
- `LLMConnectionError` from `exceptions.py`

#### Future Improvements

- [ ] Streaming response support
- [ ] Token counting / budget management
- [ ] Model switching at runtime
- [ ] Response caching for repeated queries

---

### `exceptions.py` — Exception Hierarchy

**Purpose**: Unified exception hierarchy so callers can catch all framework errors with a single `except JarvisError` or target specific failure modes.

#### Exception Tree

```
JarvisError (base)
├── LLMConnectionError      — Ollama unreachable or API error
├── ParseError               — JSON extraction from LLM output failed
├── ValidationError          — Unknown tool, action, or missing args
├── ExecutionError           — Tool execution failure
├── InvalidStateError        — Illegal Task state transition
└── MemoryError              — Memory storage/retrieval failure
```

---

## tools/

### `base_tool.py` — Tool Contract

**Purpose**: Abstract base class defining the contract for all Jarvis tools. The Registry only accepts `BaseTool` instances.

#### Abstract Interface

| Member | Type | Description |
|---|---|---|
| `name` | `property → str` | Unique tool identifier |
| `description` | `property → str` | Human-readable description for LLM prompts |
| `get_actions` | `() → dict[str, str]` | Available actions with descriptions |
| `execute` | `(action: str, args: dict) → str` | Execute an action, return result string |

### `browser.py` — Browser Tool

See [TOOLS.md](TOOLS.md#-browser-tool) for full documentation.

### `windows.py` — Windows Tool

See [TOOLS.md](TOOLS.md#-windows-tool) for full documentation.

### `file.py` — File Tool

See [TOOLS.md](TOOLS.md#-file-tool) for full documentation.

---

## memory/

### `base_memory.py` — Memory Backend Contract

**Purpose**: Abstract base class defining the interface for all memory implementations. Allows swapping SQLite for any other storage.

#### Abstract Interface

| Method | Signature | Description |
|---|---|---|
| `store` | `(entry: MemoryEntry) → None` | Persist a memory entry |
| `get_recent` | `(limit: int) → list[MemoryEntry]` | Retrieve recent entries |
| `search` | `(query: str, limit: int) → list[MemoryEntry]` | Search by keyword |
| `clear` | `() → None` | Delete all entries |

### `models.py` — Data Models

See [MEMORY.md](MEMORY.md) for full documentation.

### `memory_manager.py` — High-Level Interface

See [MEMORY.md](MEMORY.md) for full documentation.

### `sqlite_memory.py` — SQLite Backend

See [MEMORY.md](MEMORY.md) for full documentation.

---

## gui/

### Package Overview

The GUI is a PySide6 desktop application structured as:

```
gui/
├── __init__.py          → launch_gui() entry point
├── main_window.py       → Application shell
├── splash.py            → Branded splash screen
├── header.py            → Top bar
├── sidebar.py           → Navigation panel
├── footer.py            → Status strip
├── themes/              → Semantic theme engine
│   ├── theme.py         → Theme dataclass + ThemeManager + QSS builder
│   ├── dark.py          → GitHub Dark palette
│   ├── light.py         → Clean white palette
│   └── amoled.py        → Pure black OLED palette
├── views/               → Stacked page views
│   ├── chat_view.py     → Main chat with Agent worker
│   ├── memory_view.py   → Memory browser with search
│   ├── history_view.py  → History grouped by date
│   ├── logs_view.py     → Live log viewer
│   ├── plugins_view.py  → Tool inspector
│   └── settings_view.py → Theme + model + about
└── widgets/             → Reusable components
    ├── chat_widget.py   → Scrollable bubble history
    ├── input_widget.py  → Auto-growing message input
    ├── task_card.py     → Task result card
    └── thinking_indicator.py → Animated loading bubble
```

### Key Classes

| Class | Module | Description |
|---|---|---|
| `MainWindow` | `main_window.py` | Application shell composing all panels |
| `ChatView` | `views/chat_view.py` | Primary interaction surface |
| `ThemeManager` | `themes/theme.py` | Singleton managing active theme |
| `ChatWidget` | `widgets/chat_widget.py` | Rich message bubble display |
| `InputWidget` | `widgets/input_widget.py` | Multi-line auto-grow input |

### Signals Architecture

```
InputWidget.message_submitted ──▶ ChatView._on_send
ChatView.status_changed ──▶ Footer.set_status
ChatView.response_time ──▶ Footer.set_response_time
Sidebar.page_changed ──▶ MainWindow._on_page_changed
Header.settings_clicked ──▶ MainWindow._navigate_to("settings")
ThemeManager.theme_changed ──▶ MainWindow._on_theme_changed
```

#### Future Improvements

- [ ] Plugin marketplace view
- [ ] Voice input widget
- [ ] Vision/image input
- [ ] Task queue panel
- [ ] System tray integration
- [ ] Window resize/snap behaviors
- [ ] Custom fonts and font-size settings
