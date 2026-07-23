# 🏗 Architecture

> High-level architecture of the Jarvis Local AI Operating System.

---

## System Overview

Jarvis is a **modular, pipeline-based AI agent framework** that transforms natural language into real desktop actions. The architecture follows strict separation of concerns: every module has exactly one job, dependencies flow in one direction, and the system is designed for extensibility without modification.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Jarvis Architecture                         │
│                                                                     │
│  ┌──────────┐     ┌──────────────────────────────────────────────┐  │
│  │          │     │              Core Pipeline                   │  │
│  │   GUI    │────▶│                                              │  │
│  │ (PySide6)│     │  User Input                                  │  │
│  │          │     │      │                                       │  │
│  │  ┌─────┐│     │      ▼                                       │  │
│  │  │Chat ││     │  ┌─────────┐   ┌────────┐   ┌──────────┐    │  │
│  │  │View ││     │  │  Agent  │──▶│Planner │──▶│  Parser  │    │  │
│  │  └─────┘│     │  │ (orch.) │   │        │   │  (JSON)  │    │  │
│  │  ┌─────┐│     │  └────┬────┘   └───┬────┘   └────┬─────┘    │  │
│  │  │Mem. ││     │       │            │              │          │  │
│  │  │View ││     │       │            ▼              ▼          │  │
│  │  └─────┘│     │       │       ┌────────┐   ┌──────────┐     │  │
│  │  ┌─────┐│     │       │       │  LLM   │   │Normalizer│     │  │
│  │  │Hist.││     │       │       │Client  │   │ (aliases)│     │  │
│  │  │View ││     │       │       └────────┘   └──────────┘     │  │
│  │  └─────┘│     │       │                                      │  │
│  │  ┌─────┐│     │       ▼                                      │  │
│  │  │Logs ││     │  ┌──────────┐   ┌──────────┐                │  │
│  │  │View ││     │  │Validator │──▶│ Executor │                │  │
│  │  └─────┘│     │  │(safety)  │   │  (runs)  │                │  │
│  │  ┌─────┐│     │  └────┬─────┘   └─────┬────┘                │  │
│  │  │Plug.││     │       │                │                     │  │
│  │  │View ││     │       ▼                ▼                     │  │
│  │  └─────┘│     │  ┌──────────────────────────┐                │  │
│  │  ┌─────┐│     │  │       Registry           │                │  │
│  │  │Sett.││     │  │  (tool lookup + desc.)   │                │  │
│  │  │View ││     │  └──────┬───────────────────┘                │  │
│  │  └─────┘│     │         │                                    │  │
│  └──────────┘     │         ▼                                    │  │
│                   │  ┌──────────────────────────┐                │  │
│                   │  │       Tool Layer          │                │  │
│                   │  │  ┌────────┐ ┌─────────┐  │                │  │
│                   │  │  │Windows │ │ Browser │  │                │  │
│                   │  │  └────────┘ └─────────┘  │                │  │
│                   │  │  ┌────────┐ ┌─────────┐  │                │  │
│                   │  │  │  File  │ │ Future  │  │                │  │
│                   │  │  └────────┘ └─────────┘  │                │  │
│                   │  └──────────────────────────┘                │  │
│                   └──────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Memory Subsystem                          │   │
│  │  ┌───────────────┐  ┌──────────┐  ┌────────────────────┐    │   │
│  │  │MemoryManager  │─▶│BaseMemory│◀─│  SqliteMemory      │    │   │
│  │  │(serialize/fmt)│  │(contract)│  │  (persistence)     │    │   │
│  │  └───────────────┘  └──────────┘  └────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Configuration Layer                       │   │
│  │  ┌──────────────┐  ┌──────────────────┐                     │   │
│  │  │ JarvisConfig │◀─│ Environment Vars │                     │   │
│  │  │  (frozen DC) │  │ (.env / system)  │                     │   │
│  │  └──────────────┘  └──────────────────┘                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### Entry Point (`main.py`)

The **composition root** — wires all dependencies together and selects the UI mode. Contains the dependency graph in code:

```
Config → LLMClient, SqliteMemory
WindowsTool + BrowserTool + FileTool → Registry
LLMClient + Registry → Planner
Registry → Validator
Registry → Executor
SqliteMemory → MemoryManager
Planner + Validator + Executor + MemoryManager → Agent
```

### Core Pipeline (`core/`)

| Module | Single Responsibility |
|---|---|
| `agent.py` | Orchestrates the pipeline; never parses, never calls LLM, never executes tools |
| `planner.py` | Converts user input → Task objects via LLM + parse + normalize |
| `parser.py` | Extracts JSON from raw LLM output (strips thinking blocks, fences) |
| `normalizer.py` | Maps aliases to canonical names (pure data transformation) |
| `validator.py` | Safety gate — rejects unknown tools/actions before execution |
| `executor.py` | Runs validated Tasks against Registry tools |
| `registry.py` | Single source of truth for registered tools |
| `task.py` | Unit of work with state machine (`PENDING → RUNNING → COMPLETED/FAILED`) |
| `llm.py` | Pure I/O boundary to Ollama (sends prompts, returns raw text) |
| `exceptions.py` | Unified exception hierarchy rooted at `JarvisError` |

### Tools (`tools/`)

Self-contained plugins that implement `BaseTool`. Each tool:
- Declares its `name`, `description`, and `get_actions()`
- Implements `execute(action, args)` → result string
- Communicates with the framework **only** through `BaseTool`

### Memory (`memory/`)

Conversation persistence layer with swappable backends:
- `BaseMemory` — abstract contract
- `SqliteMemory` — production implementation
- `MemoryManager` — serialization, formatting, context injection
- `models.py` — `MemoryEntry` and `MemoryContext` dataclasses

### GUI (`gui/`)

PySide6 desktop application with:
- `MainWindow` — shell composing sidebar, header, stacked views, footer
- 6 view pages (Chat, Memory, History, Logs, Plugins, Settings)
- Semantic theme engine with 3 presets
- Background worker thread for non-blocking Agent.run()

---

## Data Flow

```
User Input (text)
       │
       ▼
┌─────────────┐
│    Agent     │─── loads context from MemoryManager
│  (pipeline)  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌───────────┐     ┌────────────┐
│   Planner   │────▶│  LLMClient│────▶│   Ollama   │
│             │     │ (generate)│     │  (local)   │
│             │◀────┤ raw text  │◀────┤  response  │
│             │     └───────────┘     └────────────┘
│             │
│  parse_json │ ← strips <think> blocks, code fences
│  normalize  │ ← resolves tool/action/arg aliases
│  create     │ ← produces list[Task] in PENDING state
└──────┬──────┘
       │
       ▼ (for each Task)
┌─────────────┐
│  Validator   │ → checks tool exists, action exists
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Executor   │ → Registry.get_executor(tool_name)
│             │ → tool.execute(action, args)
│             │ → Task transitions to COMPLETED/FAILED
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Agent     │─── saves interaction to MemoryManager
│  (results)  │─── returns list[Task] to caller
└─────────────┘
```

---

## Design Principles

### 1. Single Responsibility Principle (SRP)

Every module has exactly **one reason to change**:
- `parser.py` only extracts JSON — no business logic
- `normalizer.py` only maps aliases — no execution
- `llm.py` only talks to Ollama — no parsing
- `executor.py` only runs tasks — no validation

### 2. Dependency Inversion Principle (DIP)

High-level modules depend on abstractions, not implementations:
- `Executor` and `Validator` depend on `Registry` (interface-like class)
- `MemoryManager` depends on `BaseMemory` (abstract base class)
- `Agent` depends on `Planner`, `Validator`, `Executor` (all injected)

### 3. Open/Closed Principle (OCP)

Extend without modifying:
- **New tools**: Implement `BaseTool` and call `registry.register()` — zero core changes
- **New memory backends**: Implement `BaseMemory` — zero pipeline changes
- **New themes**: Create a new `Theme` dataclass instance — zero widget changes

### 4. Constructor Injection

All dependencies are injected through constructors — `main.py` is the **sole composition root**. No module instantiates its own dependencies.

### 5. Fail-Safe Memory

Memory is fully optional. If `memory=None`, the pipeline works identically. If memory operations fail, errors are logged but never crash the pipeline.

### 6. Layered Architecture

```
┌────────────────────────────────────┐
│         Presentation (GUI/CLI)     │  ← Calls Agent.run() only
├────────────────────────────────────┤
│         Orchestration (Agent)      │  ← Coordinates pipeline
├────────────────────────────────────┤
│         Intelligence (Planner)     │  ← LLM + parse + normalize
├────────────────────────────────────┤
│         Safety (Validator)         │  ← Gate before execution
├────────────────────────────────────┤
│         Execution (Executor)       │  ← Runs tools via Registry
├────────────────────────────────────┤
│         Capability (Tools)         │  ← System interactions
├────────────────────────────────────┤
│         Persistence (Memory)       │  ← Conversation storage
├────────────────────────────────────┤
│         Configuration (Config)     │  ← Environment + defaults
└────────────────────────────────────┘
```

---

## Future Scalability

### Adding New Tools

1. Create `tools/my_tool.py` implementing `BaseTool`
2. Register in `main.py`: `registry.register(MyTool())`
3. The Planner automatically discovers it via `registry.describe()`

### Swapping the LLM Backend

Replace `LLMClient` with any class that has `generate(system_prompt, user_prompt) → str`. Inject it into `Planner`.

### Swapping Memory Backends

Implement `BaseMemory` (store, get_recent, search, clear) and inject it into `MemoryManager`. Candidates: Redis, PostgreSQL, ChromaDB (vector), Pinecone.

### Multi-Agent Support

`Agent` is a pure orchestrator. Multiple agents with different tool sets can coexist by constructing separate `Registry` instances.

### Remote Execution

The `BaseTool` interface abstracts away execution location. A tool could delegate to a remote service, containerized environment, or another machine.

### Plugin Hot-Loading

The Registry supports runtime `register()`. A future plugin manager could scan a directory and load tools dynamically.

---

## Technology Decisions

| Decision | Rationale |
|---|---|
| **Ollama** over OpenAI API | Privacy-first, zero cost, offline capable |
| **PySide6** over Electron | Native performance, single language, smaller binary |
| **SQLite** over PostgreSQL | Zero infrastructure, portable, sufficient for single-user |
| **Frozen dataclasses** over dicts | Type safety, immutability, IDE support |
| **Abstract base classes** over protocols | Explicit contracts, clearer error messages |
| **QThread workers** over asyncio | Natural fit for Qt event loop, simpler mental model |
| **Environment variables** over YAML/TOML | No extra dependencies, standard practice |
