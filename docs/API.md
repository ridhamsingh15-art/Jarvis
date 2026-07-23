# 📡 Internal API Reference

> Reference for every internal interface, class, and function in Jarvis.

---

## Table of Contents

- [Entry Point](#entry-point)
- [Configuration API](#configuration-api)
- [Core Pipeline API](#core-pipeline-api)
- [Tool API](#tool-api)
- [Memory API](#memory-api)
- [GUI API](#gui-api)
- [Exception API](#exception-api)

---

## Entry Point

### `main.py`

| Function | Signature | Description |
|---|---|---|
| `main` | `() → None` | Entry point — launches GUI or CLI |
| `build_agent` | `() → dict` | Wire all components, return agent context |
| `setup_logging` | `() → None` | Configure structured logging |
| `parse_args` | `() → argparse.Namespace` | Parse `--cli` flag |
| `repl` | `(agent: Agent) → None` | Interactive terminal REPL |
| `display_results` | `(tasks: list) → None` | Print task results to stdout |

### `build_agent()` Return Dict

```python
{
    "agent": Agent,              # Fully constructed Agent
    "config": JarvisConfig,      # Configuration instance
    "registry": Registry,        # Tool registry (read-only)
    "memory": SqliteMemory,      # Memory backend (read-only)
    "model_name": str,           # Display name of current model
    "memory_backend": str,       # "SQLite"
    "tool_count": int,           # Number of registered tools
}
```

---

## Configuration API

### `JarvisConfig`

```python
@dataclass(frozen=True)
class JarvisConfig:
    model: str = "qwen3:8b"
    ollama_host: str = "http://localhost:11434"
    max_retries: int = 3
    request_timeout: int = 30
    memory_db_path: str = "~/.jarvis/memory.db"
```

### `load_config`

```python
def load_config() -> JarvisConfig
```

Loads from environment variables with defaults. See `config/config.py` for variable names.

---

## Core Pipeline API

### `Agent`

The top-level orchestrator. Only entry point for external callers.

```python
class Agent:
    def __init__(
        self,
        planner: Planner,
        validator: Validator,
        executor: Executor,
        memory: MemoryManager | None = None,
    ) -> None: ...

    def run(self, user_input: str) -> list[Task]: ...
```

#### `Agent.run()` Contract

| Aspect | Guarantee |
|---|---|
| **Input** | Any non-empty string |
| **Output** | Always returns `list[Task]`, never empty |
| **Errors** | Pipeline errors → `Task(status=FAILED)`, never raises |
| **Memory** | Loads context before planning, saves after execution |
| **Thread Safety** | Not thread-safe; use one instance per thread |

---

### `Planner`

```python
class Planner:
    def __init__(self, llm: LLMClient, registry: Registry) -> None: ...

    def plan(self, user_input: str, context: str = "") -> list[Task]: ...
```

#### `Planner.plan()` Contract

| Aspect | Guarantee |
|---|---|
| **Input** | Natural language string + optional context |
| **Output** | `list[Task]` in PENDING state |
| **Raises** | `LLMConnectionError`, `ParseError` |

---

### `Validator`

```python
class Validator:
    def __init__(self, registry: Registry) -> None: ...

    def validate(self, task: Task) -> Task: ...
```

#### `Validator.validate()` Contract

| Aspect | Guarantee |
|---|---|
| **Input** | `Task` in any state |
| **Output** | Same `Task` unchanged (for chaining) |
| **Raises** | `ValidationError` if tool or action not found |

---

### `Executor`

```python
class Executor:
    def __init__(self, registry: Registry) -> None: ...

    def execute(self, task: Task) -> Task: ...
```

#### `Executor.execute()` Contract

| Aspect | Guarantee |
|---|---|
| **Input** | Validated `Task` in PENDING state |
| **Output** | Same `Task` in COMPLETED or FAILED state |
| **Side Effects** | Calls `tool.execute()`, which may launch processes, open browsers, etc. |
| **Raises** | Never — all errors caught and stored in `task.error` |

---

### `LLMClient`

```python
class LLMClient:
    def __init__(self, config: JarvisConfig) -> None: ...

    def generate(self, system_prompt: str, user_prompt: str) -> str: ...
```

#### `LLMClient.generate()` Contract

| Aspect | Guarantee |
|---|---|
| **Input** | System prompt + user prompt |
| **Output** | Raw text from Ollama |
| **Raises** | `LLMConnectionError` on network/API failure |

---

### `Registry`

```python
class Registry:
    def __init__(self) -> None: ...

    def register(self, tool: BaseTool) -> None: ...
    def has_tool(self, name: str) -> bool: ...
    def get_executor(self, name: str) -> Optional[BaseTool]: ...
    def get_actions(self, name: str) -> dict[str, str]: ...
    def list_tools(self) -> list[str]: ...
    def describe(self) -> str: ...
```

#### Method Contracts

| Method | Raises | Notes |
|---|---|---|
| `register` | `TypeError` if not `BaseTool`, `ValueError` if duplicate | Logs on success |
| `has_tool` | Never | Pure lookup |
| `get_executor` | Never | Returns `None` if not found |
| `get_actions` | Never | Returns `{}` if not found |
| `list_tools` | Never | Returns tool names in registration order |
| `describe` | Never | Formatted string for LLM prompts |

---

### `Task`

```python
@dataclass
class Task:
    tool: str
    action: str
    args: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""

    def start(self) -> None: ...
    def complete(self, result: Any = None) -> None: ...
    def fail(self, error: str) -> None: ...
    is_terminal: bool  # property
```

### `TaskStatus`

```python
class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```

---

### `parse_json`

```python
def parse_json(text: str) -> dict | list[dict]
```

| Aspect | Guarantee |
|---|---|
| **Input** | Raw LLM text (may contain noise) |
| **Output** | Parsed dict or list of dicts |
| **Raises** | `ParseError` if no valid JSON found |

---

### `normalize`

```python
def normalize(raw: dict | list[dict]) -> list[dict]
```

| Aspect | Guarantee |
|---|---|
| **Input** | Single dict or list of dicts |
| **Output** | Always `list[dict]`, aliases resolved, values lowercased |
| **Raises** | Never |

---

## Tool API

### `BaseTool` (Abstract)

```python
class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def get_actions(self) -> dict[str, str]: ...

    @abstractmethod
    def execute(self, action: str, args: dict) -> str: ...
```

#### Implementation Contract

| Member | Required | Notes |
|---|---|---|
| `name` | Yes | Must be unique across all tools |
| `description` | Yes | Used in LLM system prompt |
| `get_actions` | Yes | Dict of `action_name → description` |
| `execute` | Yes | Must return `str`, raise `ExecutionError` on failure |

### Concrete Tools

| Tool | `name` | Actions |
|---|---|---|
| `WindowsTool` | `"windows"` | `open_app` |
| `BrowserTool` | `"browser"` | `open_url`, `open_site`, `search_google` |
| `FileTool` | `"file"` | `list_directory`, `create_folder`, `rename`, `move`, `copy`, `delete`, `open_file` |

---

## Memory API

### `BaseMemory` (Abstract)

```python
class BaseMemory(ABC):
    @abstractmethod
    def store(self, entry: MemoryEntry) -> None: ...

    @abstractmethod
    def get_recent(self, limit: int = 10) -> list[MemoryEntry]: ...

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]: ...

    @abstractmethod
    def clear(self) -> None: ...
```

### `MemoryManager`

```python
class MemoryManager:
    def __init__(
        self,
        memory: BaseMemory,
        context_limit: int = 5,
    ) -> None: ...

    def store_interaction(
        self, user_input: str, tasks: list[Task]
    ) -> None: ...

    def get_context(self) -> MemoryContext: ...
```

### `MemoryEntry`

```python
@dataclass
class MemoryEntry:
    user_input: str
    tasks: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### `MemoryContext`

```python
@dataclass
class MemoryContext:
    entries: list[MemoryEntry] = field(default_factory=list)
    formatted: str = ""
```

### `SqliteMemory`

```python
class SqliteMemory(BaseMemory):
    def __init__(self, db_path: str) -> None: ...

    def store(self, entry: MemoryEntry) -> None: ...
    def get_recent(self, limit: int = 10) -> list[MemoryEntry]: ...
    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]: ...
    def clear(self) -> None: ...
```

---

## GUI API

### `launch_gui`

```python
def launch_gui(
    agent: Agent,
    config_ctx: dict | None = None,
) -> None
```

Entry point for the PySide6 desktop application. Blocks until the window is closed.

### Key Signals

| Signal | Source | Args | Description |
|---|---|---|---|
| `message_submitted` | `InputWidget` | `str` | User sent a message |
| `clear_requested` | `InputWidget` | — | User pressed Ctrl+L |
| `status_changed` | `ChatView` | `str` | Pipeline state changed |
| `response_time` | `ChatView` | `float` | Agent.run() duration (seconds) |
| `page_changed` | `Sidebar` | `str` | User selected a page |
| `settings_clicked` | `Header` | — | Settings button clicked |
| `theme_changed` | `ThemeManager` | `Theme` | Active theme changed |

### `ThemeManager` (Singleton)

```python
class ThemeManager(QObject):
    theme_changed = Signal(object)

    @property
    def theme(self) -> Theme: ...

    def set_theme(self, theme: Theme) -> None: ...
    def stylesheet(self) -> str: ...
```

### `Theme`

```python
@dataclass(frozen=True)
class Theme:
    name: str
    # 28 semantic color tokens
    background: str
    surface: str
    surface_alt: str
    sidebar: str
    border: str
    border_light: str
    text: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_muted: str
    user_bubble: str
    bot_bubble: str
    error_bubble: str
    system_bubble: str
    success: str
    warning: str
    error: str
    input_bg: str
    input_border: str
    card_bg: str
    card_border: str
    scrollbar_bg: str
    scrollbar_handle: str
    hover_overlay: str
    shadow: str
```

---

## Exception API

### Hierarchy

```python
class JarvisError(Exception): ...         # Base for all
class LLMConnectionError(JarvisError): ... # Ollama unreachable
class ParseError(JarvisError): ...         # JSON extraction failed
class ValidationError(JarvisError): ...    # Unknown tool/action
class ExecutionError(JarvisError): ...     # Tool execution failed
class InvalidStateError(JarvisError): ...  # Illegal Task transition
class MemoryError(JarvisError): ...        # Memory operation failed
```

### Usage Pattern

```python
# Catch all Jarvis errors:
try:
    agent.run(input)
except JarvisError as exc:
    handle_error(exc)

# Catch specific errors:
try:
    planner.plan(input)
except LLMConnectionError:
    show_connection_error()
except ParseError:
    show_parse_error()
```
